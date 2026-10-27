"""Dobles de prueba compartidos (06 §1). Todo en memoria: sin archivos ni red."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from controller.dao.topology_dao import TopologyDAO
from controller.exceptions import TopologyUnavailableError
from controller.models import Link, Topology
from router.clients.route_provider import RouteProvider
from router.dao.forwarding_log_dao import ForwardingLogDAO
from router.exceptions import PersistenceError
from router.models import ForwardingResult, RouteInfo


def reference_topology() -> Topology:
    """Topología de referencia de 06 §1, construida en memoria."""
    links = (
        Link("A", "B", 10, 10, 0.01),
        Link("B", "D", 10, 10, 0.01),
        Link("A", "C", 5, 100, 0.05),
        Link("C", "D", 20, 100, 0.05),
        Link("D", "E", 5, 100, 0.0),
    )
    return Topology(nodes=("A", "B", "C", "D", "E", "F"), links=links, version=1)


class FakeTopologyDAO(TopologyDAO):
    def __init__(self, topology: Optional[Topology] = None, error: Optional[Exception] = None) -> None:
        self._topology = topology or reference_topology()
        self._error = error
        self.load_calls = 0

    def load_topology(self) -> Topology:
        self.load_calls += 1
        if self._error is not None:
            raise self._error
        return self._topology


class UnavailableTopologyDAO(FakeTopologyDAO):
    def __init__(self) -> None:
        super().__init__(error=TopologyUnavailableError("fake: file missing"))


class FakeRouteProvider(RouteProvider):
    def __init__(self, route: Optional[RouteInfo] = None, error: Optional[Exception] = None) -> None:
        self._route = route or RouteInfo(path=["A", "B", "D"], total_cost=20.0, topology_version=1)
        self._error = error
        self.calls: List[tuple] = []

    def get_route(self, src: str, dst: str, metric: str) -> RouteInfo:
        self.calls.append((src, dst, metric))
        if self._error is not None:
            raise self._error
        return self._route


class FakeForwardingLogDAO(ForwardingLogDAO):
    def __init__(self) -> None:
        self.saved: List[ForwardingResult] = []
        self._lock = threading.Lock()

    def save(self, result: ForwardingResult) -> None:
        with self._lock:
            self.saved.append(result)

    def find_all(self) -> List[Dict[str, Any]]:
        return [result.to_log_record() for result in self.saved]


class FailingForwardingLogDAO(ForwardingLogDAO):
    def __init__(self, error: Optional[Exception] = None) -> None:
        self._error = error or PersistenceError("fake: disk full")
        self.save_calls = 0

    def save(self, result: ForwardingResult) -> None:
        self.save_calls += 1
        raise self._error

    def find_all(self) -> List[Dict[str, Any]]:
        return []
