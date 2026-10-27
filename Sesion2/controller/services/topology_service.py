"""TopologyService: único dueño del estado mutable del Controller (02 §7.1, A-14).

Modelo de concurrencia (copy-on-write):
- ``_current`` es una referencia a una Topology INMUTABLE.
- Las escrituras (carga inicial, fail_link, restore_link) se serializan con ``_write_lock``
  y publican una instantánea nueva (version + 1). Nunca modifican la anterior.
- Las lecturas toman la referencia una vez (``get_snapshot``) y trabajan sobre ella sin
  mantener el lock, por eso la ruta y su versión siempre salen del mismo estado (G1).
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

import networkx as nx

from controller.dao.topology_dao import TopologyDAO
from controller.exceptions import (
    InvalidLinkMetricsError,
    InvalidTopologyError,
    LinkAlreadyActiveError,
    LinkAlreadyFailedError,
    LinkNotFoundError,
    TopologyUnavailableError,
)
from controller.models import LinkChange, LinkStatus, Metric, Topology
from controller.services.link_cost_calculator import LinkCostCalculator

logger = logging.getLogger("controller")


class TopologyService:
    def __init__(self, dao: TopologyDAO, cost_calculator: LinkCostCalculator) -> None:
        self._dao = dao
        self._cost_calculator = cost_calculator
        self._current: Optional[Topology] = None
        self._write_lock = threading.Lock()

    # ------------------------------------------------------------------ carga
    def ensure_loaded(self) -> None:
        """Carga diferida con double-checked locking (A-13). Si falla -> degraded."""
        if self._current is not None:
            return
        with self._write_lock:
            if self._current is not None:  # otro hilo la cargó mientras esperábamos
                return
            try:
                topology = self._dao.load_topology()
                self.validate(topology)
            except TopologyUnavailableError:
                raise
            except (InvalidTopologyError, InvalidLinkMetricsError) as error:
                logger.warning("Invalid topology: %s", error.message)
                raise TopologyUnavailableError(
                    "Topology is invalid", {"reason": error.code, **error.details}
                ) from error
            except Exception as error:  # el DAO no debería lanzar otra cosa; por robustez
                logger.exception("Unexpected error loading topology")
                raise TopologyUnavailableError("Topology could not be loaded") from error
            self._current = Topology(nodes=topology.nodes, links=topology.links, version=1)

    def get_snapshot(self) -> Topology:
        """Instantánea vigente; intenta cargar si aún no hay (lanza TOPOLOGY_UNAVAILABLE)."""
        self.ensure_loaded()
        with self._write_lock:
            snapshot = self._current
        if snapshot is None:  # pragma: no cover - ensure_loaded ya lo garantiza
            raise TopologyUnavailableError("Topology is not loaded")
        return snapshot

    def peek_snapshot(self) -> Optional[Topology]:
        """Instantánea vigente o None, SIN intentar cargar (lo usa /health)."""
        with self._write_lock:
            return self._current

    # ------------------------------------------------------------- validación
    def validate(self, topology: Topology) -> None:
        """Reglas semánticas de 01 §3.1 (A-11)."""
        seen = set()
        for node in topology.nodes:
            if not node or not node.strip():
                raise InvalidTopologyError("Node ids must be non-empty")
            if node in seen:
                raise InvalidTopologyError("Duplicated node id", {"node": node})
            seen.add(node)
        link_keys = set()
        for link in topology.links:
            details = {"node_a": link.node_a, "node_b": link.node_b}
            if link.node_a not in seen or link.node_b not in seen:
                raise InvalidTopologyError("Link references a non-existent node", details)
            if link.node_a == link.node_b:
                raise InvalidTopologyError("Self-loops are not allowed", details)
            if link.key() in link_keys:
                raise InvalidTopologyError("Duplicated link", details)
            link_keys.add(link.key())
            self._cost_calculator.validate(link)

    # ------------------------------------------------- fallos / restablecimientos
    def fail_link(self, node_a: str, node_b: str) -> LinkChange:
        return self._change_link_status(node_a, node_b, LinkStatus.FAILED)

    def restore_link(self, node_a: str, node_b: str) -> LinkChange:
        return self._change_link_status(node_a, node_b, LinkStatus.ACTIVE)

    def _change_link_status(self, node_a: str, node_b: str, target: LinkStatus) -> LinkChange:
        self.ensure_loaded()
        with self._write_lock:  # escrituras serializadas: sin actualizaciones perdidas (G3)
            current = self._current
            if current is None:  # pragma: no cover
                raise TopologyUnavailableError("Topology is not loaded")
            link = current.get_link(node_a, node_b)
            details = {"node_a": node_a, "node_b": node_b}
            if link is None:
                raise LinkNotFoundError(f"Link {node_a}-{node_b} does not exist", details)
            if link.status == target:
                if target == LinkStatus.FAILED:
                    raise LinkAlreadyFailedError(f"Link {node_a}-{node_b} is already failed", details)
                raise LinkAlreadyActiveError(f"Link {node_a}-{node_b} is already active", details)
            new_snapshot = current.with_link_status(node_a, node_b, target)
            self._current = new_snapshot  # publicación atómica de la nueva instantánea
            return LinkChange(link=new_snapshot.get_link(node_a, node_b), topology_version=new_snapshot.version)

    # ----------------------------------------------------------------- grafo
    def build_weighted_graph(self, snapshot: Topology, metric: Metric) -> nx.Graph:
        """Función pura de la instantánea recibida (R8): no lee ``_current``."""
        graph = nx.Graph()
        graph.add_nodes_from(snapshot.nodes)
        for link in snapshot.links:
            if link.status != LinkStatus.ACTIVE or not self._cost_calculator.is_usable(link):
                continue  # enlaces fallados o con p = 1 no participan (AC-04.2, AC-06.2)
            graph.add_edge(link.node_a, link.node_b, weight=self._cost_calculator.compute_cost(link, metric))
        return graph
