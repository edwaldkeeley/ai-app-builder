"""Figma OAuth and API integration service.

Provides OAuth 2.0 authentication flow, Figma REST API access for
fetching file data, and a design-to-prompt converter that feeds into
the existing AI generation pipeline.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.db.database import acquire_with_retry, get_pool

logger = logging.getLogger(__name__)

FIGMA_OAUTH_URL = "https://www.figma.com/oauth"
FIGMA_API_URL = "https://api.figma.com/v1"
FIGMA_TOKEN_URL = "https://api.figma.com/v1/oauth/token"
FIGMA_SCOPE = "file_content:read"

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

    # ── URL parsing ──────────────────────────────────────────

    @staticmethod
    def extract_file_key(figma_url: str) -> str:
        """Extract the Figma file key from a URL or return the input if it's already a bare key.

        Handles formats:
        - ``https://www.figma.com/file/ABC123/My-Design``
        - ``https://www.figma.com/design/ABC123/My-Design``
        - ``https://www.figma.com/file/ABC123/``
        - ``ABC123`` (bare key)

        Raises ValueError if the URL can't be parsed and doesn't look like a bare key.
        """
        figma_url = figma_url.strip().rstrip("/")

        # Match both /file/KEY and /design/KEY patterns
        match = re.search(r"/file/([^/?#]+)", figma_url)
        if not match:
            match = re.search(r"/design/([^/?#]+)", figma_url)
        if match:
            return match.group(1)

        # If no URL pattern matched, assume it's a bare key
        # Figma keys are typically 12-22 alphanumeric chars
        if re.match(r"^[A-Za-z0-9_-]+$", figma_url):
            return figma_url

        raise ValueError(
            f"Could not extract a valid Figma file key from: {figma_url}. "
            "Expected a URL like https://www.figma.com/file/KEY/name or a bare file key."
        )

    # ── Design prompt builder ─────────────────────────────────

    def build_design_prompt(
        self,
        file_data: dict[str, Any],
    ) -> str:
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

        # ── Build a compact JSON tree from the Figma document ──

        def _fmt_color(color: dict[str, float] | None, opacity: float | None = None) -> str:
            if not color:
                return ""
            r = round(color.get("r", 0) * 255)
            g = round(color.get("g", 0) * 255)
            b = round(color.get("b", 0) * 255)
            a = opacity if opacity is not None else color.get("a", 1.0)
            return f"rgba({r},{g},{b},{a})" if a < 1.0 else f"rgb({r},{g},{b})"

        def _get_fill(node: dict[str, Any]) -> str:
            fills = node.get("fills", [])
            if isinstance(fills, list):
                for fill in fills:
                    if isinstance(fill, dict) and fill.get("type") == "SOLID":
                        c = _fmt_color(fill.get("color"), fill.get("opacity"))
                        if c:
                            return c
            return ""

        def _get_stroke(node: dict[str, Any]) -> str:
            strokes = node.get("strokes", [])
            weight = node.get("strokeWeight", 0)
            if isinstance(strokes, list) and strokes and weight:
                for s in strokes:
                    if isinstance(s, dict) and s.get("type") == "SOLID":
                        c = _fmt_color(s.get("color"))
                        if c:
                            return f"{weight}px {c}"
            return ""

        def _get_shadows(node: dict[str, Any]) -> list[str]:
            result = []
            for e in (node.get("effects") or []):
                if isinstance(e, dict) and e.get("type") in ("DROP_SHADOW", "INNER_SHADOW"):
                    ox = e.get("offset", {}).get("x", 0)
                    oy = e.get("offset", {}).get("y", 0)
                    r = e.get("radius", 0)
                    c = _fmt_color(e.get("color"))
                    result.append(f"{e['type'].lower()} {ox}px {oy}px {r}px {c}")
            return result

        def _get_text(node: dict[str, Any]) -> dict[str, Any] | None:
            if node.get("type") != "TEXT":
                return None
            style = node.get("style", {}) or {}
            chars = node.get("characters", "")
            if len(chars) > 100:
                chars = chars[:100] + "..."
            t: dict[str, Any] = {"c": chars}
            if style.get("fontFamily"):
                t["ff"] = style["fontFamily"]
            if style.get("fontSize"):
                t["fs"] = style["fontSize"]
            if style.get("fontWeight"):
                t["fw"] = style["fontWeight"]
            if style.get("lineHeightPx"):
                t["lh"] = round(style["lineHeightPx"], 1)
            if style.get("textAlignHorizontal") and style["textAlignHorizontal"] != "LEFT":
                t["ta"] = style["textAlignHorizontal"].lower()
            fill = _get_fill(node)
            if fill:
                t["co"] = fill
            return t

        def _compact(node: dict[str, Any], depth: int = 0) -> dict[str, Any] | None:
            """Convert a Figma node to a compact dict."""
            if depth > 100:
                return None
            nt = node.get("type", "")
            if nt == "DOCUMENT":
                for c in (node.get("children") or []):
                    r = _compact(c, depth)
                    if r:
                        return r
                return None

            bbox = node.get("absoluteBoundingBox") or {}
            n: dict[str, Any] = {"t": nt, "n": node.get("name", "")}

            x, y, w, h = bbox.get("x"), bbox.get("y"), bbox.get("width"), bbox.get("height")
            if x is not None:
                n["x"] = round(x, 1)
            if y is not None:
                n["y"] = round(y, 1)
            if w is not None:
                n["w"] = round(w, 1)
            if h is not None:
                n["h"] = round(h, 1)

            # Auto-layout
            lm = node.get("layoutMode")
            if lm:
                n["l"] = "row" if lm == "HORIZONTAL" else "col"
                pa = node.get("primaryAxisAlignItems")
                ca = node.get("counterAxisAlignItems")
                if pa:
                    n["jc"] = pa.lower()
                if ca:
                    n["ai"] = ca.lower()
                gap = node.get("itemSpacing")
                if gap:
                    n["gap"] = round(gap, 1)
                pads = {}
                for k in ("paddingLeft", "paddingRight", "paddingTop", "paddingBottom"):
                    v = node.get(k, 0)
                    if v:
                        pads[k.replace("padding", "").lower()] = round(v, 1)
                if pads:
                    n["pd"] = pads

            # Corner radius
            cr = node.get("cornerRadius")
            if cr and cr > 0:
                n["br"] = round(cr, 1)

            # Background
            bg = _get_fill(node)
            if bg:
                n["bg"] = bg

            # Border
            border = _get_stroke(node)
            if border:
                n["bd"] = border

            # Opacity
            op = node.get("opacity")
            if op is not None and op < 1.0:
                n["op"] = round(op, 2)

            # Shadows
            shadows = _get_shadows(node)
            if shadows:
                n["sh"] = shadows

            # Overflow
            if node.get("clipsContent"):
                n["ov"] = "hidden"

            # Text
            text = _get_text(node)
            if text:
                n["tx"] = text

            # Children
            children = node.get("children")
            if children:
                cc = []
                for child in children:
                    cr = _compact(child, depth + 1)
                    if cr:
                        cc.append(cr)
                if cc:
                    n["ch"] = cc

            return n

        # Build compact tree from the first canvas
        tree = None
        for child in (document.get("children") or []):
            if child.get("type") == "CANVAS":
                tree = _compact(child)
                break

        tree_json = json.dumps(tree, indent=2, ensure_ascii=False) if tree else "{}"

        # ── Build prompt ────────────────────────────────────────
        parts = [
            f"Design name: {name}",
            "",
            "Below is the Figma design as a compact JSON tree.",
            "Field guide: t=type, n=name, x/y=position, w/h=size, l=layout(row|col),",
            "jc=justify-content, ai=align-items, gap=gap, pd=padding, br=border-radius,",
            "bg=background, bd=border, op=opacity, sh=shadows, ov=overflow,",
            "tx=text{c=content, ff=font-family, fs=font-size, fw=font-weight,",
            "lh=line-height, ta=text-align, co=color}, ch=children.",
            "",
            "You MUST reproduce this design EXACTLY in HTML/CSS.",
            "Use the x,y coordinates for positioning (canvas origin 0,0 is top-left).",
            "Use w,h for element sizes. Set explicit width/height in CSS.",
            "",
            "FIGMA TREE:",
            "```json",
            tree_json,
            "```",
            "",
            "STRICT RULES:",
            "- Use x,y,w,h from the JSON for positioning and sizing.",
            "- Use bg for background colors, bd for borders, br for border-radius.",
            "- Use tx.ff/fs/fw/lh/ta/co for text styling.",
            "- For l='row' use display:flex + flex-direction:row.",
            "- For l='col' use display:flex + flex-direction:column.",
            "- Match jc/ai/gap/pd values to CSS justify-content/align-items/gap/padding.",
            "- Match sh values to CSS box-shadow.",
            "- Create ONE self-contained index.html with embedded CSS in <style>.",
            "- DO NOT add, remove, or rearrange anything.",
            "- DO NOT change colors, fonts, or spacing.",
            "- The page must look IDENTICAL to the Figma design.",
        ]

        return "\n".join(parts)
