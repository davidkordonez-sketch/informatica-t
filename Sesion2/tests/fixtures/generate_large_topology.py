"""Generador del fixture de rendimiento de TC-18 (06 §4). Se ejecuta UNA vez y el resultado se versiona.

    python tests/fixtures/generate_large_topology.py

Algoritmo fijo (semilla 42): nodos N000..N199; anillo de 200 enlaces (grafo conexo);
enlaces aleatorios hasta llegar a 1000; atributos sorteados al crear cada enlace.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "large_topology_200n_1000l.json"
SHA_FILE = HERE / "large_topology_200n_1000l.sha256"
NODE_COUNT, LINK_COUNT, SEED = 200, 1000, 42


def generate() -> dict:
    rng = random.Random(SEED)
    nodes = [f"N{i:03d}" for i in range(NODE_COUNT)]
    links, seen = [], set()

    def add(i: int, j: int) -> None:
        seen.add(frozenset((i, j)))
        links.append(
            {
                "node_a": nodes[i],
                "node_b": nodes[j],
                "delay_ms": rng.randint(1, 50),
                "bandwidth_mbps": rng.choice([10, 100, 1000]),
                "loss_prob": round(rng.uniform(0.0, 0.05), 4),
            }
        )

    for i in range(NODE_COUNT):  # anillo
        add(i, (i + 1) % NODE_COUNT)
    while len(links) < LINK_COUNT:
        i, j = rng.randrange(NODE_COUNT), rng.randrange(NODE_COUNT)
        if i == j or frozenset((i, j)) in seen:
            continue
        add(i, j)
    return {"nodes": nodes, "links": links}


def main() -> None:
    content = json.dumps(generate(), indent=1).encode("utf-8")
    OUTPUT.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    SHA_FILE.write_text(digest + "\n", encoding="utf-8")
    print(f"{OUTPUT.name}: {digest}")


if __name__ == "__main__":
    main()
