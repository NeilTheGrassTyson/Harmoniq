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
    # Optional until provisioned — validated at the call site when used.
    clerk_secret_key: str | None = None  # sk_live_... — Clerk Management API
    clerk_webhook_secret: str | None = None  # whsec_... — webhook signature

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # Example: "http://localhost:3000,https://harmoniq.app"
    cors_allowed_origins: str = "http://localhost:3000"

    # ── Rate limiting ────────────────────────────────────────────────────────
    rate_limit_default: str = "100/minute"

    # ── MusicBrainz ──────────────────────────────────────────────────────────
    musicbrainz_user_agent: str  # "AppName/Version contact@example.com"

    # ── Home sections ────────────────────────────────────────────────────────
    # Number of entries returned per section on the Home page.
    home_trending_count: int = 10
    home_friends_count: int = 10

    # ── Cloudflare R2 (avatar storage) ───────────────────────────────────────
    # Optional until provisioned — validated at the call site when used.
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    r2_public_url: str | None = None  # e.g. https://pub-xxx.r2.dev

    # ── Spotify (account linking + listening display) ────────────────────────
    # Optional until provisioned — validated at the call site when used.
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    # Must exactly match the URI registered in the Spotify dashboard; new
    # Spotify apps require a loopback IP literal for http (not localhost).
    spotify_redirect_uri: str | None = None  # http://127.0.0.1:3000/spotify-callback

    # ── Token encryption ─────────────────────────────────────────────────────
    # Fernet key (urlsafe base64, from Fernet.generate_key()). Encrypts
    # stored OAuth refresh tokens and signs OAuth state (documented dual use).
    token_encryption_key: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",")]


settings = Settings()  # type: ignore[call-arg]
