# Domain models are defined per-service module.
# Import them here to ensure Alembic detects all tables via Base.metadata.
from app.models.catalog import Album, Artist, Track  # noqa: F401
from app.models.follow import Follow  # noqa: F401
from app.models.melody import Melody  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.rating import Rating, Report  # noqa: F401
from app.models.spotify import SpotifyConnection  # noqa: F401
from app.models.user import User  # noqa: F401
