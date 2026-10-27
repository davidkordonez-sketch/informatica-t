from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class LinkStatus(str, Enum):
    ACTIVE = "active"
    FAILED = "failed"


@dataclass(frozen=True)
class Link:
    """Enlace bidireccional y simétrico (A-01). Inmutable (A-14)."""

    node_a: str
    node_b: str
    delay_ms: float
    bandwidth_mbps: float
    loss_prob: float
    status: LinkStatus = LinkStatus.ACTIVE

    def key(self) -> frozenset:
        """Identificador del enlace sin importar el orden de los nodos."""
        return frozenset((self.node_a, self.node_b))

    def with_status(self, status: LinkStatus) -> "Link":
        """Devuelve un enlace NUEVO con otro estado; el original no cambia."""
        return replace(self, status=status)
