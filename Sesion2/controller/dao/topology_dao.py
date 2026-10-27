"""Interfaz TopologyDAO (patrón DAO). Los servicios dependen SOLO de esta abstracción (R4)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from controller.models import Topology


class TopologyDAO(ABC):
    @abstractmethod
    def load_topology(self) -> Topology:
        """Lee y parsea la topología. Devuelve Topology con version = 1.

        Lanza TopologyUnavailableError (no se puede leer / JSON corrupto) o
        InvalidTopologyError (estructura del documento incorrecta).
        NO valida reglas semánticas: eso lo hace TopologyService (A-11).
        """
