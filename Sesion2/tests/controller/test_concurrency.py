"""TC-20: consistencia ruta-versión bajo concurrencia (NFR-12, 02 §7.1)."""
from __future__ import annotations

import threading
import time

import pytest

from controller.exceptions import LinkAlreadyFailedError
from controller.models import Metric
from controller.services.link_cost_calculator import LinkCostCalculator
from controller.services.routing_service import RoutingService
from controller.services.topology_service import TopologyService
from tests.fakes import FakeTopologyDAO


class SlowTopologyService(TopologyService):
    """Pausa 1 ms al construir el grafo para forzar intercalado entre hilos."""

    def build_weighted_graph(self, snapshot, metric):
        time.sleep(0.001)
        return super().build_weighted_graph(snapshot, metric)


@pytest.mark.recommended
def test_tc20a_route_and_version_always_come_from_the_same_snapshot():
    topology_service = SlowTopologyService(FakeTopologyDAO(), LinkCostCalculator())
    routing = RoutingService(topology_service)
    readers, queries_per_reader, writes = 8, 200, 100
    observations = [[] for _ in range(readers)]
    errors = []
    start = threading.Barrier(readers + 1)

    def reader(index):
        start.wait()
        try:
            for _ in range(queries_per_reader):
                route = routing.find_route("A", "D", Metric.DELAY)
                observations[index].append((route.topology_version, route.path, route.total_cost))
        except Exception as error:  # pragma: no cover - solo si falla
            errors.append(error)

    def writer():
        start.wait()
        try:
            for step in range(writes):
                if step % 2 == 0:
                    topology_service.fail_link("B", "D")
                else:
                    topology_service.restore_link("B", "D")
                time.sleep(0.002)
        except Exception as error:  # pragma: no cover
            errors.append(error)

    threads = [threading.Thread(target=reader, args=(i,)) for i in range(readers)] + [threading.Thread(target=writer)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    versions_seen = set()
    for per_thread in observations:
        assert len(per_thread) == queries_per_reader
        previous = 0
        for version, path, cost in per_thread:
            if version % 2 == 1:  # versiones impares: B-D activo
                assert (path, cost) == (["A", "B", "D"], 20.0), f"incoherente en v{version}"
            else:  # versiones pares: B-D fallado
                assert (path, cost) == (["A", "C", "D"], 25.0), f"incoherente en v{version}"
            assert version >= previous  # G4: nunca retrocede
            previous = version
            versions_seen.add(version)
    assert topology_service.peek_snapshot().version == 1 + writes  # G3: sin actualizaciones perdidas
    assert len(versions_seen) > 2  # hubo intercalado real entre lecturas y escrituras


@pytest.mark.recommended
def test_tc20b_simultaneous_fail_on_same_link_produces_one_success_and_one_conflict():
    topology_service = TopologyService(FakeTopologyDAO(), LinkCostCalculator())
    for attempt in range(50):
        version_before = topology_service.get_snapshot().version
        barrier = threading.Barrier(2)
        outcomes = []

        def try_fail():
            barrier.wait()
            try:
                outcomes.append(topology_service.fail_link("B", "D"))
            except LinkAlreadyFailedError as error:
                outcomes.append(error)

        threads = [threading.Thread(target=try_fail) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        successes = [o for o in outcomes if not isinstance(o, Exception)]
        conflicts = [o for o in outcomes if isinstance(o, LinkAlreadyFailedError)]
        assert len(successes) == 1 and len(conflicts) == 1, f"intento {attempt}"
        assert successes[0].topology_version == version_before + 1
        assert topology_service.get_snapshot().version == version_before + 1
        topology_service.restore_link("B", "D")
