from fastapi import APIRouter

from app.api.v1 import (
    catalog,
    follows,
    health,
    home,
    melodies,
    moderation,
    notifications,
    ratings,
    spotify,
    users,
    webhooks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(catalog.router)
api_router.include_router(users.router)
api_router.include_router(webhooks.router)
api_router.include_router(ratings.router)
api_router.include_router(follows.router)
api_router.include_router(home.router)
api_router.include_router(spotify.router)
api_router.include_router(melodies.router)
api_router.include_router(notifications.router)
api_router.include_router(moderation.router)
