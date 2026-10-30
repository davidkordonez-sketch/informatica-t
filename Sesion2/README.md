# Sesión 2 — Controlador y Enrutador SDN

Simulación SDN a nivel de aplicación con dos procesos Python independientes que se comunican por HTTP/JSON:

- **Controller** (`controller/`, puerto 8000): carga la topología desde JSON mediante `TopologyDAO`, administra el estado de los enlaces, calcula rutas con Dijkstra (NetworkX) y las expone por REST.
- **Router** (`router/`, puerto 8001): recibe paquetes simulados, **pide la ruta al Controller** (nunca la calcula), simula el reenvío salto a salto y registra cada resultado con `ForwardingLogDAO`.

Especificaciones de la Sesión 1 (v1.1): [`specs/`](specs/) (`01-requirements.md` … `06-test-specification.md`) y su registro de cambios en `specs/01-requirements.md` §9.
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

specs/  01-requirements · 02-static-architecture · 03-dynamic-architecture · 04-api-contract · 05-implementation-plan · 06-test-specification
prompts-session1.md · prompts-session2.md · README.md
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

En Windows PowerShell las comillas simples de `curl` no funcionan igual; usar `Invoke-RestMethod`, la consola visual o la página `/docs` (Swagger UI):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8001/packets -ContentType "application/json" -Body '{"packet_id":"pkt-1","src":"A","dst":"D","metric":"delay"}' | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://localhost:8000/links/fail -ContentType "application/json" -Body '{"node_a":"B","node_b":"D"}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/links/restore -ContentType "application/json" -Body '{"node_a":"B","node_b":"D"}'
Invoke-RestMethod "http://localhost:8000/route?src=A&dst=D&metric=bandwidth"
```

### Consola visual (recomendado para la demo)

Con las dos apps corriendo, abre **<http://localhost:8000/>** en el navegador. Verás la topología dibujada y podrás:

- **Ubicarte en un router:** clic en un router (origen, marcado «Tú») y clic en otro (destino). La consola pide `GET /route` y dibuja la ruta en azul, con el costo de cada salto.
- **Cambiar la métrica** (Retardo / Ancho de banda / Pérdida): la ruta se recalcula y las etiquetas de los enlaces cambian.
- **Fallar o restablecer un enlace:** clic en el enlace o botón «Fallar» / «Restablecer» en la lista (`POST /links/fail|restore`). Si el enlace estaba en la ruta, la consola muestra la ruta nueva y la anterior en naranja; si no queda camino, el destino se marca en rojo.
- **Enviar un paquete por el Router** (`POST /packets` al puerto 8001): un punto naranja recorre el `trace` salto a salto.
- **Ver la actividad:** cada llamada a la API queda en el panel «Actividad»; la versión de la topología y el estado de ambas apps se actualizan solos (también si haces cambios desde `/docs` o `scripts/demo.py`).

La consola es parte de la **Vista** (`controller/ui/`): no calcula rutas ni costos, solo dibuja lo que responde la API. La sirve `StaticFiles` desde `controller/main.py`, y el Router permite llamadas desde ella mediante CORS (variable `ROUTER_CORS_ORIGINS`, por defecto `http://localhost:8000,http://127.0.0.1:8000`).

### Demo guiada

Alternativa por línea de comandos a la consola visual. Con las dos apps corriendo, en una tercera terminal (desde `Sesion2`, con el entorno virtual activo):

```bash
python scripts/demo.py                    # demo completa; al final pide detener el Controller
python scripts/demo.py --no-interactive   # sin el paso del Controller detenido
```

Solo usa la biblioteca estándar. Ejecuta y verifica (`[OK]` / `[FALLÓ]`) el comportamiento en vivo obligatorio:

