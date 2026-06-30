"""Figma OAuth and API integration service.

Provides OAuth 2.0 authentication flow, Figma REST API access for
fetching file data, and a design-to-prompt converter that feeds into
the existing AI generation pipeline.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.db.database import acquire_with_retry, get_pool

logger = logging.getLogger(__name__)

FIGMA_OAUTH_URL = "https://www.figma.com/oauth"
FIGMA_API_URL = "https://api.figma.com/v1"
FIGMA_TOKEN_URL = "https://www.figma.com/api/oauth/token"
FIGMA_SCOPE = "file_content:read"

_MAX_WALK_DEPTH = 200


class FigmaService:
    """Handles Figma OAuth flow and API interactions.

    Tokens are persisted in the database and cached in-memory for the
    lifetime of the service. Follows the singleton pattern injected into
    ``app.state``.
    """

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._oauth_state: str | None = None

    # ── Token management ──────────────────────────────────────

    async def load_tokens(self) -> None:
        """Load tokens from the database into memory."""
        pool = get_pool()
        conn = await acquire_with_retry(pool)
        try:
            row = await conn.fetchrow(
                "SELECT access_token, refresh_token FROM figma_tokens ORDER BY id DESC LIMIT 1"
            )
            if row:
                self._access_token = row["access_token"]
                self._refresh_token = row.get("refresh_token")
        finally:
            await pool.release(conn)

    async def _save_tokens(self, access_token: str, refresh_token: str | None = None) -> None:
        """Persist tokens to the database."""
        self._access_token = access_token
        if refresh_token:
            self._refresh_token = refresh_token

        pool = get_pool()
        conn = await acquire_with_retry(pool)
        try:
            async with conn.transaction():
                await conn.execute("DELETE FROM figma_tokens")
                await conn.execute(
                    "INSERT INTO figma_tokens (access_token, refresh_token) VALUES ($1, $2)",
                    access_token,
                    refresh_token,
                )
        finally:
            await pool.release(conn)

    async def clear_tokens(self) -> None:
        """Remove all stored tokens."""
        self._access_token = None
        self._refresh_token = None
        pool = get_pool()
        conn = await acquire_with_retry(pool)
        try:
            await conn.execute("DELETE FROM figma_tokens")
        finally:
            await pool.release(conn)

    def is_connected(self) -> bool:
        """Check if we have a valid access token."""
        return self._access_token is not None

    async def ensure_connected(self) -> bool:
        """Ensure we have a valid token, attempting refresh if needed.

        Returns True if connected, False if not (caller should tell user to re-auth).
        """
        if self._access_token:
            return True
        # Try loading from DB
        await self.load_tokens()
        if self._access_token:
            return True
        # Try refreshing if we have a refresh token
        if self._refresh_token:
            try:
                await self.refresh_access_token()
                return True
            except Exception:
                await self.clear_tokens()
                return False
        return False

    # ── OAuth flow ────────────────────────────────────────────

    def get_auth_url(self) -> str:
        """Build the Figma OAuth authorization URL with CSRF state."""
        self._oauth_state = secrets.token_urlsafe(32)
        # Normalize redirect URI: strip trailing slash to avoid mismatch
        redirect_uri = settings.figma_redirect_uri.rstrip("/")
        params = {
            "client_id": settings.figma_client_id,
            "redirect_uri": redirect_uri,
            "scope": FIGMA_SCOPE,
            "state": self._oauth_state,
            "response_type": "code",
        }
        logger.info("Figma OAuth URL built with redirect_uri=%s", redirect_uri)
        return f"{FIGMA_OAUTH_URL}?{urlencode(params)}"

    def validate_oauth_state(self, state: str | None) -> bool:
        """Validate the OAuth state parameter to prevent CSRF attacks.

        Returns True if the state matches the one we issued.
        """
        if not state or not self._oauth_state:
            return False
        return secrets.compare_digest(self._oauth_state, state)

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange an authorization code for access and refresh tokens.

        Returns the parsed JSON response from Figma's token endpoint.
        Automatically persists the tokens on success.
        Raises RuntimeError if the response does not contain an access token.
        """
        redirect_uri = settings.figma_redirect_uri.rstrip("/")
        data = {
            "client_id": settings.figma_client_id,
            "client_secret": settings.figma_client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(FIGMA_TOKEN_URL, data=data)
            response.raise_for_status()
            result = response.json()

        access_token = result.get("access_token")
        if not access_token:
            raise RuntimeError(
                "Figma token exchange succeeded but no access_token in response"
            )

        refresh_token = result.get("refresh_token")
        await self._save_tokens(access_token, refresh_token)
        # Clear the stored state after successful exchange
        self._oauth_state = None

        return result

    async def refresh_access_token(self) -> dict[str, Any]:
        """Refresh the access token using the stored refresh token."""
        if not self._refresh_token:
            raise RuntimeError("No refresh token available")

        data = {
            "client_id": settings.figma_client_id,
            "client_secret": settings.figma_client_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(FIGMA_TOKEN_URL, data=data)
            response.raise_for_status()
            result = response.json()

        access_token = result.get("access_token")
        if not access_token:
            raise RuntimeError("Token refresh succeeded but no access_token in response")

        refresh_token = result.get("refresh_token") or self._refresh_token
        await self._save_tokens(access_token, refresh_token)

        return result

    # ── Figma API calls ───────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        """Build auth headers for Figma API requests."""
        if not self._access_token:
            raise RuntimeError("Not authenticated with Figma")
        return {"Authorization": f"Bearer {self._access_token}"}

    async def get_me(self) -> dict[str, Any]:
        """Get the authenticated user's info."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{FIGMA_API_URL}/me", headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def get_files(self) -> list[dict[str, Any]]:
        """List the user's Figma files and projects.

        Note: This endpoint may require an enterprise Figma account.
        Non-enterprise users will receive a 403/404.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{FIGMA_API_URL}/me/files",
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
            return data.get("files", [])

    async def get_file(self, file_key: str) -> dict[str, Any]:
        """Fetch the full document JSON for a Figma file."""
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{FIGMA_API_URL}/files/{file_key}",
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def get_file_images(
        self, file_key: str, ids: list[str]
    ) -> dict[str, Any]:
        """Get rendered image URLs for specific nodes."""
        ids_param = ",".join(ids)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{FIGMA_API_URL}/images/{file_key}?ids={ids_param}",
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    # ── Design prompt builder ─────────────────────────────────

    def build_design_prompt(self, file_data: dict[str, Any]) -> str:
        """Extract key design information from Figma JSON and build a structured prompt.

        The prompt is designed to be fed into the existing AI generation pipeline
        so the AI can produce HTML/CSS that matches the Figma design.
        """
        document = file_data.get("document")
        if not document or not isinstance(document, dict):
            return (
                "Convert this Figma design to HTML/CSS code. "
                "The design data could not be fully parsed, so create a "
                "beautiful, responsive web page based on the design name: "
                f"{file_data.get('name', 'Untitled Design')}."
            )

        name = file_data.get("name", "Untitled Design")
        pages = []
        colors: set[str] = set()
        fonts: set[str] = set()
        elements: list[str] = []

        def walk_nodes(node: dict[str, Any], depth: int = 0) -> None:
            if depth > _MAX_WALK_DEPTH:
                return
            node_type = node.get("type", "UNKNOWN")
            node_name = node.get("name", "")
            if depth <= 2 and node_type not in ("DOCUMENT", "CANVAS"):
                elements.append(f"  {'  ' * depth}- {node_type}: \"{node_name}\"")

            # Extract colors from fill styles
            fills = node.get("fills", [])
            if isinstance(fills, list):
                for fill in fills:
                    if fill.get("type") == "SOLID":
                        color = fill.get("color", {})
                        if color:
                            r = round(color.get("r", 0) * 255)
                            g = round(color.get("g", 0) * 255)
                            b = round(color.get("b", 0) * 255)
                            colors.add(f"rgb({r}, {g}, {b})")

            # Extract font info from text nodes
            if node_type == "TEXT":
                style = node.get("style", {})
                font_family = style.get("fontFamily")
                if font_family:
                    fonts.add(font_family)

            # Recurse into children
            for child in node.get("children", []):
                walk_nodes(child, depth + 1)

        # Process each page (canvas)
        for child in document.get("children", []):
            if child.get("type") == "CANVAS":
                page_name = child.get("name", "Untitled")
                pages.append(page_name)
                walk_nodes(child)

        # Build the prompt
        prompt_parts = [
            "Convert this Figma design to HTML/CSS code.",
            "",
            f"Design name: {name}",
        ]

        if pages:
            prompt_parts.append(f"Pages: {', '.join(pages)}")

        if elements:
            prompt_parts.append("")
            prompt_parts.append("Design structure:")
            prompt_parts.extend(elements[:50])

        if colors:
            prompt_parts.append("")
            prompt_parts.append(f"Color palette: {', '.join(sorted(colors)[:20])}")

        if fonts:
            prompt_parts.append("")
            prompt_parts.append(f"Typography: {', '.join(sorted(fonts)[:10])}")

        prompt_parts.append("")
        prompt_parts.append(
            "Create a complete, responsive web page that matches this design. "
            "Use semantic HTML5, modern CSS (flexbox/grid), and ensure the layout "
            "matches the Figma design structure. Include appropriate colors, "
            "typography, and spacing."
        )

        return "\n".join(prompt_parts)
