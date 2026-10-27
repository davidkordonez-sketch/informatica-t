"""Pruebas unitarias de servicios del Controller: TC-01, TC-02, TC-03, TC-04, TC-08, TC-10.

Todas usan FakeTopologyDAO en memoria: sin HTTP ni archivos.
"""
from __future__ import annotations

import math

import pytest

from controller.exceptions import InvalidLinkMetricsError, NodeNotFoundError, RouteNotFoundError
from controller.models import Link, Metric
from controller.services.link_cost_calculator import LinkCostCalculator
from controller.services.routing_service import RoutingService
from controller.services.topology_service import TopologyService
from tests.fakes import FakeTopologyDAO


def build_services(dao: FakeTopologyDAO = None):
    dao = dao or FakeTopologyDAO()
    topology_service = TopologyService(dao, LinkCostCalculator())
    return dao, topology_service, RoutingService(topology_service)


@pytest.mark.mandatory
def test_tc01_dijkstra_chooses_minimum_cost_path():
    _, _, routing = build_services()
    route = routing.find_route("A", "D", Metric.DELAY)
    assert route.path == ["A", "B", "D"]
    assert route.total_cost == 20
    assert route.hop_costs == [10, 10]
    assert route.topology_version == 1

    same = routing.find_route("A", "A", Metric.DELAY)  # A-08
    assert same.path == ["A"] and same.total_cost == 0 and same.hop_costs == []


@pytest.mark.mandatory
@pytest.mark.parametrize(
    "metric, expected_path, expected_cost",
    [
        (Metric.DELAY, ["A", "B", "D"], 20.0),
        (Metric.BANDWIDTH, ["A", "C", "D"], 0.02),
        (Metric.LOSS, ["A", "B", "D"], 2 * -math.log(1 - 0.01)),
    ],
)
def test_tc02_all_three_metrics_supported(metric, expected_path, expected_cost):
    _, _, routing = build_services()
    route = routing.find_route("A", "D", metric)
    assert route.path == expected_path
    assert route.total_cost == pytest.approx(expected_cost, abs=1e-4)


@pytest.mark.mandatory
def test_tc03_failed_link_excluded_from_routes():
    _, topology_service, routing = build_services()
    change = topology_service.fail_link("B", "D")
    assert change.topology_version == 2

    route = routing.find_route("A", "D", Metric.DELAY)
    assert route.path == ["A", "C", "D"]
    assert route.total_cost == 25
    assert ("B", "D") not in list(zip(route.path, route.path[1:]))
    assert route.topology_version == 2


@pytest.mark.mandatory
def test_tc04_restoring_link_updates_routes():
    _, topology_service, routing = build_services()
    topology_service.fail_link("B", "D")
    change = topology_service.restore_link("D", "B")  # el orden no importa (A-01)
    assert change.topology_version == 3

    route = routing.find_route("A", "D", Metric.DELAY)
    assert route.path == ["A", "B", "D"]
    assert route.total_cost == 20
    assert route.topology_version == 3


@pytest.mark.mandatory
def test_tc08_routing_service_with_fake_topology_dao_without_http_or_files():
    dao, _, routing = build_services(FakeTopologyDAO())
    first = routing.find_route("A", "D", Metric.DELAY)
    second = routing.find_route("A", "E", Metric.DELAY)
    assert first.path == ["A", "B", "D"]
    assert second.path == ["A", "B", "D", "E"]
    assert dao.load_calls == 1  # el servicio usó el DAO inyectado, una sola carga

    with pytest.raises(NodeNotFoundError):
        routing.find_route("A", "Z", Metric.DELAY)
    with pytest.raises(RouteNotFoundError):
        routing.find_route("A", "F", Metric.DELAY)


@pytest.mark.recommended
def test_tc10_link_cost_calculator():
    calc = LinkCostCalculator()

    def link(d=10.0, b=100.0, p=0.0):
        return Link("X", "Y", d, b, p)

    assert calc.compute_cost(link(d=10), Metric.DELAY) == 10
    assert calc.compute_cost(link(b=100), Metric.BANDWIDTH) == pytest.approx(0.01)
    assert calc.compute_cost(link(p=0.5), Metric.LOSS) == pytest.approx(0.6931, abs=1e-4)
    assert calc.compute_cost(link(p=0.0), Metric.LOSS) == 0
    assert calc.is_usable(link(p=1.0)) is False
    assert calc.is_usable(link(p=0.99)) is True
    for bad in (link(b=0), link(b=-5), link(p=1.5), link(p=-0.1), link(d=-1)):
        with pytest.raises(InvalidLinkMetricsError):
            calc.compute_cost(bad, Metric.DELAY)
    for metric in Metric:
        assert calc.compute_cost(link(d=3, b=7, p=0.2), metric) >= 0


@pytest.mark.recommended
def test_tc10_link_with_p_equal_1_is_excluded_from_graph_for_every_metric():
    from controller.models import Topology

    topology = Topology(
        nodes=("A", "B", "C"),
        links=(Link("A", "B", 1, 1000, 1.0), Link("A", "C", 5, 10, 0.1), Link("C", "B", 5, 10, 0.1)),
    )
    _, _, routing = build_services(FakeTopologyDAO(topology))
    for metric in Metric:
        assert routing.find_route("A", "B", metric).path == ["A", "C", "B"]
