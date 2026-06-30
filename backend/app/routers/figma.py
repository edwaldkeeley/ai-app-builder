"""REST endpoints for Figma OAuth integration and design import."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from app.models.schemas import (
    FigmaAuthUrl,
    FigmaImportRequest,
    GenerateResponse,
    ProjectCreate,
    ProjectFile,
)
from app.services.ai_service import BaseAIProvider
from app.services.figma_service import FigmaService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/figma", tags=["figma"])

_figma: FigmaService | None = None
_provider: BaseAIProvider | None = None
_service: ProjectService | None = None


def set_dependencies(
    figma: FigmaService,
    provider: BaseAIProvider | None = None,
    service: ProjectService | None = None,
) -> None:
    global _figma, _provider, _service
    _figma = figma
    _provider = provider
    _service = service


# ── OAuth endpoints ────────────────────────────────────────────


@router.get("/auth-url", response_model=FigmaAuthUrl)
async def get_auth_url():
    """Get the Figma OAuth authorization URL.

    The frontend should open this URL in a new window to start the
    OAuth flow. After authorization, Figma redirects to ``/callback``.
    """
    if _figma is None:
        raise HTTPException(status_code=503, detail="Figma service not initialised")
    if not settings.figma_client_id:
        raise HTTPException(
            status_code=501,
            detail="Figma OAuth not configured. Set FIGMA_CLIENT_ID and FIGMA_CLIENT_SECRET in .env",
        )
    if not _figma.is_connected():
        # Only load tokens on first access if not already connected
        await _figma.load_tokens()
    return FigmaAuthUrl(url=_figma.get_auth_url())


@router.get("/callback")
async def callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
):
    """Handle the OAuth callback from Figma.

    Exchanges the authorization code for tokens and redirects the
    browser back to the frontend with a success indicator.
    """
    if _figma is None:
        raise HTTPException(status_code=503, detail="Figma service not initialised")

    if error:
        return _redirect_frontend(f"?figma=error&message={error}")

    if not code:
        return _redirect_frontend("?figma=error&message=no_code")

    try:
        await _figma.exchange_code(code)
        return _redirect_frontend("?figma=connected")
    except Exception as e:
        return _redirect_frontend(f"?figma=error&message={str(e)}")


def _redirect_frontend(query: str) -> HTMLResponse:
    """Return an HTML redirect response to the frontend.

    FastAPI doesn't have a built-in 302 for external URLs in a way
    that works cleanly with OAuth popups, so we return a small HTML
    page that closes the popup and notifies the opener.
    """
    # Use the first allowed CORS origin as the frontend URL
    frontend_url = settings.cors_origins[0] if settings.cors_origins else "http://localhost:3000"
    html = f"""<!DOCTYPE html>
<html>
<body>
<script>
    if (window.opener) {{
        window.opener.postMessage({{ type: 'figma-oauth', query: '{query}' }}, '{frontend_url}');
        window.close();
    }} else {{
        window.location.href = '{frontend_url}{query}';
    }}
</script>
<p>Redirecting...</p>
</body>
</html>"""
    return HTMLResponse(content=html)


# ── Status and file listing ────────────────────────────────────


@router.get("/status")
async def get_status():
    """Check if the user is connected to Figma."""
    if _figma is None:
        raise HTTPException(status_code=503, detail="Figma service not initialised")
    return {"connected": _figma.is_connected()}


@router.get("/files")
async def list_files():
    """List the user's Figma files.

    Requires an active Figma OAuth session.
    """
    if _figma is None:
        raise HTTPException(status_code=503, detail="Figma service not initialised")

    if not _figma.is_connected():
        raise HTTPException(status_code=401, detail="Not connected to Figma")

    try:
        files = await _figma.get_files()
        return {
            "files": [
                {
                    "key": f.get("key", ""),
                    "name": f.get("name", "Untitled"),
                    "last_modified": f.get("last_modified"),
                    "thumbnail_url": f.get("thumbnail_url"),
                }
                for f in files
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch Figma files: {str(e)}",
        )


# ── Import endpoint ────────────────────────────────────────────


@router.post("/import", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def import_figma(body: FigmaImportRequest):
    """Import a Figma design and generate code from it.

    Fetches the Figma file data, builds a structured design prompt,
    and feeds it into the AI generation pipeline. Creates a new project
    with the generated files.
    """
    if _figma is None or _provider is None or _service is None:
        raise HTTPException(
            status_code=503,
            detail="Required services not initialised",
        )

    if not _figma.is_connected():
        raise HTTPException(status_code=401, detail="Not connected to Figma")

    # Fetch the Figma file data
    try:
        file_data = await _figma.get_file(body.figma_file_key)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch Figma file: {str(e)}",
        )

    # Build a structured design prompt from the Figma data
    design_prompt = _figma.build_design_prompt(file_data)
    design_name = file_data.get("name", "Figma Import")

    # Create a new project
    project = await _service.create(
        ProjectCreate(
            name=design_name,
            description=f"Imported from Figma (file key: {body.figma_file_key})",
        )
    )
    project_id = project.id

    # Generate code from the design prompt
    try:
        message, files = await _provider.generate(design_prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Persist files and chat messages
    await _service.upsert_files_transactional(project_id, files)
    await _service.save_chat_message(project_id, "user", design_prompt)
    await _service.save_chat_message(project_id, "assistant", message, files)

    return GenerateResponse(
        project_id=project_id,
        project_name=design_name,
        message=message,
        files=files,
    )
