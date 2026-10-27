"""TC-22: sustitución de interfaces del Router (fakes vs adaptadores reales)."""
from __future__ import annotations

import httpx
import pytest

from router.clients.http_controller_client import HttpControllerClient
from router.dao.jsonlines_forwarding_log_dao import JsonLinesForwardingLogDAO
from router.exceptions import RouteNotFoundError
from router.models import Packet, RouteInfo
from router.services.forwarding_service import ForwardingService
from tests.fakes import FakeForwardingLogDAO, FakeRouteProvider
from tests.helpers import fixed_clock, json_response, route_body

DELIVERED_PACKET = Packet("pkt-1", "A", "D", "delay")
UNREACHABLE_PACKET = Packet("pkt-2", "A", "F", "delay")


class ScriptedFakeProvider(FakeRouteProvider):
    def get_route(self, src, dst, metric):
        if dst == "F":
            raise RouteNotFoundError("no route")
        return RouteInfo(["A", "B", "D"], 20.0, 1)


def controller_stub(request: httpx.Request) -> httpx.Response:
    if request.url.params["dst"] == "F":
        return json_response(404, {"error": {"code": "ROUTE_NOT_FOUND", "message": "x", "details": {}}})
    return json_response(200, route_body(["A", "B", "D"], [10.0, 10.0]))


def run(provider, log_dao):
    service = ForwardingService(provider, log_dao, clock=fixed_clock)
    return [service.forward_packet(DELIVERED_PACKET), service.forward_packet(UNREACHABLE_PACKET)]


@pytest.mark.extension
def test_tc22_forwarding_service_identical_with_fakes_and_real_adapters(tmp_path):
    fake_results = run(ScriptedFakeProvider(), FakeForwardingLogDAO())
    real_provider = HttpControllerClient("http://controller.test", 1.0, transport=httpx.MockTransport(controller_stub))
    real_dao = JsonLinesForwardingLogDAO(str(tmp_path / "log.jsonl"))
    real_results = run(real_provider, real_dao)
    assert fake_results == real_results  # mismo reloj fijo: resultados idénticos


@pytest.mark.extension
@pytest.mark.parametrize("kind", ["fake", "jsonlines"])
def test_tc22_forwarding_log_dao_contract(tmp_path, kind):
    dao = FakeForwardingLogDAO() if kind == "fake" else JsonLinesForwardingLogDAO(str(tmp_path / "log.jsonl"))
    results = run(ScriptedFakeProvider(), dao)
    records = dao.find_all()
    assert records == [result.to_log_record() for result in results]
    assert [record["status"] for record in records] == ["DELIVERED", "UNREACHABLE"]
    for record in records:
        assert "log_persisted" not in record and "warnings" not in record
