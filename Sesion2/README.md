# Sesión 2 — Controlador y Enrutador SDN

Simulación SDN a nivel de aplicación con dos procesos Python independientes que se comunican por HTTP/JSON:

- **Controller** (`controller/`, puerto 8000): carga la topología desde JSON mediante `TopologyDAO`, administra el estado de los enlaces, calcula rutas con Dijkstra (NetworkX) y las expone por REST.
- **Router** (`router/`, puerto 8001): recibe paquetes simulados, **pide la ruta al Controller** (nunca la calcula), simula el reenvío salto a salto y registra cada resultado con `ForwardingLogDAO`.

Especificaciones de la Sesión 1 (v1.1): `../Informatica3/Informatica3/01…06` y su registro de cambios en `01-requirements.md` §9.
Documentos de la Sesión 2 (plantillas del profesor): `docs/01-scrum-requirements.md`, `docs/02-test-plan.md`, `docs/03-system-architecture.md`.

## 1. Estructura

```text
controller/                 router/
├── main.py   (composición) ├── main.py   (composición)
├── config.py               ├── config.py
├── controllers/  (MVC: C)  ├── controllers/  (MVC: C)
├── schemas/      (MVC: V)  ├── schemas/      (MVC: V)
├── models/       (MVC: M)  ├── models/       (MVC: M)
├── services/               ├── services/     ForwardingService
│   RoutingService          ├── clients/      RouteProvider, HttpControllerClient
│   TopologyService         ├── dao/          ForwardingLogDAO, JsonLinesForwardingLogDAO
│   LinkCostCalculator      ├── exceptions.py ErrorHandler + errores de dominio
├── dao/  TopologyDAO, JsonTopologyDAO
├── exceptions.py           tests/  controller/ router/ architecture/ integration/ performance/ fixtures/
└── data/topology.json      docs/ (01-scrum, 02-test-plan, 03-architecture, architecture-review) · demo-evidence/ · scripts/demo.py
```

## 2. Instalación

Requiere Python 3.11 o superior.

```bash
cd Sesion2
python -m venv .venv
# Linux/macOS:  source .venv/bin/activate      Windows (PowerShell):  .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Ejecución (dos procesos independientes)

Todos los comandos se ejecutan **desde la carpeta `Sesion2`** (`cd Sesion2`), en dos terminales. En PyCharm: abrir la carpeta `Sesion2` como proyecto y usar su Terminal o *Run* sobre `controller/main.py` y `router/main.py`.

```bash
# Terminal 1 - Controller
python -m controller.main
# Terminal 2 - Router
python -m router.main
```

Puertos y rutas son configurables sin tocar código (NFR-05):

| Variable | Por defecto | App |
|---|---|---|
| `CONTROLLER_PORT` | `8000` | Controller |
| `TOPOLOGY_FILE` | `controller/data/topology.json` | Controller |
| `ROUTER_PORT` | `8001` | Router |
| `CONTROLLER_URL` | `http://localhost:8000` | Router |
| `CONTROLLER_TIMEOUT_S` | `2.0` | Router |
| `FORWARDING_LOG_FILE` | `router/data/forwarding_log.jsonl` | Router |

Ejemplo con otros puertos: Linux/macOS `CONTROLLER_PORT=9000 python -m controller.main`; PowerShell `$env:CONTROLLER_PORT="9000"; python -m controller.main`. También funciona `uvicorn controller.main:app --port 8000` (siempre con 1 worker, ver A-14).

Documentación interactiva: <http://localhost:8000/docs> y <http://localhost:8001/docs>.

### Peticiones de ejemplo

```bash
curl -X POST localhost:8001/packets -H "content-type: application/json" -d '{"packet_id":"pkt-1","src":"A","dst":"D","metric":"delay"}'
curl -X POST localhost:8000/links/fail -H "content-type: application/json" -d '{"node_a":"B","node_b":"D"}'
curl -X POST localhost:8000/links/restore -H "content-type: application/json" -d '{"node_a":"B","node_b":"D"}'
curl "localhost:8000/route?src=A&dst=D&metric=bandwidth"
```

### Demo guiada

Con las dos apps corriendo: `python scripts/demo.py`. Ejecuta el comportamiento en vivo obligatorio: paquete A→D, fallo de B–D y nueva ruta, destino inalcanzable, restablecimiento, métrica alternativa, nodo inexistente, conflicto 409 y las pruebas TC-08/TC-09 con DAO falso.

## 4. Pruebas

Desde la carpeta `Sesion2`:

```bash
pytest -v | tee tests/test-results.txt   # todas (26 casos, 76 pruebas con parametrizaciones)
pytest -m mandatory -v                   # solo las 11 obligatorias (TC-01…TC-09, TC-12, TC-24)
pytest -m "not integration and not perf" # rápidas, sin procesos reales
python tests/fixtures/generate_large_topology.py   # regenera el fixture de TC-18 (no hace falta)
```

