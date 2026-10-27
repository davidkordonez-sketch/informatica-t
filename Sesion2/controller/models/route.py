from __future__ import annotations

from dataclasses import dataclass
from typing import List

from controller.models.metric import Metric


@dataclass(frozen=True)
class Route:
    """Ruta calculada sobre UNA instantánea; topology_version es la de esa instantánea (G1)."""

    src: str
    dst: str
    metric: Metric
    path: List[str]
    total_cost: float
    hop_costs: List[float]
    topology_version: int
