"""TC-05 (el Router pide la ruta por HTTP) y TC-25 (respuestas inesperadas del Controller)."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from router.clients.http_controller_client import HttpControllerClient
from router.config import RouterSettings
from router.main import create_app
from tests.fakes import FakeForwardingLogDAO
from tests.helpers import RecordingTransport, json_response, route_body

SETTINGS = RouterSettings(port=0, controller_url="http://controller.test", controller_timeout_s=1.0, forwarding_log_file="unused")


def router_with(transport, log_dao=None):
    client = HttpControllerClient(SETTINGS.controller_url, SETTINGS.controller_timeout_s, transport=transport)
    log_dao = log_dao or FakeForwardingLogDAO()
    return TestClient(create_app(SETTINGS, route_provider=client, log_dao=log_dao)), log_dao


@pytest.mark.mandatory
def test_tc05_router_obtains_route_via_http_instead_of_calculating():
    # El stub devuelve una ruta "rara" a propósito: si el Router calculara su propia ruta, no coincidiría.
    transport = RecordingTransport(lambda request: json_response(200, route_body(["A", "C", "E", "D"], [1, 1, 1], version=7)))
    client, _ = router_with(transport)
    response = client.post("/packets", json={"packet_id": "pkt-1", "src": "A", "dst": "D", "metric": "delay"})

    assert response.status_code == 200
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.method == "GET" and request.url.path == "/route"
    assert dict(request.url.params) == {"src": "A", "dst": "D", "metric": "delay"}
    body = response.json()
    assert body["route"] == {"path": ["A", "C", "E", "D"], "total_cost": 3.0, "topology_version": 7}
    assert [(h["from_node"], h["to_node"]) for h in body["trace"]] == [("A", "C"), ("C", "E"), ("E", "D")]


def raw(status, content: bytes):
    return lambda request: httpx.Response(status, content=content)


def err(status, code, details=None):
    return lambda request: json_response(status, {"error": {"code": code, "message": "x", "details": details or {}}})


def good_body_with(**changes):
    body = route_body(["A", "B", "D"], [10, 10])
    body.update(changes)
    return lambda request: json_response(200, body)


CASES = {
    "a_200_no_json": (raw(200, b"<html>oops</html>"), 502, "CONTROLLER_BAD_RESPONSE", "invalid_json"),
    "b_200_sin_path": (lambda r: json_response(200, {"src": "A", "dst": "D", "metric": "delay"}), 502, "CONTROLLER_BAD_RESPONSE", "schema_mismatch"),
    "c_200_path_final_distinto": (good_body_with(path=["A", "B", "C"]), 502, "CONTROLLER_BAD_RESPONSE", "path_dst_mismatch"),
    "d_200_hop_costs_incoherentes": (good_body_with(hop_costs=[10]), 502, "CONTROLLER_BAD_RESPONSE", "hop_costs_mismatch"),
    "e_404_codigo_desconocido": (err(404, "FOO"), 502, "CONTROLLER_BAD_RESPONSE", "unexpected_error_code"),
    "f_503_topology_unavailable": (err(503, "TOPOLOGY_UNAVAILABLE"), 503, "CONTROLLER_UNAVAILABLE", None),
    "g_500": (raw(500, b"Internal Server Error"), 503, "CONTROLLER_UNAVAILABLE", None),
    "h_409_inesperado": (err(409, "LINK_ALREADY_FAILED"), 502, "CONTROLLER_BAD_RESPONSE", "unexpected_status"),
    "i_400_invalid_parameter": (err(400, "INVALID_PARAMETER", {"field": "src"}), 400, "INVALID_PARAMETER", None),
    "extra_200_version_cero": (good_body_with(topology_version=0), 502, "CONTROLLER_BAD_RESPONSE", "invalid_topology_version"),
    "extra_200_costo_negativo": (good_body_with(hop_costs=[10, -1]), 502, "CONTROLLER_BAD_RESPONSE", "negative_cost"),
    "extra_200_nodos_repetidos": (lambda r: json_response(200, route_body(["A", "B", "A", "D"], [1, 1, 1])), 502, "CONTROLLER_BAD_RESPONSE", "path_repeated_nodes"),
    "extra_302_redireccion": (raw(302, b""), 502, "CONTROLLER_BAD_RESPONSE", "unexpected_status"),
}


@pytest.mark.recommended
@pytest.mark.parametrize("case", list(CASES))
def test_tc25_unexpected_controller_responses_are_classified(case):
    responder, status, code, reason = CASES[case]
    client, log_dao = router_with(httpx.MockTransport(responder))
    response = client.post("/packets", json={"packet_id": "pkt-x", "src": "A", "dst": "D"})

    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"} and body["error"]["code"] == code
    details = body["error"]["details"]
    if reason:
        assert details["reason"] == reason
    if case == "f_503_topology_unavailable":
        assert details == {"upstream_status": 503, "upstream_code": "TOPOLOGY_UNAVAILABLE"}
    if case == "g_500":
        assert details["upstream_status"] == 500
    if case == "i_400_invalid_parameter":
        assert details["source"] == "controller"
    assert log_dao.saved == []  # ningún error escribe en el log
    assert client.get("/health").status_code == 200  # el Router sigue vivo


@pytest.mark.recommended
@pytest.mark.parametrize(
    "network_error, expected_code",
    [
        (httpx.ConnectError("refused"), "CONTROLLER_UNAVAILABLE"),    # Linux: puerto cerrado
        (httpx.ConnectTimeout("no SYN-ACK"), "CONTROLLER_UNAVAILABLE"),  # Windows: puerto cerrado
        (httpx.ReadTimeout("slow"), "CONTROLLER_TIMEOUT"),            # conectó pero no respondió
    ],
    ids=["connect_error", "connect_timeout", "read_timeout"],
)
def test_tc25_network_failures_are_classified(network_error, expected_code):
    def raise_error(request):
        raise network_error

    client, log_dao = router_with(httpx.MockTransport(raise_error))
    response = client.post("/packets", json={"packet_id": "p", "src": "A", "dst": "D"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == expected_code
    assert log_dao.saved == []


@pytest.mark.recommended
def test_tc25_route_not_found_and_node_not_found_are_translated():
    client, log_dao = router_with(httpx.MockTransport(err(404, "ROUTE_NOT_FOUND")))
    body = client.post("/packets", json={"packet_id": "p", "src": "A", "dst": "F"}).json()
    assert body["status"] == "UNREACHABLE" and len(log_dao.saved) == 1

    client, log_dao = router_with(httpx.MockTransport(err(404, "NODE_NOT_FOUND", {"node": "Z"})))
    response = client.post("/packets", json={"packet_id": "p", "src": "A", "dst": "Z"})
    assert response.status_code == 404 and response.json()["error"]["details"] == {"node": "Z"}
    assert log_dao.saved == []
