"""Figma type definitions: exception classes and color conversion helpers.

These are pure functions with no state or IO — used across other figma modules.
"""


class FigmaApiError(RuntimeError):
    """Raised when a Figma API call fails with a non-429 error."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        super().__init__(detail)


class FigmaRateLimitError(RuntimeError):
    """Raised when Figma API returns 429 and retries are exhausted.

    Attributes:
        retry_after: Seconds the caller should wait before retrying.
    """

    def __init__(self, retry_after: int, message: str | None = None) -> None:
        self.retry_after = retry_after
        if message is None:
            message = f"Figma API rate limited. Retry after {retry_after}s."
        super().__init__(message)


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """Convert 0-1 RGB floats to hex string."""
    return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"


def get_solid_color(fills: list[dict] | None) -> str | None:
    """Extract the first solid fill color as hex, or None."""
    if not fills:
        return None
    for f in fills:
        if f.get("type") == "SOLID":
            c = f.get("color", {})
            return rgb_to_hex(c.get("r", 0), c.get("g", 0), c.get("b", 0))
    return None


def get_text_color(node: dict) -> str:
    """Extract text color from a node's fills."""
    color = get_solid_color(node.get("fills"))
    return color or "#000000"
