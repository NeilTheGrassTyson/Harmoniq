# Domain models are defined per-service module.
# Import them here to ensure Alembic detects all tables via Base.metadata.
from app.models.catalog import Album, Artist, Track  # noqa: F401
