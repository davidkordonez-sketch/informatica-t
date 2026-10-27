"""TC-18: rendimiento reproducible de GET /route (NFR-10, protocolo de 06 §4)."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from controller.config import ControllerSettings
from controller.main import create_app

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "large_topology_200n_1000l.json"
SHA_FILE = ROOT / "tests" / "fixtures" / "large_topology_200n_1000l.sha256"
ENV_FILE = ROOT / "tests" / "perf-environment.txt"
METRICS = ["delay", "bandwidth", "loss"]
WARMUP, MEASURED, REPETITIONS, P95_LIMIT_MS = 10, 100, 3, 200.0


def cost(link, metric):
    if metric == "delay":
        return link["delay_ms"]
    if metric == "bandwidth":
        return 1.0 / link["bandwidth_mbps"]
    return -math.log1p(-link["loss_prob"])


def oracle_graphs(document):
    """Grafos construidos de forma INDEPENDIENTE al Controller, solo para verificar resultados."""
    graphs = {}
    for metric in METRICS:
        graph = nx.Graph()
        graph.add_nodes_from(document["nodes"])
        for link in document["links"]:
            if link["loss_prob"] < 1:
                graph.add_edge(link["node_a"], link["node_b"], weight=cost(link, metric))
        graphs[metric] = graph
    return graphs


def queries(document):
    rng = random.Random(4242)
    nodes = document["nodes"]
    result = []
    while len(result) < WARMUP + MEASURED:
        src, dst = rng.choice(nodes), rng.choice(nodes)
        if src != dst:
            result.append((src, dst, METRICS[len(result) % 3]))
    return result


def nearest_rank_p95(samples_ms):
    ordered = sorted(samples_ms)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def cpu_model():
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def total_ram():
    try:
        return f"{os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 1024**3:.1f} GiB"
    except (ValueError, OSError, AttributeError):
        return "unknown"


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5).stdout.strip() or "n/a"
    except Exception:
        return "n/a"


@pytest.mark.extension
@pytest.mark.perf
def test_tc18_route_query_p95_on_200_nodes_1000_links():
    content = FIXTURE.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert digest == SHA_FILE.read_text().strip(), "el fixture cambió: no es reproducible"
    document = json.loads(content)
    assert len(document["nodes"]) == 200 and len(document["links"]) == 1000

    graphs = oracle_graphs(document)
    link_set = {frozenset((l["node_a"], l["node_b"])) for l in document["links"]}
    all_queries = queries(document)
    client = TestClient(create_app(ControllerSettings(port=0, topology_file=str(FIXTURE))))

    runs = []
    for _ in range(REPETITIONS):
        samples = []
        for index, (src, dst, metric) in enumerate(all_queries):
            started = time.perf_counter()
            response = client.get("/route", params={"src": src, "dst": dst, "metric": metric})
            elapsed_ms = (time.perf_counter() - started) * 1000
            # Corrección: condición previa, ninguna respuesta incorrecta se excluye
            assert response.status_code == 200, (src, dst, metric, response.text)
            body = response.json()
            path = body["path"]
            assert path[0] == src and path[-1] == dst
            assert all(frozenset(pair) in link_set for pair in zip(path, path[1:]))
            assert math.isclose(math.fsum(body["hop_costs"]), body["total_cost"], rel_tol=1e-9, abs_tol=1e-12)
            expected = nx.dijkstra_path_length(graphs[metric], src, dst, weight="weight")
            assert math.isclose(body["total_cost"], expected, rel_tol=1e-9, abs_tol=1e-12)
            if index >= WARMUP:
                samples.append(elapsed_ms)
        assert len(samples) == MEASURED
        runs.append(
            {"p50": statistics.median(samples), "p95": nearest_rank_p95(samples), "max": max(samples)}
        )

    median_p95 = statistics.median(run["p95"] for run in runs)
    lines = [
        f"TC-18 run: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"commit: {git_commit()}",
        f"fixture: {FIXTURE.name} sha256={digest}",
        f"cpu: {cpu_model()} | cores: {os.cpu_count()} | ram: {total_ram()}",
        f"os: {platform.platform()} | python: {platform.python_version()}",
        "packages: " + ", ".join(f"{p}={package_version(p)}" for p in ("fastapi", "starlette", "pydantic", "networkx", "httpx", "uvicorn")),
        "power: not recorded automatically (indicar manualmente si el portátil estaba conectado)",
        f"protocol: warmup={WARMUP}, measured={MEASURED}, repetitions={REPETITIONS}, in-process TestClient, nearest-rank p95",
    ]
    for number, run in enumerate(runs, start=1):
        lines.append(f"run {number}: p50={run['p50']:.2f} ms  p95={run['p95']:.2f} ms  max={run['max']:.2f} ms")
    lines.append(f"median p95 = {median_p95:.2f} ms (limit {P95_LIMIT_MS} ms) -> {'PASS' if median_p95 <= P95_LIMIT_MS else 'FAIL'}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    assert median_p95 <= P95_LIMIT_MS
