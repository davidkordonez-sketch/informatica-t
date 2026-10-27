"""Modelos de dominio del Router (plano de datos). Sin HTTP ni almacenamiento."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ForwardingStatus(str, Enum):
    DELIVERED = "DELIVERED"
    UNREACHABLE = "UNREACHABLE"


@dataclass(frozen=True)
class Packet:
    packet_id: str
    src: str
    dst: str
    metric: str = "delay"
    payload: Optional[str] = None


@dataclass(frozen=True)
class RouteInfo:
    """Ruta tal como la decidió el Controller (el Router no la calcula)."""

    path: List[str]
    total_cost: float
    topology_version: int


@dataclass(frozen=True)
class HopRecord:
    hop: int
    from_node: str
    to_node: str
    status: str = "FORWARDED"


@dataclass(frozen=True)
class ResultWarning:
    code: str
    message: str


@dataclass(frozen=True)
class ForwardingResult:
    packet_id: str
    src: str
    dst: str
    metric: str
    status: ForwardingStatus
    route: Optional[RouteInfo]
    trace: List[HopRecord]
    reason: Optional[str]
    timestamp: str
    log_persisted: bool = False
    warnings: List[ResultWarning] = field(default_factory=list)

    def to_log_record(self) -> Dict[str, Any]:
        """Lo que se persiste: todo EXCEPTO log_persisted y warnings (04 §2.3)."""
        return {
            "packet_id": self.packet_id,
            "status": self.status.value,
            "src": self.src,
            "dst": self.dst,
            "metric": self.metric,
            "route": None
            if self.route is None
            else {
                "path": list(self.route.path),
                "total_cost": self.route.total_cost,
                "topology_version": self.route.topology_version,
            },
            "trace": [
                {"hop": h.hop, "from_node": h.from_node, "to_node": h.to_node, "status": h.status} for h in self.trace
            ],
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


__all__ = ["ForwardingStatus", "Packet", "RouteInfo", "HopRecord", "ResultWarning", "ForwardingResult"]
