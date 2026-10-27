"""Configuración del Controller por variables de entorno (NFR-05, 01 §8)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TOPOLOGY_FILE = BASE_DIR / "data" / "topology.json"


@dataclass(frozen=True)
class ControllerSettings:
    port: int
    topology_file: str


def load_settings() -> ControllerSettings:
    return ControllerSettings(
        port=int(os.getenv("CONTROLLER_PORT", "8000")),
        topology_file=os.getenv("TOPOLOGY_FILE", str(DEFAULT_TOPOLOGY_FILE)),
    )
