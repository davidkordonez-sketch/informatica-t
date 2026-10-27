"""TopologyController: GET /topology (una sola instantánea, G5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from controller.controllers.dependencies import get_topology_service
from controller.schemas import TopologyResponse
from controller.services.topology_service import TopologyService

router = APIRouter(tags=["topology"])


class TopologyController:
    def __init__(self, topology_service: TopologyService) -> None:
        self._topology_service = topology_service

    def get_topology(self) -> TopologyResponse:
        return TopologyResponse.from_domain(self._topology_service.get_snapshot())


@router.get("/topology", response_model=TopologyResponse)
def get_topology(topology_service: TopologyService = Depends(get_topology_service)) -> TopologyResponse:
    return TopologyController(topology_service).get_topology()
