"""LinkController: POST /links/fail y /links/restore (FR-06)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from controller.controllers.dependencies import get_topology_service
from controller.schemas import LinkRequest, LinkStateResponse
from controller.services.topology_service import TopologyService

router = APIRouter(tags=["links"])


class LinkController:
    def __init__(self, topology_service: TopologyService) -> None:
        self._topology_service = topology_service

    def fail_link(self, request: LinkRequest) -> LinkStateResponse:
        return LinkStateResponse.from_domain(self._topology_service.fail_link(request.node_a, request.node_b))

    def restore_link(self, request: LinkRequest) -> LinkStateResponse:
        return LinkStateResponse.from_domain(self._topology_service.restore_link(request.node_a, request.node_b))


@router.post("/links/fail", response_model=LinkStateResponse)
def fail_link(
    request: LinkRequest, topology_service: TopologyService = Depends(get_topology_service)
) -> LinkStateResponse:
    return LinkController(topology_service).fail_link(request)


@router.post("/links/restore", response_model=LinkStateResponse)
def restore_link(
    request: LinkRequest, topology_service: TopologyService = Depends(get_topology_service)
) -> LinkStateResponse:
    return LinkController(topology_service).restore_link(request)
