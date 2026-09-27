"""
Rate limiting configuration via slowapi (Starlette-native wrapper for limits).
"""

import hashlib

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

# headers_enabled surfaces X-RateLimit-* response headers on decorated routes.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    headers_enabled=True,
)


def per_session(request: Request) -> str:
    """
    Bucket by bearer credential instead of client address.

    For steady background traffic that every signed-in person generates —
    presence heartbeats — a per-address key makes everyone behind one shared
    IP (a campus network, an office) share a single budget, and past a dozen
    of them they would flicker offline. Hashing the whole header, rather than
    trusting a claim inside it, means a forged token lands in its own bucket
    and cannot drain anyone else's.
    """
    auth = request.headers.get("authorization")
    if auth:
        return "session:" + hashlib.sha256(auth.encode()).hexdigest()[:32]
    return get_remote_address(request)
