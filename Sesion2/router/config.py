"""Configuración del Router por variables de entorno (NFR-05, 01 §8)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_LOG_FILE = BASE_DIR / "data" / "forwarding_log.jsonl"
# Orígenes web que pueden llamar al Router desde el navegador (la consola visual del Controller).
DEFAULT_CORS_ORIGINS = ("http://localhost:8000", "http://127.0.0.1:8000")


@dataclass(frozen=True)
class RouterSettings:
    port: int
    controller_url: str
    controller_timeout_s: float
    forwarding_log_file: str
    cors_origins: Tuple[str, ...] = DEFAULT_CORS_ORIGINS


def load_settings() -> RouterSettings:
    origins = os.getenv("ROUTER_CORS_ORIGINS")
    return RouterSettings(
        port=int(os.getenv("ROUTER_PORT", "8001")),
        controller_url=os.getenv("CONTROLLER_URL", "http://localhost:8000"),
        controller_timeout_s=float(os.getenv("CONTROLLER_TIMEOUT_S", "2.0")),
        forwarding_log_file=os.getenv("FORWARDING_LOG_FILE", str(DEFAULT_LOG_FILE)),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()) if origins else DEFAULT_CORS_ORIGINS,
    )
