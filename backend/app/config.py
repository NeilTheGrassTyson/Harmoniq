from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────────
    # Constrained, not a bare str: app_env gates /docs and /redoc in main.py,
    # so a typo ("prod", "Production") would silently serve the API docs
    # publicly. An invalid value now refuses to boot instead.
    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Harmoniq"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str  # postgresql+asyncpg://user:pass@host/db

    # ── Clerk auth ───────────────────────────────────────────────────────────
    clerk_jwks_url: str  # https://api.clerk.com/v1/jwks (per Clerk app)
    # Optional until provisioned — validated at the call site when used.
    clerk_secret_key: str | None = None  # sk_live_... — Clerk Management API
    clerk_webhook_secret: str | None = None  # whsec_... — webhook signature

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # Example: "http://localhost:3000,https://harmoniq.live"
    cors_allowed_origins: str = "http://localhost:3000"

    # ── MusicBrainz ──────────────────────────────────────────────────────────
    musicbrainz_user_agent: str  # "AppName/Version contact@example.com"

    # ── Search ───────────────────────────────────────────────────────────────
    # Local-first catalog search (specs/local-first-search.md). Off restores
    # the MusicBrainz-first path unchanged — the rollback lever.
    search_local_first: bool = True

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
    def debug(self) -> bool:
        """Verbose logging and SQLAlchemy echo — local development only.

        Derived rather than configured: a separate DEBUG variable was a second
        way to say the same thing, and the two could disagree. Deliberately
        `== "development"` and not `!= "production"`, so the test environment
        stays quiet.
        """
        return self.app_env == "development"

    @property
    def cors_origins_list(self) -> list[str]:
        # Trailing slashes are stripped and blank entries dropped: an Origin
        # header is a bare scheme://host[:port], so "https://app.example.com/"
        # never matches one and CORSMiddleware rejects every browser request
        # with no error the operator can see (docs/deployment.md records this
        # costing a live debugging session). Normalising here means the env
        # var can be written either way.
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip().rstrip("/")
        ]

    @property
    def cors_origins_look_like_production(self) -> bool:
        """True when every allowed origin is a remote https:// domain.

        A developer's machine always needs a localhost origin to talk to its
        own frontend, so an allow-list with none is a deployed one. Used by
        main.py to catch an APP_ENV that was never set; an empty list is a
        different misconfiguration and is not reported here.
        """
        origins = self.cors_origins_list
        return bool(origins) and all(
            origin.startswith("https://") and "localhost" not in origin
            for origin in origins
        )


settings = Settings()  # type: ignore[call-arg]