**Resultado registrado** (`tests/test-results.txt`): **76 passed, 0 failed** (Linux y Windows).

| TC | Nivel | Qué verifica | Archivo | Estado |
|---|---|---|---|---|
| TC-01 | Obligatoria | Dijkstra elige el camino de costo mínimo; `src = dst` | `tests/controller/test_routing_services.py` | ✅ |
| TC-02 | Obligatoria | Métricas delay, 1/bandwidth y −ln(1−p) | `tests/controller/test_routing_services.py` | ✅ |
| TC-03 | Obligatoria | Enlace fallado excluido; versión 2 | `tests/controller/test_routing_services.py` | ✅ |
| TC-04 | Obligatoria | Restablecer actualiza la ruta; versión 3 | `tests/controller/test_routing_services.py` | ✅ |
| TC-05 | Obligatoria | El Router obtiene la ruta por HTTP (1 `GET /route`) | `tests/router/test_http_controller_client.py` | ✅ |
| TC-06 | Obligatoria | Trace salto a salto válido | `tests/router/test_forwarding_service.py` | ✅ |
| TC-07 | Obligatoria | Controller caído (503), destino aislado (`UNREACHABLE`), nodo inexistente (404) | `tests/router/test_error_scenarios.py` | ✅ |
| TC-08 | Obligatoria | `RoutingService` con `FakeTopologyDAO`, sin HTTP ni archivos | `tests/controller/test_routing_services.py` | ✅ |
| TC-09 | Obligatoria | `ForwardingService` usa su DAO de log, aislado | `tests/router/test_forwarding_service.py` | ✅ |
| TC-10 | Recomendada | `LinkCostCalculator` (incluye p = 1, b ≤ 0) | `tests/controller/test_routing_services.py` | ✅ |
| TC-11 | Recomendada | Contrato de la API del Controller | `tests/controller/test_controller_api.py` | ✅ |
| TC-12 | Obligatoria | AST: controladores sin algoritmos ni acceso a datos | `tests/architecture/test_layer_rules.py` | ✅ |
| TC-13 | Recomendada | AST: servicios sin E/S directa | `tests/architecture/test_layer_rules.py` | ✅ |
| TC-14 | Recomendada | AST: el Router no calcula rutas | `tests/architecture/test_layer_rules.py` | ✅ |
| TC-15 | Recomendada | Fallo del DAO → 200 con `log_persisted: false` | `tests/router/test_forwarding_service.py` | ✅ |
| TC-16 | Recomendada | E2E con **dos procesos reales** | `tests/integration/test_end_to_end.py` | ✅ |
| TC-17 | Recomendada | Topologías válidas e inválidas; modo degradado y reintento | `tests/controller/test_controller_api.py` | ✅ |
| TC-18 | Extensión | p95 en 200 nodos / 1000 enlaces (protocolo reproducible) | `tests/performance/test_route_performance.py` | ✅ mediana p95 ≈ 12 ms (≤ 200 ms) |
| TC-19 | Extensión | 503 en ≤ timeout + 1 s; `/health` sigue en 200 | `tests/router/test_timeout.py` | ✅ |
| TC-20 | Recomendada | Concurrencia: ruta y versión de la misma instantánea | `tests/controller/test_concurrency.py` | ✅ |
| TC-21 | Extensión | Sustitución de `TopologyDAO` (fake vs JSON) | `tests/controller/test_topology_dao_contract.py` | ✅ |
| TC-22 | Extensión | Sustitución en el Router (fakes vs adaptadores reales) | `tests/router/test_substitution.py` | ✅ |
| TC-23 | Recomendada | Delegación MVC con servicios espía | `tests/architecture/test_mvc_delegation.py` | ✅ |
| TC-24 | Obligatoria | Persistencia de `UNREACHABLE`; errores sin `save()` | `tests/router/test_forwarding_service.py` | ✅ |
| TC-25 | Recomendada | Respuestas inesperadas del Controller (502/503/400) | `tests/router/test_http_controller_client.py` | ✅ |
| TC-26 | Extensión | Escritura parcial, fallo de `fsync`, escrituras concurrentes | `tests/router/test_log_dao_robustness.py` | ✅ |

**Sensibilidad de las pruebas:** se inyectaron a propósito dos defectos (un `import networkx` en un controlador y un `UNREACHABLE` sin `save()`); TC-12 y TC-24 fallaron como se esperaba y luego se revirtió el cambio.

El entorno de TC-18 queda en `tests/perf-environment.txt`. **Al ejecutar en su propia máquina, ese archivo se regenera; anoten si el portátil estaba conectado a la corriente.**