1. Paquete A→D: el Router pide la ruta al Controller → `DELIVERED`, ruta `[A,B,D]`, costo 20.
2. Falla B–D (enlace usado por la ruta) y reenvía → nueva ruta `[A,C,D]`, costo 25.
3. Falla también C–D → `UNREACHABLE` (se registra en el log).
4. Restablece C–D y B–D y repite → vuelve `[A,B,D]`; `GET /route` coincide con el Router.
5. Métrica alternativa `bandwidth` → `[A,C,D]`, costo 0,02.
6. Errores controlados: nodo inexistente (404 `NODE_NOT_FOUND`) y enlace ya fallado (409).
7. TC-08 y TC-09 con DAO falso, sin servidor HTTP.
8. Controller detenido → 503 `CONTROLLER_UNAVAILABLE` y `GET /health` del Router en 200.

Si una ejecución anterior dejó enlaces caídos, el script los restablece al empezar. La salida se guarda en `demo-evidence/demo-log.txt`. URL distintas: `--controller http://localhost:9000 --router http://localhost:9001`.

## 4. Pruebas

Desde la carpeta `Sesion2`:

```bash
pytest -v | tee tests/test-results.txt   # todas (27 casos, 79 pruebas con parametrizaciones)
# Windows PowerShell: python -m pytest -v 2>&1 | Out-File -Encoding utf8 tests\test-results.txt
pytest -m mandatory -v                   # solo las 11 obligatorias (TC-01…TC-09, TC-12, TC-24)
pytest -m "not integration and not perf" # rápidas, sin procesos reales
python tests/fixtures/generate_large_topology.py   # regenera el fixture de TC-18 (no hace falta)
```

**Resultado registrado** (`tests/test-results.txt`, Windows): **79 passed, 0 failed**.

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
| TC-27 | Recomendada | Consola visual servida en `/ui/`, solo usa la API REST; CORS del Router | `tests/controller/test_ui_console.py` | ✅ |

**Sensibilidad de las pruebas:** se inyectaron a propósito dos defectos (un `import networkx` en un controlador y un `UNREACHABLE` sin `save()`); TC-12 y TC-24 fallaron como se esperaba y luego se revirtió el cambio (procedimiento en `prompts-session2.md`, P2-04).

El entorno de TC-18 queda en `tests/perf-environment.txt` y se regenera en cada ejecución; el resultado depende del equipo donde se mida.

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

La revisión arquitectónica manual RA-01…RA-10 está en [`docs/architecture-review.md`](docs/architecture-review.md); cada fila lleva las iniciales del estudiante que la verificó.

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

Capturas en `demo-evidence/`, tomadas el 2026-10-27 desde `/docs` con el Controller y el Router como procesos independientes:

| Archivo | Qué muestra |
|---|---|
| `01-paquete-ABD.jpeg` | `POST /packets` A→D: `DELIVERED`, ruta `[A,B,D]` emitida por el Controller (costo 20, versión 1) y trace de 2 saltos. |
| `02-fallo-BD.png` | `POST /links/fail` B–D: enlace `failed`, `topology_version` 2. |
| `03-ruta-alternativa-ACD.png` | Nuevo paquete A→D: ruta alternativa `[A,C,D]`, costo 25, versión 2. |
| `04-restablecer-BD.png` | `POST /links/restore` B–D. |
| `05-ruta-original-ABD.png` | Tras restablecer, vuelve la ruta `[A,B,D]`. |
| `06-controller-caido-503.png` | Controller detenido: el Router responde 503 `CONTROLLER_UNAVAILABLE`. |
| `07-router-sigue-vivo.png` | Con el Controller detenido, `GET /health` del Router sigue respondiendo. |
| `08-prueba-dao-falso.png` | TC-08 y TC-09 con DAO falso, sin servidor HTTP: 2 passed. |
| `09-destino-inalcanzable.png` | Paquete A→F (nodo aislado): `UNREACHABLE` con `reason` `ROUTE_NOT_FOUND`, registrado en el log. |
| `prueba ruta.png` | Otra captura del paquete A→D entregado. |
| `prueba 76 est.png` | `pytest -v` antes de agregar TC-27: 76 passed. |

## 9. Registro de IA

- Sesión 1: [`prompts-session1.md`](prompts-session1.md).
- Sesión 2: [`prompts-session2.md`](prompts-session2.md).
