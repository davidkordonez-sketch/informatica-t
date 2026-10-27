"""TC-21: sustitución de TopologyDAO (prueba de contrato fake vs JSON)."""
from __future__ import annotations

from pathlib import Path

import pytest

from controller.dao.json_topology_dao import JsonTopologyDAO
from controller.exceptions import TopologyUnavailableError
from controller.models import LinkStatus, Metric
from controller.services.link_cost_calculator import LinkCostCalculator
from controller.services.routing_service import RoutingService
from controller.services.topology_service import TopologyService
from tests.fakes import FakeTopologyDAO

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "topology.json"

DAO_FACTORIES = {
    "fake": lambda: FakeTopologyDAO(),
    "json": lambda: JsonTopologyDAO(str(FIXTURE)),
}


def run_scenario(dao):
    topology_service = TopologyService(dao, LinkCostCalculator())
    routing = RoutingService(topology_service)
    results = []
    for metric in Metric:
        for src, dst in (("A", "D"), ("A", "E"), ("C", "B"), ("E", "E")):
            route = routing.find_route(src, dst, metric)
            results.append((metric, route.path, round(route.total_cost, 12), route.topology_version))
    topology_service.fail_link("B", "D")
    results.append(routing.find_route("A", "D", Metric.DELAY).path)
    topology_service.restore_link("B", "D")
    results.append(routing.find_route("A", "D", Metric.DELAY).path)
    return results


@pytest.mark.extension
def test_tc21_topology_services_behave_identically_with_fake_and_json_dao():
    assert run_scenario(DAO_FACTORIES["fake"]()) == run_scenario(DAO_FACTORIES["json"]())


@pytest.mark.extension
@pytest.mark.parametrize("name", list(DAO_FACTORIES))
def test_tc21_topology_dao_contract(name):
    topology = DAO_FACTORIES[name]().load_topology()
    assert topology.version == 1
    assert list(topology.nodes) == ["A", "B", "C", "D", "E", "F"]
    assert len(topology.links) == 5
    assert all(link.status == LinkStatus.ACTIVE for link in topology.links)
    assert topology.get_link("D", "B").delay_ms == 10


@pytest.mark.extension
def test_tc21_json_dao_reports_missing_file_as_topology_unavailable(tmp_path):
    with pytest.raises(TopologyUnavailableError):
        JsonTopologyDAO(str(tmp_path / "missing.json")).load_topology()
