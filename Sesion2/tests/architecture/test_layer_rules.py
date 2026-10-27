"""TC-12, TC-13, TC-14: reglas de arquitectura verificadas por análisis AST (R1, R2, R3)."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator, List, Set, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONCRETE_DAO_MODULES = {"json_topology_dao", "jsonlines_forwarding_log_dao"}


def python_files(*relative_dirs: str) -> Iterator[Path]:
    for relative in relative_dirs:
        yield from sorted((ROOT / relative).rglob("*.py"))


def analyse(path: Path) -> Tuple[Set[str], List[str], List[str]]:
    """Devuelve (módulos importados, llamadas 'nombre' o 'obj.attr', funciones definidas)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: Set[str] = set()
    calls: List[str] = []
    functions: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                calls.append(f"{func.value.id}.{func.attr}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
    return imports, calls, functions


def top_level(module: str) -> str:
    return module.split(".")[0]


def last_part(module: str) -> str:
    return module.split(".")[-1]


@pytest.mark.mandatory
def test_tc12_http_controllers_have_no_algorithms_nor_data_access():
    files = list(python_files("controller/controllers", "router/controllers"))
    assert files, "no se encontraron controladores"
    violations = []
    for path in files:
        imports, calls, _ = analyse(path)
        for module in imports:
            if top_level(module) in {"networkx", "heapq", "json", "pathlib"}:
                violations.append(f"{path.name}: importa {module}")
            if ".dao" in module or last_part(module) in CONCRETE_DAO_MODULES:
                violations.append(f"{path.name}: importa la capa DAO ({module})")
        if "open" in calls:
            violations.append(f"{path.name}: llama a open()")
    assert violations == []


@pytest.mark.recommended
def test_tc13_services_have_no_direct_io_nor_concrete_dao_imports():
    files = list(python_files("controller/services", "router/services"))
    assert files
    violations = []
    for path in files:
        imports, calls, _ = analyse(path)
        if "pathlib" in {top_level(m) for m in imports}:
            violations.append(f"{path.name}: importa pathlib")
        for module in imports:
            if last_part(module) in CONCRETE_DAO_MODULES:
                violations.append(f"{path.name}: importa DAO concreto {module}")
        for call in calls:
            if call in {"open", "json.load", "json.loads", "json.dump", "json.dumps"}:
                violations.append(f"{path.name}: llama a {call}()")
    assert violations == []


@pytest.mark.recommended
def test_tc14_router_does_not_compute_routes():
    violations = []
    for path in python_files("router"):
        imports, calls, functions = analyse(path)
        for module in imports:
            if top_level(module) in {"networkx", "heapq"}:
                violations.append(f"{path.name}: importa {module}")
        for name in functions + calls:
            lowered = name.lower()
            if any(word in lowered for word in ("dijkstra", "shortest_path", "bellman", "floyd")):
                violations.append(f"{path.name}: {name}")
    assert violations == []
