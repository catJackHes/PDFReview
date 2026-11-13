from __future__ import annotations

from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=HealthResponse)
def ready() -> dict[str, str]:
    return {"status": "ok"}
