"""Pruebas de API del Controller: TC-11 y TC-17."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from controller.config import ControllerSettings
from controller.main import create_app
from tests.fakes import FakeTopologyDAO

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "topology.json"


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert isinstance(body["error"]["details"], dict)


@pytest.fixture
def client():
    return TestClient(create_app(topology_dao=FakeTopologyDAO()))


@pytest.mark.recommended
def test_tc11_controller_api_contract(client):
    # Respuestas 200 acordes con 04
    health = client.get("/health").json()
    assert health == {"status": "ok", "service": "controller", "topology_loaded": True, "topology_version": 1}
    route = client.get("/route", params={"src": "A", "dst": "D", "metric": "delay"}).json()
    assert route == {
        "src": "A", "dst": "D", "metric": "delay", "path": ["A", "B", "D"],
        "hop_costs": [10.0, 10.0], "total_cost": 20.0, "topology_version": 1,
    }
    assert client.get("/route", params={"src": "A", "dst": "D"}).json()["metric"] == "delay"  # por defecto
    topology = client.get("/topology").json()
    assert topology["topology_version"] == 1
    assert "F" in topology["nodes"]  # nodo aislado consultable (AC-02.3)
    assert len(topology["links"]) == 5 and topology["links"][0]["status"] == "active"

    # Errores
    assert_error(client.get("/route", params={"dst": "D"}), 400, "INVALID_PARAMETER")
    assert_error(client.get("/route", params={"src": "", "dst": "D"}), 400, "INVALID_PARAMETER")
    assert_error(client.get("/route", params={"src": "A", "dst": "D", "metric": "foo"}), 400, "INVALID_PARAMETER")
    not_found = client.get("/route", params={"src": "A", "dst": "Z"})
    assert_error(not_found, 404, "NODE_NOT_FOUND")
    assert not_found.json()["error"]["details"] == {"node": "Z"}
    assert_error(client.get("/route", params={"src": "A", "dst": "F"}), 404, "ROUTE_NOT_FOUND")
    assert_error(client.post("/links/fail", json={"node_a": "A", "node_b": "F"}), 404, "LINK_NOT_FOUND")
    assert_error(client.post("/links/fail", json={"node_a": "B"}), 400, "INVALID_PARAMETER")
    assert_error(client.post("/links/fail", json={"node_a": " ", "node_b": "D"}), 400, "INVALID_PARAMETER")

    first = client.post("/links/fail", json={"node_a": "B", "node_b": "D"})
    assert first.status_code == 200
    assert first.json() == {"link": {"node_a": "B", "node_b": "D", "status": "failed"}, "topology_version": 2}
    assert_error(client.post("/links/fail", json={"node_a": "D", "node_b": "B"}), 409, "LINK_ALREADY_FAILED")
    assert client.get("/health").json()["topology_version"] == 2  # el 409 no cambió la versión
    restored = client.post("/links/restore", json={"node_a": "B", "node_b": "D"})
    assert restored.json() == {"link": {"node_a": "B", "node_b": "D", "status": "active"}, "topology_version": 3}
    assert_error(client.post("/links/restore", json={"node_a": "B", "node_b": "D"}), 409, "LINK_ALREADY_ACTIVE")


def make_client(tmp_path: Path, content) -> TestClient:
    file_path = tmp_path / "topology.json"
    if content is not None:
        file_path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return TestClient(create_app(ControllerSettings(port=0, topology_file=str(file_path))))


def link(a, b, d=1, bw=10, p=0.0):
    return {"node_a": a, "node_b": b, "delay_ms": d, "bandwidth_mbps": bw, "loss_prob": p}


VALID_TOPOLOGIES = {
    "lineal": ({"nodes": ["A", "B", "C"], "links": [link("A", "B"), link("B", "C")]}, ("A", "C"), ["A", "B", "C"]),
    "anillo": (
        {"nodes": ["A", "B", "C", "D"], "links": [link("A", "B"), link("B", "C"), link("C", "D", d=5), link("D", "A")]},
        ("A", "C"),
        ["A", "B", "C"],
    ),
    "malla": (
        {
            "nodes": ["A", "B", "C", "D"],
            "links": [link("A", "B", d=3), link("A", "C", d=3), link("A", "D", d=9), link("B", "C"), link("B", "D", d=2), link("C", "D", d=4)],
        },
        ("A", "D"),
        ["A", "B", "D"],
    ),
    "nodo_aislado": ({"nodes": ["A", "B", "Z"], "links": [link("A", "B")]}, ("A", "B"), ["A", "B"]),
}


@pytest.mark.recommended
@pytest.mark.parametrize("name", list(VALID_TOPOLOGIES))
def test_tc17_valid_topologies_load_without_code_changes(tmp_path, name):
    document, (src, dst), expected_path = VALID_TOPOLOGIES[name]
    client = make_client(tmp_path, document)
    assert client.get("/health").json()["topology_loaded"] is True
    topology = client.get("/topology").json()
    assert topology["nodes"] == document["nodes"]
    assert len(topology["links"]) == len(document["links"])
    assert client.get("/route", params={"src": src, "dst": dst}).json()["path"] == expected_path


INVALID_TOPOLOGIES = {
    "archivo_inexistente": None,
    "json_corrupto": '{"nodes": ["A", "B"], "links": [',
    "nodo_inexistente": {"nodes": ["A", "B"], "links": [link("A", "X")]},
    "p_fuera_de_rango": {"nodes": ["A", "B"], "links": [link("A", "B", p=1.5)]},
    "ancho_de_banda_cero": {"nodes": ["A", "B"], "links": [link("A", "B", bw=0)]},
    "enlace_duplicado": {"nodes": ["A", "B"], "links": [link("A", "B"), link("B", "A")]},
    "lazo": {"nodes": ["A"], "links": [link("A", "A")]},
}


@pytest.mark.recommended
@pytest.mark.parametrize("name", list(INVALID_TOPOLOGIES))
def test_tc17_invalid_topology_keeps_process_alive_in_degraded_mode(tmp_path, name):
    client = make_client(tmp_path, INVALID_TOPOLOGIES[name])
    assert client.get("/health").json() == {
        "status": "degraded", "service": "controller", "topology_loaded": False, "topology_version": 0,
    }
    assert_error(client.get("/route", params={"src": "A", "dst": "B"}), 503, "TOPOLOGY_UNAVAILABLE")
    assert_error(client.get("/topology"), 503, "TOPOLOGY_UNAVAILABLE")
    assert_error(client.post("/links/fail", json={"node_a": "A", "node_b": "B"}), 503, "TOPOLOGY_UNAVAILABLE")
    assert client.get("/health").status_code == 200  # el proceso sigue respondiendo


@pytest.mark.recommended
def test_tc17_degraded_controller_retries_loading_on_next_request(tmp_path):
    """A-13: si el archivo aparece después, la siguiente petición que lo necesita lo carga."""
    client = make_client(tmp_path, None)
    assert client.get("/health").json()["status"] == "degraded"
    (tmp_path / "topology.json").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    assert client.get("/route", params={"src": "A", "dst": "D"}).json()["path"] == ["A", "B", "D"]
    assert client.get("/health").json()["status"] == "ok"
