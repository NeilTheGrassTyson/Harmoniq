from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)

# Feature routers are registered here as services are built:
# from app.api.v1 import users, catalog, melodies, ...
# api_router.include_router(users.router, prefix="/users", tags=["users"])
