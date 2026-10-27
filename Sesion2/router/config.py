"""Configuración del Router por variables de entorno (NFR-05, 01 §8)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_LOG_FILE = BASE_DIR / "data" / "forwarding_log.jsonl"


@dataclass(frozen=True)
class RouterSettings:
    port: int
    controller_url: str
    controller_timeout_s: float
    forwarding_log_file: str


def load_settings() -> RouterSettings:
    return RouterSettings(
        port=int(os.getenv("ROUTER_PORT", "8001")),
        controller_url=os.getenv("CONTROLLER_URL", "http://localhost:8000"),
        controller_timeout_s=float(os.getenv("CONTROLLER_TIMEOUT_S", "2.0")),
        forwarding_log_file=os.getenv("FORWARDING_LOG_FILE", str(DEFAULT_LOG_FILE)),
    )
