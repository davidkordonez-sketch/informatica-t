"""Interfaz ForwardingLogDAO (patrón DAO)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from router.models import ForwardingResult


class ForwardingLogDAO(ABC):
    @abstractmethod
    def save(self, result: ForwardingResult) -> None:
        """Persiste result.to_log_record(). Solo puede lanzar PersistenceError (A-16)."""

    @abstractmethod
    def find_all(self) -> List[Dict[str, Any]]:
        """Devuelve los registros válidos; omite fragmentos de escrituras parciales."""
