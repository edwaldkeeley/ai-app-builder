"""REST endpoints for Figma OAuth integration and design import."""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from app.config import settings
from app.models.schemas import (
    FigmaAuthUrl,
    FigmaImportRequest,
    GenerateResponse,
    ProjectCreate,
)
from app.services.ai_service import BaseAIProvider
from app.services.figma_service import FigmaService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

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
        raise HTTPException(status_code=503, detail="Figma service not initialized")
    if not settings.figma_client_id:
        raise HTTPException(
            status_code=501,
            detail="Figma OAuth not configured. Set FIGMA_CLIENT_ID and FIGMA_CLIENT_SECRET in .env",
        )
    if not _figma.is_connected():
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
        raise HTTPException(status_code=503, detail="Figma service not initialized")

    if error:
        return _redirect_frontend("figma", "error", error)

    if not code:
        return _redirect_frontend("figma", "error", "no_code")

    # Validate state parameter to prevent CSRF
    if not _figma.validate_oauth_state(state):
        logger.warning("OAuth state mismatch — possible CSRF attack")
        return _redirect_frontend("figma", "error", "state_mismatch")

    try:
        await _figma.exchange_code(code)
        return _redirect_frontend("figma", "connected", "")
    except Exception as e:
        logger.exception("Figma OAuth callback failed")
        return _redirect_frontend("figma", "error", "authentication_failed")


def _redirect_frontend(category: str, status_str: str, message: str) -> HTMLResponse:
    """Return an HTML page that closes the OAuth popup and notifies the opener.

    Uses ``postMessage`` to communicate the OAuth result back to the
    frontend, then closes the popup window.
    """
    frontend_url = settings.cors_origins[0] if settings.cors_origins else "http://localhost:3000"
    # Build a safe query string — no user input in the JS string literal
    params = urlencode({status_str: message}) if message else status_str
    html = f"""<!DOCTYPE html>
<html>
<body>
<script>
    (function() {{
        var origin = '{frontend_url}';
        var msg = {{ type: 'figma-oauth', status: '{status_str}', category: '{category}' }};
        if (window.opener) {{
            window.opener.postMessage(msg, origin);
            window.close();
        }} else {{
            window.location.href = origin + '?figma=' + '{status_str}';
        }}
    }}());
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
        raise HTTPException(status_code=503, detail="Figma service not initialized")
    return {"connected": _figma.is_connected()}


@router.get("/files")
async def list_files():
    """List the user's Figma files.

    Requires an active Figma OAuth session. Note: file listing via the
    Figma API may require an enterprise account. If it fails, users can
    still import by file key.
    """
    if _figma is None:
        raise HTTPException(status_code=503, detail="Figma service not initialized")

    if not await _figma.ensure_connected():
        raise HTTPException(status_code=401, detail="Not connected to Figma. Please re-authenticate.")

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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch Figma files")
        # Return empty list with a flag instead of crashing — the frontend
        # will show a manual file key input as fallback
        return {"files": [], "error": str(e), "listing_unavailable": True}


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
            detail="Required services not initialized",
        )

    if not await _figma.ensure_connected():
        raise HTTPException(status_code=401, detail="Not connected to Figma. Please re-authenticate.")

    # Fetch the Figma file data
    try:
        file_data = await _figma.get_file(body.figma_file_key)
    except Exception as e:
        logger.exception("Failed to fetch Figma file")
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
