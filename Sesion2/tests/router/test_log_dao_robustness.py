"""TC-26: escritura parcial y fallo de fsync en JsonLinesForwardingLogDAO (A-16)."""
from __future__ import annotations

import pytest

import router.dao.jsonlines_forwarding_log_dao as dao_module
from router.dao.jsonlines_forwarding_log_dao import JsonLinesForwardingLogDAO
from router.exceptions import PersistenceError
from router.models import Packet
from router.services.forwarding_service import ForwardingService
from tests.fakes import FakeRouteProvider
from tests.helpers import fixed_clock


class HalfWriteFile:
    """Escribe la mitad de los bytes y luego falla, como un disco que se llena a mitad."""

    def __init__(self, real_file):
        self._real = real_file

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._real.close()
        return False

    def write(self, data):
        self._real.write(data[: len(data) // 2])
        self._real.flush()
        raise OSError(28, "No space left on device")

    def flush(self):
        self._real.flush()

    def fileno(self):
        return self._real.fileno()


def half_write_opener(path, mode):
    return HalfWriteFile(open(path, mode))


@pytest.mark.extension
def test_tc26_partial_write_is_isolated_and_reported(tmp_path):
    log_file = tmp_path / "log.jsonl"
    broken_dao = JsonLinesForwardingLogDAO(str(log_file), opener=half_write_opener)
    service = ForwardingService(FakeRouteProvider(), broken_dao, clock=fixed_clock)

    first = service.forward_packet(Packet("pkt-partial", "A", "D"))
    assert first.log_persisted is False
    assert first.warnings[0].code == "PERSISTENCE_ERROR"
    other_dao = JsonLinesForwardingLogDAO(str(tmp_path / "other.jsonl"), opener=half_write_opener)
    with pytest.raises(PersistenceError):  # el DAO solo lanza PersistenceError, no OSError
        other_dao.save(first)

    healthy_dao = JsonLinesForwardingLogDAO(str(log_file))
    second = ForwardingService(FakeRouteProvider(), healthy_dao, clock=fixed_clock).forward_packet(Packet("pkt-ok", "A", "D"))
    assert second.log_persisted is True

    records = healthy_dao.find_all()
    assert [record["packet_id"] for record in records] == ["pkt-ok"]
    assert healthy_dao.last_skipped_lines == 1  # el fragmento quedó aislado en su propia línea
    assert log_file.read_bytes().count(b"\n") == 2


@pytest.mark.extension
def test_tc26_fsync_failure_means_not_persisted(tmp_path, monkeypatch):
    def broken_fsync(fd):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(dao_module.os, "fsync", broken_fsync)
    dao = JsonLinesForwardingLogDAO(str(tmp_path / "log.jsonl"))
    result = ForwardingService(FakeRouteProvider(), dao, clock=fixed_clock).forward_packet(Packet("pkt", "A", "D"))
    assert result.log_persisted is False  # "no garantizado" aunque la línea pueda existir


@pytest.mark.extension
def test_tc26_concurrent_saves_produce_complete_lines(tmp_path):
    import threading

    dao = JsonLinesForwardingLogDAO(str(tmp_path / "log.jsonl"))
    service = ForwardingService(FakeRouteProvider(), dao, clock=fixed_clock)
    threads = [threading.Thread(target=service.forward_packet, args=(Packet(f"pkt-{i}", "A", "D"),)) for i in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    records = dao.find_all()
    assert len(records) == 50 and dao.last_skipped_lines == 0
