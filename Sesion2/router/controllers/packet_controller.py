"""PacketController: POST /packets. Solo delega en ForwardingService (sin reenvío aquí, R1)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from router.controllers.dependencies import get_forwarding_service
from router.schemas import ForwardingResultResponse, PacketRequest
from router.services.forwarding_service import ForwardingService

router = APIRouter(tags=["packets"])


class PacketController:
    def __init__(self, forwarding_service: ForwardingService) -> None:
        self._forwarding_service = forwarding_service

    def post_packet(self, request: PacketRequest) -> ForwardingResultResponse:
        return ForwardingResultResponse.from_domain(self._forwarding_service.forward_packet(request.to_domain()))


@router.post("/packets", response_model=ForwardingResultResponse)
def post_packet(
    request: PacketRequest, forwarding_service: ForwardingService = Depends(get_forwarding_service)
) -> ForwardingResultResponse:
    return PacketController(forwarding_service).post_packet(request)
