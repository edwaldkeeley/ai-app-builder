"""REST and WebSocket endpoints for AI-powered code generation."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.models.schemas import GenerateResponse, ProjectCreate, ProjectFile, PromptRequest
from app.services.ai_service import BaseAIProvider
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/ai", tags=["ai"])

_provider: BaseAIProvider | None = None
_service: ProjectService | None = None


def set_dependencies(provider: BaseAIProvider, service: ProjectService) -> None:
    global _provider, _service
    _provider = provider
    _service = service


# ── REST endpoint (kept as fallback) ─────────────────────────────


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate(body: PromptRequest):
    """Generate code from a text prompt using the configured AI provider.

    If ``project_id`` is provided, the generated files are added to that
    project.  Otherwise a new project is created.
    """
    if _provider is None or _service is None:
        raise HTTPException(
            status_code=503,
            detail="AI provider not initialised. Set TARGET_URL, JWT_TOKEN, and MODEL.",
        )

    # Load existing files and chat history for context
    existing_files: list | None = None
    chat_history: list[dict[str, str]] | None = None

    if body.project_id:
        project = await _service.get(body.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        existing_files = project.files
        # Load chat history for context
        chat_msgs = await _service.get_chat_messages(body.project_id)
        chat_history = [
            {"role": m.role, "content": m.content} for m in chat_msgs
        ]

    try:
        message, files = await _provider.generate(body.prompt, existing_files, chat_history)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if body.project_id:
        project = await _service.get(body.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        # Atomic: upsert all files in a single transaction
        await _service.upsert_files_transactional(project.id, files)

        # Save chat messages
        await _service.save_chat_message(project.id, "user", body.prompt)
        await _service.save_chat_message(project.id, "assistant", message, files)

        project_name = project.name
        project_id = project.id
    else:
        name = body.prompt[:120].strip()
        project = await _service.create(
            ProjectCreate(
                name=name,
                description=f"Generated from: {body.prompt[:200]}",
            )
        )
        project_id = project.id
        project_name = project.name

        # Atomic: upsert all files in a single transaction
        await _service.upsert_files_transactional(project_id, files)

        # Save chat messages
        await _service.save_chat_message(project_id, "user", body.prompt)
        await _service.save_chat_message(project_id, "assistant", message, files)

    return GenerateResponse(
        project_id=project_id,
        project_name=project_name,
        message=message,
        files=files,
    )


# ── WebSocket streaming endpoint ─────────────────────────────────


@router.websocket("/ws/generate")
async def ws_generate(websocket: WebSocket):
    """Stream AI generation results over WebSocket.

    Protocol — client sends::

        {"type": "generate", "prompt": "...", "project_id": "..."}

    Server streams events (JSON per message):

        {"type": "status", "status": "connected"}
        {"type": "project", "project_id": "...", "project_name": "..."}
        {"type": "message_chunk", "delta": "..."}
        {"type": "file_start", "path": "...", "file_type": "..."}
        {"type": "file_chunk", "path": "...", "delta": "..."}
        {"type": "file_done", "path": "..."}
        {"type": "done", "message": "...", "files": [...]}
        {"type": "error", "detail": "..."}
    """
    if _provider is None or _service is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "detail": "AI provider not configured."})
        await websocket.close()
        return

    await websocket.accept()
    await websocket.send_json({"type": "status", "status": "connected"})

    project_id: str | None = None

    try:
        # Receive the generate command
        raw = await websocket.receive_text()
        msg = json.loads(raw)

        if msg.get("type") != "generate":
            await websocket.send_json({"type": "error", "detail": "Expected 'generate' message."})
            await websocket.close()
            return

        prompt = msg.get("prompt", "").strip()
        if not prompt:
            await websocket.send_json({"type": "error", "detail": "Prompt is required."})
            await websocket.close()
            return

        incoming_project_id = msg.get("project_id")

        # Resolve or create project
        if incoming_project_id:
            project = await _service.get(incoming_project_id)
            if project is None:
                await websocket.send_json({"type": "error", "detail": "Project not found."})
                await websocket.close()
                return
        else:
            name = prompt[:120].strip()
            project = await _service.create(
                ProjectCreate(
                    name=name,
                    description=f"Generated from: {prompt[:200]}",
                )
            )

        project_id = str(project.id)
        await websocket.send_json({
            "type": "project",
            "project_id": project_id,
            "project_name": project.name,
        })

        # Load existing files and chat history for context
        existing_files = project.files
        chat_msgs = await _service.get_chat_messages(project.id)
        chat_history = [
            {"role": m.role, "content": m.content} for m in chat_msgs
        ]

        # Stream generation events
        done_event = None
        async for event in _provider.generate_stream(prompt, existing_files, chat_history):
            await websocket.send_json(event)

            if event["type"] == "done":
                done_event = event

        # Persist files to database after streaming completes (atomic transaction)
        if done_event and project_id:
            done_files_data = done_event.get("files", [])
            done_files = [ProjectFile(**f) for f in done_files_data]
            await _service.upsert_files_transactional(project_id, done_files)

            # Save chat messages
            await _service.save_chat_message(project_id, "user", prompt)
            done_message = done_event.get("message", "")
            await _service.save_chat_message(project_id, "assistant", done_message, done_files)

    except WebSocketDisconnect:
        return
    except json.JSONDecodeError:
        try:
            await websocket.send_json({"type": "error", "detail": "Invalid JSON received."})
        except WebSocketDisconnect:
            pass
    except RuntimeError as e:
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except WebSocketDisconnect:
            pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "detail": f"Unexpected error: {e}"})
        except WebSocketDisconnect:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
