"""Utilidades de prueba."""
from __future__ import annotations

import json
import socket
from typing import Any, Callable, Dict, List

import httpx
from fastapi.testclient import TestClient

FIXED_TIME = "2026-10-26T12:00:00Z"


def fixed_clock() -> str:
    return FIXED_TIME


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def bridge_to(controller_client: TestClient) -> httpx.MockTransport:
    """Transporte httpx que entrega las peticiones del Router a un Controller en proceso."""

    def handler(request: httpx.Request) -> httpx.Response:
        response = controller_client.get(request.url.path, params=dict(request.url.params))
        return httpx.Response(response.status_code, content=response.content, headers={"content-type": "application/json"})

    return httpx.MockTransport(handler)


def recording_transport(responder: Callable[[httpx.Request], httpx.Response]) -> "RecordingTransport":
    return RecordingTransport(responder)


class RecordingTransport(httpx.MockTransport):
    def __init__(self, responder: Callable[[httpx.Request], httpx.Response]) -> None:
        self.requests: List[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return responder(request)

        super().__init__(handler)


def json_response(status: int, body: Any) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(body).encode(), headers={"content-type": "application/json"})


def route_body(path: List[str], hop_costs: List[float], version: int = 1, metric: str = "delay") -> Dict[str, Any]:
    return {
        "src": path[0],
        "dst": path[-1],
        "metric": metric,
        "path": path,
        "hop_costs": hop_costs,
        "total_cost": sum(hop_costs),
        "topology_version": version,
    }
