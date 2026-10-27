"""RouteController: GET /route. Solo traduce HTTP <-> RoutingService (sin Dijkstra, R1)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from controller.controllers.dependencies import get_routing_service
from controller.models import Metric
from controller.schemas import RouteResponse
from controller.services.routing_service import RoutingService

router = APIRouter(tags=["routes"])


class RouteController:
    def __init__(self, routing_service: RoutingService) -> None:
        self._routing_service = routing_service

    def get_route(self, src: str, dst: str, metric: Metric) -> RouteResponse:
        return RouteResponse.from_domain(self._routing_service.find_route(src, dst, metric))


@router.get("/route", response_model=RouteResponse)
def get_route(
    src: str = Query(min_length=1),
    dst: str = Query(min_length=1),
    metric: Metric = Query(Metric.DELAY),
    routing_service: RoutingService = Depends(get_routing_service),
) -> RouteResponse:
    return RouteController(routing_service).get_route(src, dst, metric)
