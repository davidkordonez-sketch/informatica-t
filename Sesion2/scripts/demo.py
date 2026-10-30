"""Demo guiada del comportamiento en vivo obligatorio (enunciado: "Mandatory live behavior").

Requisitos: el Controller y el Router ya deben estar corriendo como procesos separados.
Ejecutar desde la carpeta Sesion2:

    python scripts/demo.py                    # demo completa (al final pide apagar el Controller)
    python scripts/demo.py --no-interactive   # sin el paso del Controller apagado

Usa solo la biblioteca estándar. Supone la topología de referencia de controller/data/topology.json.
La salida se muestra en pantalla y se guarda en demo-evidence/demo-log.txt.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG = BASE_DIR / "demo-evidence" / "demo-log.txt"


class Demo:
    def __init__(self, controller_url: str, router_url: str, log_path: Path) -> None:
        self.controller = controller_url.rstrip("/")
        self.router = router_url.rstrip("/")
        self.log_path = log_path
        self.lines: List[str] = []
        self.failures: List[str] = []
        self.packet_counter = 0

    # ------------------------------------------------------------ utilidades
    def say(self, text: str = "") -> None:
        print(text)
        self.lines.append(text)

    def request(self, method: str, url: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method, headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8")
            try:
                return error.code, json.loads(raw)
            except ValueError:
                return error.code, raw
        except (urllib.error.URLError, OSError) as error:
            return 0, {"connection_error": str(error)}

    def call(self, title: str, method: str, url: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, Any]:
        self.say(f"\n>>> {title}")
        self.say(f"    {method} {url}" + (f"  {json.dumps(body)}" if body else ""))
        status, payload = self.request(method, url, body)
        self.say(f"<<< HTTP {status}")
        for line in json.dumps(payload, indent=2, ensure_ascii=False).splitlines():
            self.say(f"    {line}")
        return status, payload

    def check(self, condition: bool, description: str) -> None:
        self.say(f"    [{'OK' if condition else 'FALLÓ'}] {description}")
        if not condition:
            self.failures.append(description)

    def send_packet(self, title: str, dst: str = "D", metric: str = "delay") -> Tuple[int, Any]:
        self.packet_counter += 1
        body = {"packet_id": f"demo-{self.packet_counter}", "src": "A", "dst": dst, "metric": metric}
        return self.call(title, "POST", f"{self.router}/packets", body)

    def link(self, action: str, node_a: str, node_b: str) -> Tuple[int, Any]:
        verb = "Fallar" if action == "fail" else "Restablecer"
        return self.call(
            f"{verb} el enlace {node_a}–{node_b}",
            "POST",
            f"{self.controller}/links/{action}",
            {"node_a": node_a, "node_b": node_b},
        )

    @staticmethod
    def path_of(payload: Any) -> Optional[List[str]]:
        route = payload.get("route") if isinstance(payload, dict) else None
        return route.get("path") if isinstance(route, dict) else None

    def wait_for(self, url: str, seconds: float = 15.0) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            status, _ = self.request("GET", url)
            if status == 200:
                return True
            time.sleep(0.5)
        return False

    # ----------------------------------------------------------------- pasos
    def run(self, interactive: bool) -> int:
        self.say(f"DEMO SDN — {datetime.now().isoformat(timespec='seconds')}")
        self.say(f"Controller: {self.controller} · Router: {self.router}")

        if not (self.wait_for(f"{self.controller}/health") and self.wait_for(f"{self.router}/health")):
            self.say("No responden ambas apps. Arranquen primero:")
            self.say("  python -m controller.main     y     python -m router.main")
            self.save()
            return 2

        self.say("\n=== Paso 0. Estado inicial ===")
        self.call("Health del Controller", "GET", f"{self.controller}/health")
        self.call("Health del Router", "GET", f"{self.router}/health")
        status, topology = self.request("GET", f"{self.controller}/topology")
        if status == 200:  # si una demo anterior dejó enlaces caídos, se restablecen
            for link in topology.get("links", []):
                if link.get("status") == "failed":
                    self.link("restore", link["node_a"], link["node_b"])

        self.say("\n=== Paso 1. Paquete A→D: el Router pide la ruta al Controller ===")
        status, result = self.send_packet("Enviar paquete A→D (delay)")
        self.check(status == 200 and result.get("status") == "DELIVERED", "status DELIVERED")
        self.check(self.path_of(result) == ["A", "B", "D"], "ruta del Controller [A, B, D], costo 20")
        self.check(len(result.get("trace", [])) == 2 if isinstance(result, dict) else False, "trace con 2 saltos")

        self.say("\n=== Paso 2. Fallar B–D (enlace usado por la ruta) y reenviar ===")
        status, _ = self.link("fail", "B", "D")
        self.check(status == 200, "enlace B–D fallado")
        status, result = self.send_packet("Reenviar paquete A→D")
        self.check(self.path_of(result) == ["A", "C", "D"], "nueva ruta [A, C, D], costo 25 (B–D excluido)")

        self.say("\n=== Paso 3. Fallar también C–D: destino inalcanzable ===")
        self.link("fail", "C", "D")
        status, result = self.send_packet("Enviar paquete A→D sin caminos disponibles")
        self.check(status == 200 and result.get("status") == "UNREACHABLE", "status UNREACHABLE y se registra")

        self.say("\n=== Paso 4. Restablecer los enlaces y repetir ===")
        self.link("restore", "C", "D")
        status, _ = self.link("restore", "B", "D")
        self.check(status == 200, "enlace B–D restablecido")
        status, result = self.send_packet("Reenviar paquete A→D")
        self.check(self.path_of(result) == ["A", "B", "D"], "vuelve la ruta [A, B, D]")
        status, route = self.call(
            "Consultar la misma ruta directamente al Controller",
            "GET",
            f"{self.controller}/route?" + urllib.parse.urlencode({"src": "A", "dst": "D", "metric": "delay"}),
        )
        self.check(status == 200 and route.get("path") == ["A", "B", "D"], "GET /route coincide con el Router")

        self.say("\n=== Paso 5. Métrica alternativa (desafío del instructor) ===")
        status, route = self.call(
            "Ruta A→D con bandwidth",
            "GET",
            f"{self.controller}/route?" + urllib.parse.urlencode({"src": "A", "dst": "D", "metric": "bandwidth"}),
        )
        self.check(status == 200 and route.get("path") == ["A", "C", "D"], "bandwidth elige [A, C, D], costo 0,02")

        self.say("\n=== Paso 6. Errores controlados ===")
        status, result = self.send_packet("Paquete a un nodo inexistente Z", dst="Z")
        code = result.get("error", {}).get("code") if isinstance(result, dict) else None
        self.check(status == 404 and code == "NODE_NOT_FOUND", "404 NODE_NOT_FOUND (distinto de ruta ausente)")
        self.link("fail", "B", "D")
        status, result = self.link("fail", "B", "D")
        self.check(status == 409, "409 al fallar un enlace ya fallado")
        self.link("restore", "B", "D")

        self.say("\n=== Paso 7. Aislamiento DAO: TC-08 y TC-09 con DAO falso, sin HTTP ===")
        command = [sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider", "-k", "tc08 or tc09"]
        self.say("    " + " ".join(command))
        completed = subprocess.run(command, cwd=BASE_DIR, capture_output=True, text=True)
        for line in completed.stdout.splitlines():
            if "PASSED" in line or "FAILED" in line or "passed" in line or "failed" in line:
                self.say(f"    {line.strip()}")
        if completed.returncode != 0:  # muestra la causa (p. ej., pytest no instalado o venv sin activar)
            for line in (completed.stderr or completed.stdout).strip().splitlines()[-3:]:
                self.say(f"    {line}")
        self.check(completed.returncode == 0, "TC-08 y TC-09 pasan con fakes")

        if interactive:
            self.say("\n=== Paso 8. Controller no disponible ===")
            input("\n    Detengan el Controller (Ctrl+C en su terminal) y presionen Enter... ")
            status, result = self.send_packet("Enviar paquete con el Controller apagado")
            code = result.get("error", {}).get("code") if isinstance(result, dict) else None
            self.check(status == 503 and code == "CONTROLLER_UNAVAILABLE", "503 CONTROLLER_UNAVAILABLE")
            status, _ = self.call("Health del Router", "GET", f"{self.router}/health")
            self.check(status == 200, "el Router sigue vivo (200)")

        self.say("\n=== Resumen ===")
        if self.failures:
            self.say(f"{len(self.failures)} verificación(es) fallaron:")
            for failure in self.failures:
                self.say(f"  - {failure}")
        else:
            self.say("Todas las verificaciones pasaron.")
        self.save()
        return 1 if self.failures else 0

    def save(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        print(f"\nSalida guardada en {self.log_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo en vivo del Controller y el Router SDN")
    parser.add_argument("--controller", default=os.getenv("CONTROLLER_URL", "http://localhost:8000"))
    parser.add_argument("--router", default=os.getenv("ROUTER_URL", "http://localhost:8001"))
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--no-interactive", action="store_true", help="omite el paso del Controller apagado")
    args = parser.parse_args()
    return Demo(args.controller, args.router, Path(args.log)).run(interactive=not args.no_interactive)


if __name__ == "__main__":
    sys.exit(main())
