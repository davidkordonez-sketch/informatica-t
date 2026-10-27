"""ForwardingService: plano de datos del Router (FR-08, FR-10, R9).

- Pide la ruta al RouteProvider (nunca la calcula).
- DELIVERED o UNREACHABLE -> se persiste SIEMPRE, exactamente una vez, antes de responder.
- Cualquier otro error del proveedor se propaga sin crear resultado ni escribir en el log.
- Un fallo del DAO nunca convierte la simulación en error: log_persisted = false + aviso.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable, List

from router.clients.route_provider import RouteProvider
from router.dao.forwarding_log_dao import ForwardingLogDAO
from router.exceptions import RouteNotFoundError
from router.models import ForwardingResult, ForwardingStatus, HopRecord, Packet, ResultWarning, RouteInfo

logger = logging.getLogger("router")

PERSISTENCE_WARNING = ResultWarning("PERSISTENCE_ERROR", "Forwarding log could not be persisted")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ForwardingService:
    def __init__(
        self, route_provider: RouteProvider, log_dao: ForwardingLogDAO, clock: Callable[[], str] = _utc_now
    ) -> None:
        self._route_provider = route_provider
        self._log_dao = log_dao
        self._clock = clock

    def forward_packet(self, packet: Packet) -> ForwardingResult:
        try:
            route = self._route_provider.get_route(packet.src, packet.dst, packet.metric)
        except RouteNotFoundError:
            result = ForwardingResult(
                packet_id=packet.packet_id,
                src=packet.src,
                dst=packet.dst,
                metric=packet.metric,
                status=ForwardingStatus.UNREACHABLE,
                route=None,
                trace=[],
                reason="ROUTE_NOT_FOUND",
                timestamp=self._clock(),
            )
        else:
            result = ForwardingResult(
                packet_id=packet.packet_id,
                src=packet.src,
                dst=packet.dst,
                metric=packet.metric,
                status=ForwardingStatus.DELIVERED,
                route=route,
                trace=self._simulate_hops(packet, route),
                reason=None,
                timestamp=self._clock(),
            )
        return self._persist(result)

    def _simulate_hops(self, packet: Packet, route: RouteInfo) -> List[HopRecord]:
        """Un registro por salto, en el orden de la ruta del Controller (AC-08.1)."""
        return [
            HopRecord(hop=index, from_node=from_node, to_node=to_node, status="FORWARDED")
            for index, (from_node, to_node) in enumerate(zip(route.path, route.path[1:]), start=1)
        ]

    def _persist(self, result: ForwardingResult) -> ForwardingResult:
        try:
            self._log_dao.save(result)
        except Exception:  # PersistenceError u otra falla del DAO: filas D2 / D4
            logger.exception("Forwarding result %s could not be persisted", result.packet_id)
            return replace(result, log_persisted=False, warnings=[PERSISTENCE_WARNING])
        return replace(result, log_persisted=True, warnings=[])
