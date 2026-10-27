"""TC-16: integración E2E con DOS procesos reales comunicándose por HTTP."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from tests.helpers import free_port

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "topology.json"


def start(module: str, port: int, env_extra: dict, log_path: Path) -> subprocess.Popen:
    env = {**os.environ, **env_extra}
    log = open(log_path, "w")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", f"{module}.main:app", "--host", "127.0.0.1", "--port", str(port), "--workers", "1"],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
    )


def wait_healthy(url: str, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if httpx.get(f"{url}/health", timeout=0.5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"{url} did not start")


@pytest.fixture
def running_apps(tmp_path):
    controller_port, router_port = free_port(), free_port()
    log_file = tmp_path / "forwarding_log.jsonl"
    controller = start("controller", controller_port, {"TOPOLOGY_FILE": str(FIXTURE)}, tmp_path / "controller.out")
    router = start(
        "router",
        router_port,
        {
            "CONTROLLER_URL": f"http://127.0.0.1:{controller_port}",
            "CONTROLLER_TIMEOUT_S": "2",
            "FORWARDING_LOG_FILE": str(log_file),
        },
        tmp_path / "router.out",
    )
    try:
        controller_url, router_url = f"http://127.0.0.1:{controller_port}", f"http://127.0.0.1:{router_port}"
        wait_healthy(controller_url)
        wait_healthy(router_url)
        yield controller_url, router_url, log_file
    finally:
        for process in (router, controller):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover
                process.kill()


def log_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


@pytest.mark.recommended
@pytest.mark.integration
def test_tc16_end_to_end_two_processes(running_apps):
    controller_url, router_url, log_file = running_apps

    def send(packet_id):
        response = httpx.post(f"{router_url}/packets", json={"packet_id": packet_id, "src": "A", "dst": "D", "metric": "delay"})
        assert response.status_code == 200
        return response.json()

    first = send("pkt-1")
    assert first["route"]["path"] == ["A", "B", "D"] and first["route"]["topology_version"] == 1
    assert [(h["from_node"], h["to_node"]) for h in first["trace"]] == [("A", "B"), ("B", "D")]
    assert log_lines(log_file) == 1

    failed = httpx.post(f"{controller_url}/links/fail", json={"node_a": "B", "node_b": "D"}).json()
    assert failed["topology_version"] == 2
    second = send("pkt-2")
    assert second["route"]["path"] == ["A", "C", "D"] and second["route"]["total_cost"] == 25
    assert second["route"]["topology_version"] == 2
    assert [(h["from_node"], h["to_node"]) for h in second["trace"]] == [("A", "C"), ("C", "D")]
    assert log_lines(log_file) == 2

    restored = httpx.post(f"{controller_url}/links/restore", json={"node_a": "B", "node_b": "D"}).json()
    assert restored["topology_version"] == 3
    third = send("pkt-3")
    assert third["route"]["path"] == ["A", "B", "D"] and third["route"]["topology_version"] == 3
    assert log_lines(log_file) == 3

    records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert [r["packet_id"] for r in records] == ["pkt-1", "pkt-2", "pkt-3"]