## 5. Estado de los requisitos

| Req. | Estado | Evidencia principal |
|---|---|---|
| FR-01 Carga de topología vía DAO | ✅ Cumplido | TC-17, TC-21 |
| FR-02 Topologías arbitrarias con NetworkX | ✅ Cumplido | TC-17 |
| FR-03 Dijkstra | ✅ Cumplido | TC-01, TC-20 |
| FR-04 Costos de enlace | ✅ Cumplido | TC-02, TC-10 |
| FR-05 API REST documentada | ✅ Cumplido | TC-11, `/docs` |
| FR-06 Fallo y restablecimiento | ✅ Cumplido | TC-03, TC-04, TC-11, TC-20 |
| FR-07 Router pide rutas por HTTP | ✅ Cumplido | TC-05, TC-19, TC-25 |
| FR-08 Simulación de reenvío | ✅ Cumplido | TC-06, TC-07, TC-23 |
| FR-09 Manejo de errores | ✅ Cumplido | TC-07, TC-11, TC-24, TC-25 |
| FR-10 Registro mediante DAO | ✅ Cumplido | TC-09, TC-15, TC-24, TC-26 |
| NFR-01…NFR-03 MVC / DAO / separación | ✅ Cumplido | TC-12, TC-13, TC-23, revisión RA |
| NFR-04 Contrato de API | ✅ Cumplido | TC-11, TC-16 |
| NFR-05 Configurabilidad | ✅ Cumplido | TC-16, TC-19 |
| NFR-06 Robustez | ✅ Cumplido | TC-07, TC-15, TC-17, TC-19 |
| NFR-07, NFR-09 DI y testabilidad | ✅ Cumplido | TC-08, TC-09, TC-21, TC-22 |
| NFR-08 Trazabilidad | ✅ Cumplido | `05` §3, tabla de la sección 4 |
| NFR-10 Rendimiento | ✅ Cumplido en el entorno registrado | TC-18 |
| NFR-11 Resiliencia | ✅ Cumplido | TC-19 |
| NFR-12 Consistencia | ✅ Cumplido | TC-20 |

La revisión arquitectónica manual RA-01…RA-10 está en [`docs/architecture-review.md`](docs/architecture-review.md) y **debe ser confirmada por ambos estudiantes**.

## 6. Decisiones de implementación y diferencias con la especificación

Ninguna cambia el contrato de API ni los requisitos. Se documentan para mantener la trazabilidad:

1. `JsonTopologyDAO` lanza `InvalidTopologyError` cuando el JSON es válido pero **su estructura** no lo es (falta `nodes`/`links`, atributos no numéricos). Es parte del *parseo* (A-11). Igual que los demás errores de carga, el resultado es `degraded` + 503 `TOPOLOGY_UNAVAILABLE`.
2. Puntos de inyección extra solo para pruebas, sin cambiar el comportamiento: `HttpControllerClient(transport=...)`, `JsonLinesForwardingLogDAO(opener=...)`, `ForwardingService(clock=...)` y `create_app(...)` con dobles opcionales.
3. `JsonLinesForwardingLogDAO.find_all()` informa las líneas omitidas en el atributo `last_skipped_lines` (A-16 pedía "contarlas").
4. `Route` también es inmutable (`frozen=True`); la especificación solo lo exigía para `Link`, `Topology` y `LinkChange`.
5. Los controladores se implementan como clases (`RouteController`, etc., como en el diagrama de clases de `02`) que la función de FastAPI crea por petición con el servicio inyectado por `Depends`.

## 7. Limitaciones conocidas

- Estado de enlaces en memoria: al reiniciar el Controller se pierde (decisión A-07).
- Un solo worker por app; la garantía de consistencia no aplica a varios procesos Controller (A-14).
- El log de reenvíos no admite varios procesos Router escribiendo el mismo archivo (01 §1.3).
- `scripts/demo.py` asume la topología de referencia de `controller/data/topology.json`.

## 8. Evidencias de la demo

- `demo-evidence/demo-log.txt`: salida completa de `scripts/demo.py` con ambas apps como procesos reales, incluida la prueba con DAO falso y el Controller apagado (503 y `/health` 200).
- `demo-evidence/controller-console.txt` y `router-console.txt`: logs de los dos procesos (se ve cada `GET /route` del Router al Controller).
- `demo-evidence/forwarding_log-demo.jsonl`: log de reenvíos generado por la demo (`DELIVERED` y `UNREACHABLE`).
- **Pendiente para el equipo:** agregar capturas de pantalla o un video corto ejecutando la demo en su máquina (el enunciado pide "images/video").

## 9. Registro de IA

- Sesión 1: `../prompts-session1.md`.
- Sesión 2: [`prompts-session2.md`](prompts-session2.md).
