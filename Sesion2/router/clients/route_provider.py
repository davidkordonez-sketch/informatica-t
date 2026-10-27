"""Interfaz RouteProvider: de dónde obtiene el Router las rutas (siempre del Controller)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from router.models import RouteInfo


class RouteProvider(ABC):
    @abstractmethod
    def get_route(self, src: str, dst: str, metric: str) -> RouteInfo:
        """Devuelve la ruta o lanza RouteNotFoundError, NodeNotFoundError, InvalidParameterError,
        ControllerUnavailableError, ControllerTimeoutError o ControllerBadResponseError."""
