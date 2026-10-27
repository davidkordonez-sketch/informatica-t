from __future__ import annotations

from enum import Enum


class Metric(str, Enum):
    """Criterio de costo de una consulta (A-02). Un solo criterio por consulta."""

    DELAY = "delay"
    BANDWIDTH = "bandwidth"
    LOSS = "loss"
