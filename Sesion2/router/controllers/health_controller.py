"""HealthController del Router: responde 200 aunque el Controller esté caído (NFR-11)."""
from __future__ import annotations

from fastapi import APIRouter

from router.schemas import HealthResponse

router = APIRouter(tags=["health"])


class HealthController:
    def get_health(self) -> HealthResponse:
        return HealthResponse(status="ok", service="router")


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthController().get_health()
