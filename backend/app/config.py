from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_name: str = "Harmoniq"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str  # postgresql+asyncpg://user:pass@host/db

    # ── Clerk auth ───────────────────────────────────────────────────────────
    clerk_jwks_url: str  # https://api.clerk.com/v1/jwks (per Clerk app)

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # Example: "http://localhost:3000,https://harmoniq.app"
    cors_allowed_origins: str = "http://localhost:3000"

    # ── Rate limiting ────────────────────────────────────────────────────────
    rate_limit_default: str = "100/minute"

    # ── MusicBrainz ──────────────────────────────────────────────────────────
    musicbrainz_user_agent: str  # "AppName/Version contact@example.com"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",")]


settings = Settings()  # type: ignore[call-arg]
