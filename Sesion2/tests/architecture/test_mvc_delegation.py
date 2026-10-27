"""TC-23: los controladores HTTP solo delegan en el servicio inyectado (verificación de comportamiento).

Se reemplazan los servicios por ESPÍAS que devuelven valores fijos "imposibles". Si un
controlador calculara rutas o simulara saltos por su cuenta, la respuesta no coincidiría.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from controller.controllers.dependencies import get_routing_service, get_topology_service
from controller.exceptions import LinkAlreadyFailedError, NodeNotFoundError
from controller.main import create_app as create_controller_app
from controller.models import Link, LinkChange, LinkStatus, Metric, Route
from router.controllers.dependencies import get_forwarding_service
from router.config import RouterSettings
from router.main import create_app as create_router_app
from router.models import ForwardingResult, ForwardingStatus, HopRecord, Packet, RouteInfo
from tests.fakes import FakeForwardingLogDAO, FakeRouteProvider, FakeTopologyDAO


class SpyRoutingService:
    def __init__(self, result=None, error=None):
        self.calls, self._result, self._error = [], result, error

    def find_route(self, src, dst, metric):
        self.calls.append((src, dst, metric))
        if self._error:
            raise self._error
        return self._result


class SpyTopologyService:
    def __init__(self, error=None):
        self.calls, self._error = [], error

    def fail_link(self, node_a, node_b):
        self.calls.append(("fail", node_a, node_b))
        if self._error:
            raise self._error
        return LinkChange(Link(node_a, node_b, 1, 1, 0, LinkStatus.FAILED), 42)


class SpyForwardingService:
    def __init__(self, result):
        self.calls, self._result = [], result

    def forward_packet(self, packet):
        self.calls.append(packet)
        return self._result


@pytest.mark.recommended
def test_tc23_route_controller_only_delegates():
    canned = Route("A", "D", Metric.LOSS, ["A", "X", "Y", "D"], 99.5, [1.0, 2.0, 96.5], 42)
    spy = SpyRoutingService(result=canned)
    app = create_controller_app(topology_dao=FakeTopologyDAO())
    app.dependency_overrides[get_routing_service] = lambda: spy
    response = TestClient(app).get("/route", params={"src": "A", "dst": "D", "metric": "loss"})
    assert spy.calls == [("A", "D", Metric.LOSS)]  # una llamada, con la métrica ya convertida
    assert response.json() == {
        "src": "A", "dst": "D", "metric": "loss", "path": ["A", "X", "Y", "D"],
        "hop_costs": [1.0, 2.0, 96.5], "total_cost": 99.5, "topology_version": 42,
    }

    app.dependency_overrides[get_routing_service] = lambda: SpyRoutingService(error=NodeNotFoundError("x", {"node": "Q"}))
    response = TestClient(app).get("/route", params={"src": "A", "dst": "Q"})
    assert response.status_code == 404 and response.json()["error"]["code"] == "NODE_NOT_FOUND"


@pytest.mark.recommended
def test_tc23_link_controller_only_delegates():
    spy = SpyTopologyService()
    app = create_controller_app(topology_dao=FakeTopologyDAO())
    app.dependency_overrides[get_topology_service] = lambda: spy
    response = TestClient(app).post("/links/fail", json={"node_a": "P", "node_b": "Q"})
    assert spy.calls == [("fail", "P", "Q")]
    assert response.json() == {"link": {"node_a": "P", "node_b": "Q", "status": "failed"}, "topology_version": 42}

    app.dependency_overrides[get_topology_service] = lambda: SpyTopologyService(error=LinkAlreadyFailedError("x"))
    assert TestClient(app).post("/links/fail", json={"node_a": "P", "node_b": "Q"}).status_code == 409


@pytest.mark.recommended
def test_tc23_packet_controller_only_delegates():
    canned = ForwardingResult(
        packet_id="pkt-9", src="A", dst="D", metric="bandwidth", status=ForwardingStatus.DELIVERED,
        route=RouteInfo(["A", "Q", "D"], 7.0, 42), trace=[HopRecord(1, "A", "Q"), HopRecord(2, "Q", "D")],
        reason=None, timestamp="2000-01-01T00:00:00Z", log_persisted=True, warnings=[],
    )
    spy = SpyForwardingService(canned)
    settings = RouterSettings(0, "http://unused", 1.0, "unused")
    app = create_router_app(settings, route_provider=FakeRouteProvider(), log_dao=FakeForwardingLogDAO())
    app.dependency_overrides[get_forwarding_service] = lambda: spy
    response = TestClient(app).post("/packets", json={"packet_id": "pkt-9", "src": "A", "dst": "D", "metric": "bandwidth"})
    assert spy.calls == [Packet("pkt-9", "A", "D", "bandwidth", None)]
    body = response.json()
    assert body["route"] == {"path": ["A", "Q", "D"], "total_cost": 7.0, "topology_version": 42}
    assert [(h["from_node"], h["to_node"]) for h in body["trace"]] == [("A", "Q"), ("Q", "D")]
    assert body["timestamp"] == "2000-01-01T00:00:00Z"
