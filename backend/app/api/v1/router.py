from fastapi import APIRouter

from app.api.v1 import catalog, health, users, webhooks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(catalog.router)
api_router.include_router(users.router)
api_router.include_router(webhooks.router)
