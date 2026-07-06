"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Server ──────────────────────────────────────────────
    app_name: str = "AI Design Sandbox"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000

    # ── Paths ───────────────────────────────────────────────
    sandbox_dir: Path = Path(__file__).resolve().parent.parent / "sandbox_files"
    cors_origins: list[str] = ["http://localhost:3000"]

    # ── Figma OAuth (placeholder – configure when integrating) ──
    figma_client_id: str = ""
    figma_client_secret: str = ""
    figma_redirect_uri: str = "http://localhost:8000/api/figma/callback"

    # ── AI Provider (required) ──────────────────────────────
    target_url: str = ""
    jwt_token: str = ""
    model: str = ""
    max_tokens: int = 0  # 0 = use provider default (provider says no token limits)
    timeout_seconds: int = 600  # AI provider request timeout (default 10 min)

    # ── Database ────────────────────────────────────────────
    database_url: str = "postgresql://postgres:postgres@localhost:5432/ai_design_sandbox"
    database_pool_min_size: int = 2
    database_pool_max_size: int = 10

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
    }

    def validate_ai_config(self) -> None:
        """Raise if AI provider config is incomplete."""
        missing = []
        if not self.target_url:
            missing.append("TARGET_URL")
        if not self.jwt_token:
            missing.append("JWT_TOKEN")
        if not self.model:
            missing.append("MODEL")
        if missing:
            raise ValueError(
                f"AI provider not configured. Set the following environment variables: {', '.join(missing)}. "
                "Without these, AI generation will not work."
            )


settings = Settings()
