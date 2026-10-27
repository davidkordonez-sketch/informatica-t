"""HealthController: GET /health. No dispara cargas de topología (usa peek_snapshot)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from controller.controllers.dependencies import get_topology_service
from controller.schemas import HealthResponse
from controller.services.topology_service import TopologyService

router = APIRouter(tags=["health"])


class HealthController:
    def __init__(self, topology_service: TopologyService) -> None:
        self._topology_service = topology_service

    def get_health(self) -> HealthResponse:
        snapshot = self._topology_service.peek_snapshot()
        if snapshot is None:
            return HealthResponse(status="degraded", service="controller", topology_loaded=False, topology_version=0)
        return HealthResponse(status="ok", service="controller", topology_loaded=True, topology_version=snapshot.version)


@router.get("/health", response_model=HealthResponse)
def get_health(topology_service: TopologyService = Depends(get_topology_service)) -> HealthResponse:
    return HealthController(topology_service).get_health()
