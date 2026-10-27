from __future__ import annotations

from dataclasses import dataclass

from controller.models.link import Link


@dataclass(frozen=True)
class LinkChange:
    """Resultado de fail_link/restore_link: el enlace nuevo y la versión que creó (G5)."""

    link: Link
    topology_version: int
