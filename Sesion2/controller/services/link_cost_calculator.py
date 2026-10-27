"""Costos de enlace (FR-04, 01 §3.2). Sin estado."""
from __future__ import annotations

import math

from controller.exceptions import InvalidLinkMetricsError
from controller.models import Link, Metric


class LinkCostCalculator:
    def validate(self, link: Link) -> None:
        """Comprueba los dominios de 01 §3.1. Lanza INVALID_LINK_METRICS."""
        d, b, p = link.delay_ms, link.bandwidth_mbps, link.loss_prob
        details = {"node_a": link.node_a, "node_b": link.node_b}
        if not all(math.isfinite(value) for value in (d, b, p)):
            raise InvalidLinkMetricsError("Link attributes must be finite numbers", details)
        if d < 0:
            raise InvalidLinkMetricsError("delay_ms must be >= 0", details)
        if b <= 0:
            raise InvalidLinkMetricsError("bandwidth_mbps must be > 0", details)
        if p < 0 or p > 1:
            raise InvalidLinkMetricsError("loss_prob must be in [0, 1]", details)

    def is_usable(self, link: Link) -> bool:
        """p = 1 es válido en el archivo pero inutilizable para todas las métricas (A-05)."""
        return link.loss_prob < 1

    def compute_cost(self, link: Link, metric: Metric) -> float:
        """Costo >= 0 para Dijkstra: d, 1/b o -ln(1-p)."""
        self.validate(link)
        if metric == Metric.DELAY:
            return float(link.delay_ms)
        if metric == Metric.BANDWIDTH:
            return 1.0 / link.bandwidth_mbps
        if metric == Metric.LOSS:
            if not self.is_usable(link):
                raise InvalidLinkMetricsError(
                    "Link with loss_prob = 1 is unusable", {"node_a": link.node_a, "node_b": link.node_b}
                )
            cost = -math.log1p(-link.loss_prob)
            return cost if cost > 0 else 0.0  # evita -0.0 cuando p = 0
        raise ValueError(f"Unsupported metric: {metric}")
