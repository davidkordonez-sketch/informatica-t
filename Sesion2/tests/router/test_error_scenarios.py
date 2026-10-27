"""TC-07: Controller caído, destino inalcanzable y nodo inexistente (Router + Controller reales en proceso)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from controller.main import create_app as create_controller_app
from router.clients.http_controller_client import HttpControllerClient
from router.config import RouterSettings
from router.main import create_app as create_router_app
from tests.fakes import FakeForwardingLogDAO, FakeTopologyDAO
from tests.helpers import bridge_to, free_port


def router_connected_to_real_controller():
    controller = TestClient(create_controller_app(topology_dao=FakeTopologyDAO()))
    settings = RouterSettings(0, "http://controller.test", 2.0, "unused")
    provider = HttpControllerClient(settings.controller_url, settings.controller_timeout_s, transport=bridge_to(controller))
    log_dao = FakeForwardingLogDAO()
    return TestClient(create_router_app(settings, route_provider=provider, log_dao=log_dao)), log_dao


@pytest.mark.mandatory
def test_tc07a_controller_down_returns_503_and_router_stays_alive():
    settings = RouterSettings(0, f"http://127.0.0.1:{free_port()}", 1.0, "unused")  # nadie escucha ahí
    log_dao = FakeForwardingLogDAO()
    client = TestClient(create_router_app(settings, log_dao=log_dao))
    response = client.post("/packets", json={"packet_id": "pkt-1", "src": "A", "dst": "D"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CONTROLLER_UNAVAILABLE"
    assert client.get("/health").json() == {"status": "ok", "service": "router"}
    assert log_dao.saved == []


@pytest.mark.mandatory
def test_tc07b_isolated_destination_is_unreachable():
    client, log_dao = router_connected_to_real_controller()
    response = client.post("/packets", json={"packet_id": "pkt-2", "src": "A", "dst": "F"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNREACHABLE" and body["trace"] == [] and body["reason"] == "ROUTE_NOT_FOUND"
    assert body["route"] is None and body["log_persisted"] is True
    assert len(log_dao.saved) == 1


@pytest.mark.mandatory
def test_tc07c_unknown_node_propagates_404():
    client, log_dao = router_connected_to_real_controller()
    response = client.post("/packets", json={"packet_id": "pkt-3", "src": "A", "dst": "Z"})
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NODE_NOT_FOUND", "message": "Node 'Z' does not exist", "details": {"node": "Z"}}
    }
    assert log_dao.saved == []


@pytest.mark.mandatory
def test_tc07_router_validates_request_format_without_calling_controller():
    client, log_dao = router_connected_to_real_controller()
    for body in ({"src": "A", "dst": "D"}, {"packet_id": "p", "src": "", "dst": "D"}, {"packet_id": "p", "src": "A", "dst": "D", "metric": "foo"}):
        response = client.post("/packets", json=body)
        assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_PARAMETER"
    assert log_dao.saved == []
