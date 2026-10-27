"""Adaptador HTTP hacia GET /route del Controller (FR-07).

Clasifica TODAS las respuestas según 04 §3 regla 4 / 01 §7.2 (R11) y valida el
RouteResponse (A-15). Validar el formato NO es calcular rutas: aquí no hay costos ni grafos.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

import httpx

from router.clients.route_provider import RouteProvider
from router.exceptions import (
    ControllerBadResponseError,
    ControllerTimeoutError,
    ControllerUnavailableError,
    DomainError,
    InvalidParameterError,
    NodeNotFoundError,
    RouteNotFoundError,
)
from router.models import RouteInfo


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class HttpControllerClient(RouteProvider):
    def __init__(self, base_url: str, timeout_s: float, transport: Optional[httpx.BaseTransport] = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        # ``transport`` permite inyectar httpx.MockTransport en pruebas (TC-05, TC-25).
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout_s, transport=transport)

    def close(self) -> None:
        self._client.close()

    def get_route(self, src: str, dst: str, metric: str) -> RouteInfo:
        try:
            response = self._client.get("/route", params={"src": src, "dst": dst, "metric": metric})
        except httpx.TimeoutException as error:
            raise ControllerTimeoutError(
                "Controller did not answer in time", {"timeout_s": self._timeout_s}
            ) from error
        except httpx.HTTPError as error:  # conexión rechazada, DNS, protocolo...
            raise ControllerUnavailableError(
                "Controller is unavailable", {"reason": type(error).__name__}
            ) from error

        if response.status_code == 200:
            return self.parse_route_response(response, src, dst, metric)
        raise self.map_error_response(response)

    # ------------------------------------------------------------ validación
    def parse_route_response(self, response: httpx.Response, src: str, dst: str, metric: str) -> RouteInfo:
        def bad(reason: str) -> ControllerBadResponseError:
            return ControllerBadResponseError(
                "Controller response does not match the API contract",
                {"reason": reason, "upstream_status": response.status_code},
            )

        try:
            body = response.json()
        except ValueError:
            raise bad("invalid_json")
        if not isinstance(body, dict):
            raise bad("schema_mismatch")
        path = body.get("path")
        hop_costs = body.get("hop_costs")
        total_cost = body.get("total_cost")
        version = body.get("topology_version")
        if (
            not isinstance(path, list)
            or not all(isinstance(node, str) for node in path)
            or not isinstance(hop_costs, list)
            or not all(_is_number(cost) for cost in hop_costs)
            or not _is_number(total_cost)
            or not isinstance(version, int)
            or isinstance(version, bool)
        ):
            raise bad("schema_mismatch")
        if body.get("src") != src or body.get("dst") != dst or body.get("metric") != metric:
            raise bad("query_mismatch")
        if not path:
            raise bad("empty_path")
        if path[0] != src:
            raise bad("path_src_mismatch")
        if path[-1] != dst:
            raise bad("path_dst_mismatch")
        if len(set(path)) != len(path):
            raise bad("path_repeated_nodes")
        if len(hop_costs) != len(path) - 1:
            raise bad("hop_costs_mismatch")
        if total_cost < 0 or any(cost < 0 for cost in hop_costs):
            raise bad("negative_cost")
        if version < 1:
            raise bad("invalid_topology_version")
        return RouteInfo(path=list(path), total_cost=float(total_cost), topology_version=version)

    # ---------------------------------------------------------- traducción
    def map_error_response(self, response: httpx.Response) -> DomainError:
        status = response.status_code
        error = self._error_object(response)
        code = error.get("code") if error else None
        upstream_details: Dict[str, Any] = error.get("details", {}) if error else {}
        if not isinstance(upstream_details, dict):
            upstream_details = {}

        if status >= 500:  # incluye 503 TOPOLOGY_UNAVAILABLE (fila E3)
            return ControllerUnavailableError(
                "Controller returned a server error", {"upstream_status": status, "upstream_code": code}
            )
        if status == 404 and code == "ROUTE_NOT_FOUND":
            return RouteNotFoundError(error.get("message", "No route"), upstream_details)
        if status == 404 and code == "NODE_NOT_FOUND":
            details = {"node": upstream_details.get("node")} if "node" in upstream_details else {}
            return NodeNotFoundError(error.get("message", "Node not found"), details)
        if status == 400 and code == "INVALID_PARAMETER":
            return InvalidParameterError(
                error.get("message", "Invalid parameter"), {"source": "controller", "upstream": upstream_details}
            )
        reason = "unexpected_error_code" if status in (400, 404) else "unexpected_status"
        return ControllerBadResponseError(
            "Controller response does not match the API contract",
            {"reason": reason, "upstream_status": status, "upstream_code": code},
        )

    @staticmethod
    def _error_object(response: httpx.Response) -> Optional[Dict[str, Any]]:
        try:
            body = response.json()
        except ValueError:
            return None
        if isinstance(body, dict) and isinstance(body.get("error"), dict) and isinstance(body["error"].get("code"), str):
            return body["error"]
        return None
