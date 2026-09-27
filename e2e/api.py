"""External catalog fixture; real routes, JWT verification, services and database."""

import os

from app.main import app  # noqa: F401
from app.services import musicbrainz

# This module is an explicit test runner entry point, never a production import.
musicbrainz._MB_BASE = os.environ["E2E_PROVIDER_URL"]
