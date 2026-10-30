"""TC-27: consola visual del Controller (capa Vista).

(a) Se sirve en /ui/ y la raíz redirige allí.
(b) Solo consume la API REST documentada: no calcula rutas ni costos.
(c) El Router acepta llamadas del navegador desde el origen de la consola (CORS) y rechaza otros.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from controller.config import UI_DIR
from controller.main import create_app as create_controller_app
from router.config import RouterSettings
from router.main import create_app as create_router_app
from tests.fakes import FakeForwardingLogDAO, FakeTopologyDAO

API_PATHS = ("/topology", "/route", "/links/", "/packets", "/health")


@pytest.mark.recommended
def test_tc27a_console_is_served_under_ui():
    client = TestClient(create_controller_app(topology_dao=FakeTopologyDAO()))

    root = client.get("/", follow_redirects=False)
    assert root.status_code in (302, 307)
    assert root.headers["location"] == "/ui/"

    page = client.get("/ui/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "app.js" in page.text

    script = client.get("/ui/app.js")
    assert script.status_code == 200

    # La consola no reemplaza la API: los endpoints siguen respondiendo JSON
    assert client.get("/health").json()["status"] == "ok"


@pytest.mark.recommended
def test_tc27b_console_only_uses_the_rest_api():
    source = (UI_DIR / "app.js").read_text(encoding="utf-8")

    assert source.count("fetch(") == 1, "toda llamada de red debe pasar por la función api()"
    paths = re.findall(r"api\(\s*(?:[^,()]|\(\))*,\s*[`\"']([^`\"'?$]+)", source)
    assert paths, "no se encontraron llamadas a la API"
    assert all(path.startswith(API_PATHS) for path in paths), paths
    assert "dijkstra" not in source.lower(), "la Vista no debe calcular rutas"


@pytest.mark.recommended
def test_tc27c_router_accepts_the_console_origin_only():
    settings = RouterSettings(0, "http://controller.invalid", 1.0, "unused")
    client = TestClient(create_router_app(settings, log_dao=FakeForwardingLogDAO()))
    preflight = {"access-control-request-method": "POST", "access-control-request-headers": "content-type"}

    allowed = client.options("/packets", headers={"origin": "http://localhost:8000", **preflight})
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:8000"

    rejected = client.options("/packets", headers={"origin": "http://evil.example", **preflight})
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
