"""TC-19: el Router falla rápido si el Controller no responde (NFR-11)."""
from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from router.config import RouterSettings
from router.main import create_app
from tests.fakes import FakeForwardingLogDAO
from tests.helpers import free_port

TIMEOUT_S = 1.0


class SlowHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - nombre exigido por http.server
        time.sleep(3)  # más que el timeout
        try:
            self.send_response(200)
            self.end_headers()
        except OSError:
            pass

    def log_message(self, *args):
        pass


@pytest.fixture
def slow_controller():
    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.mark.extension
@pytest.mark.parametrize("scenario", ["lento", "inexistente"])
def test_tc19_router_answers_503_within_timeout_plus_one_second(scenario, slow_controller):
    url = slow_controller if scenario == "lento" else f"http://127.0.0.1:{free_port()}"
    settings = RouterSettings(0, url, TIMEOUT_S, "unused")
    client = TestClient(create_app(settings, log_dao=FakeForwardingLogDAO()))

    started = time.perf_counter()
    response = client.post("/packets", json={"packet_id": "pkt", "src": "A", "dst": "D"})
    elapsed = time.perf_counter() - started

    assert response.status_code == 503
    expected = "CONTROLLER_TIMEOUT" if scenario == "lento" else "CONTROLLER_UNAVAILABLE"
    assert response.json()["error"]["code"] == expected
    assert elapsed <= TIMEOUT_S + 1.0
    health_started = time.perf_counter()
    assert client.get("/health").status_code == 200
    assert time.perf_counter() - health_started < 0.5
