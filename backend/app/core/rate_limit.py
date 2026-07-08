"""
Rate limiting configuration via slowapi (Starlette-native wrapper for limits).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# headers_enabled surfaces X-RateLimit-* response headers on decorated routes.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    headers_enabled=True,
)
