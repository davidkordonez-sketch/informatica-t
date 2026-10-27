"""Pruebas de ForwardingService: TC-06, TC-09, TC-15, TC-24 (sin red ni archivos)."""
from __future__ import annotations

import pytest

from router.exceptions import (
    ControllerBadResponseError,
    ControllerTimeoutError,
    ControllerUnavailableError,
    NodeNotFoundError,
    RouteNotFoundError,
)
from router.models import ForwardingStatus, Packet, ResultWarning
from router.services.forwarding_service import ForwardingService
from tests.fakes import FailingForwardingLogDAO, FakeForwardingLogDAO, FakeRouteProvider
from tests.helpers import fixed_clock

PACKET = Packet("pkt-001", "A", "D", "delay", "hello")
PERSISTENCE_WARNING = [ResultWarning("PERSISTENCE_ERROR", "Forwarding log could not be persisted")]


@pytest.mark.mandatory
def test_tc06_forwarding_trace_reports_valid_outcome():
    service = ForwardingService(FakeRouteProvider(), FakeForwardingLogDAO(), clock=fixed_clock)
    result = service.forward_packet(PACKET)
    assert result.status == ForwardingStatus.DELIVERED
    assert [(h.hop, h.from_node, h.to_node, h.status) for h in result.trace] == [
        (1, "A", "B", "FORWARDED"),
        (2, "B", "D", "FORWARDED"),
    ]
    assert result.route.path == ["A", "B", "D"] and result.reason is None


@pytest.mark.mandatory
def test_tc09_forwarding_service_uses_its_log_dao_and_runs_in_isolation():
    provider, log_dao = FakeRouteProvider(), FakeForwardingLogDAO()
    result = ForwardingService(provider, log_dao, clock=fixed_clock).forward_packet(PACKET)
    assert provider.calls == [("A", "D", "delay")]
    assert len(log_dao.saved) == 1
    saved = log_dao.saved[0]
    assert (saved.packet_id, saved.status) == ("pkt-001", ForwardingStatus.DELIVERED)
    assert result.log_persisted is True and result.warnings == []


@pytest.mark.recommended
@pytest.mark.parametrize("dao_error", [None, RuntimeError("unexpected DAO bug")], ids=["PersistenceError", "RuntimeError"])
def test_tc15_persistence_failure_keeps_delivered_result(dao_error):
    log_dao = FailingForwardingLogDAO(dao_error)
    result = ForwardingService(FakeRouteProvider(), log_dao, clock=fixed_clock).forward_packet(PACKET)  # no relanza
    assert result.status == ForwardingStatus.DELIVERED  # fila D2
    assert len(result.trace) == 2
    assert result.log_persisted is False
    assert result.warnings == PERSISTENCE_WARNING
    assert log_dao.save_calls == 1  # sin reintentos


@pytest.mark.mandatory
def test_tc24a_unreachable_result_is_persisted():
    log_dao = FakeForwardingLogDAO()
    provider = FakeRouteProvider(error=RouteNotFoundError("no route"))
    result = ForwardingService(provider, log_dao, clock=fixed_clock).forward_packet(Packet("pkt-002", "A", "F"))
    assert result.status == ForwardingStatus.UNREACHABLE  # fila D3
    assert result.route is None and result.trace == [] and result.reason == "ROUTE_NOT_FOUND"
    assert len(log_dao.saved) == 1 and log_dao.saved[0].status == ForwardingStatus.UNREACHABLE
    assert result.log_persisted is True and result.warnings == []


@pytest.mark.mandatory
def test_tc24b_unreachable_with_persistence_failure():
    log_dao = FailingForwardingLogDAO()
    provider = FakeRouteProvider(error=RouteNotFoundError("no route"))
    result = ForwardingService(provider, log_dao, clock=fixed_clock).forward_packet(Packet("pkt-004", "A", "F"))
    assert result.status == ForwardingStatus.UNREACHABLE  # fila D4
    assert result.log_persisted is False and result.warnings == PERSISTENCE_WARNING
    assert log_dao.save_calls == 1


@pytest.mark.mandatory
@pytest.mark.parametrize(
    "error",
    [
        NodeNotFoundError("Z"),
        ControllerUnavailableError("down"),
        ControllerTimeoutError("slow"),
        ControllerBadResponseError("bad"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_tc24c_error_branches_never_create_or_persist_a_result(error):
    log_dao = FakeForwardingLogDAO()
    service = ForwardingService(FakeRouteProvider(error=error), log_dao, clock=fixed_clock)
    with pytest.raises(type(error)):
        service.forward_packet(PACKET)
    assert log_dao.saved == []  # filas E1, E3-E6
