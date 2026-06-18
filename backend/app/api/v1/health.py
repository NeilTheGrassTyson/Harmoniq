from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
