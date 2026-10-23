# 06 — Especificación de Pruebas

Herramientas: `pytest`, `FastAPI TestClient`, `httpx`, y `ast` (módulo estándar) para las pruebas de arquitectura. Resultados: `tests/test-results.txt` (se genera con `pytest -v | tee tests/test-results.txt`).

El enunciado exige **≥ 8 pruebas automatizadas exitosas**, incluidas TC-08 y TC-09. Este plan define 19.

## 1. Datos de prueba: topología de referencia (`tests/fixtures/topology.json`)

```json
{
  "nodes": ["A", "B", "C", "D", "E", "F"],
  "links": [
    {"node_a": "A", "node_b": "B", "delay_ms": 10, "bandwidth_mbps": 10,  "loss_prob": 0.01},
    {"node_a": "B", "node_b": "D", "delay_ms": 10, "bandwidth_mbps": 10,  "loss_prob": 0.01},
    {"node_a": "A", "node_b": "C", "delay_ms": 5,  "bandwidth_mbps": 100, "loss_prob": 0.05},
    {"node_a": "C", "node_b": "D", "delay_ms": 20, "bandwidth_mbps": 100, "loss_prob": 0.05},
    {"node_a": "D", "node_b": "E", "delay_ms": 5,  "bandwidth_mbps": 100, "loss_prob": 0.0}
  ]
}
```
`F` es un nodo **aislado** (sin enlaces).

### Costos esperados (A → D)
| Camino | `delay` | `bandwidth` (Σ 1/b) | `loss` (Σ −ln(1−p)) |
|---|---|---|---|
| A–B–D | **20** | 0,1 + 0,1 = 0,20 | 2 × 0,010050 = **0,020101** |
| A–C–D | 25 | 0,01 + 0,01 = **0,02** | 2 × 0,051293 = 0,102587 |
| **Ganador** | **A,B,D** | **A,C,D** | **A,B,D** |

## 2. Casos de prueba

| ID | Tipo | Req. | Escenario | Resultado esperado |
|---|---|---|---|---|
| **TC-01** | Unitaria | FR-03 | `RoutingService.find_route("A","D",DELAY)` sobre la topología de referencia; además `src == dst` | Ruta `[A,B,D]`, `total_cost` = 20, `hop_costs` = `[10,10]`; con `A→A`: `[A]`, costo 0 |
| **TC-02** | Unitaria | FR-04 | Consulta A→D con `delay`, `bandwidth` y `loss` | `[A,B,D]`/20; `[A,C,D]`/0,02; `[A,B,D]`/≈0,0201 (tolerancia 1e-4) |
| **TC-03** | Funcional | FR-06 | Fallar B–D y consultar A→D (`delay`) | Ruta `[A,C,D]`, costo 25; el enlace B–D no aparece; `topology_version` = 2 |
| **TC-04** | Funcional | FR-06 | Tras TC-03, restablecer B–D y consultar | Ruta `[A,B,D]`, costo 20; `topology_version` = 3 |
| **TC-05** | Integración | FR-07 | Router con servidor Controller simulado (stub HTTP o `httpx.MockTransport`) que registra peticiones; enviar paquete A→D | El stub recibe exactamente un `GET /route?src=A&dst=D&metric=delay`; el Router usa esa ruta (no calcula) |
| **TC-06** | Funcional | FR-08 | `ForwardingService` con `FakeRouteProvider` que devuelve `[A,B,D]` | `status` = DELIVERED; `trace` con 2 saltos (A→B, B→D) en orden; `hop` 1 y 2 |
| **TC-07** | Funcional | FR-03, FR-08, FR-09 | (a) Controller detenido; (b) destino aislado F; (c) nodo inexistente Z | (a) 503 `CONTROLLER_UNAVAILABLE`, Router sigue vivo; (b) 200 `UNREACHABLE`, `trace` vacío, `reason` = `ROUTE_NOT_FOUND`; (c) 404 `NODE_NOT_FOUND` |
| **TC-08** | Aislamiento DAO | NFR-07, NFR-09 | `RoutingService` con `TopologyService(FakeTopologyDAO)` en memoria, **sin** servidor HTTP ni archivos | Devuelve la ruta correcta; el fake registra la llamada a `load_topology()` |
| **TC-09** | Aislamiento DAO | FR-10, NFR-09 | `ForwardingService` con `FakeRouteProvider` y `MockForwardingLogDAO` | El mock recibe exactamente un `save(result)` con el resultado; la prueba corre sin archivos |
| **TC-10** | Unitaria | FR-04 | `LinkCostCalculator`: d=10 → 10; b=100 → 0,01; p=0,5 → ≈0,6931; p=0 → 0; p=1 → inutilizable; b=0 y b<0 → error; p>1 → error | Valores indicados; `INVALID_LINK_METRICS` en los casos de error; todo costo ≥ 0 |
| **TC-11** | API | FR-02, FR-05, FR-06, FR-09 | Casos contra los endpoints del Controller (TestClient) | Sin `src` → 400; `metric=foo` → 400; nodo Z → 404 `NODE_NOT_FOUND`; A→F → 404 `ROUTE_NOT_FOUND`; fail de enlace inexistente → 404 `LINK_NOT_FOUND`; fail dos veces → 409; restore de enlace activo → 409; todos con formato `{"error": {...}}` y respuestas 200 acordes con `04` |
| **TC-12** | Arquitectura | NFR-03, FR-03 | Análisis AST de `controller/controllers/` y `router/controllers/` | Cero imports de `networkx`, `heapq`, `json`, `pathlib`; cero llamadas a `open()`; sin imports de `dao/` concretos |
| **TC-13** | Arquitectura | NFR-02, FR-10 | Análisis AST de `controller/services/` y `router/services/` | Cero `open()`, `json.load/loads`, `pathlib`; sin imports de clases DAO concretas (solo interfaces) |
| **TC-14** | Arquitectura | FR-07 | Análisis AST de todo `router/` | Cero imports de `networkx`; sin funciones de camino mínimo |
| **TC-15** | Funcional | FR-10, NFR-06 | `ForwardingService` con DAO que lanza `PersistenceError` (o log en ruta sin permisos) | Respuesta 200 `DELIVERED`, `log_persisted` = false, `warnings` no vacío, proceso vivo |
| **TC-16** | Integración E2E | FR-01, FR-05–FR-08, NFR-04, NFR-05 | Levantar ambos procesos en puertos configurables (p. ej. 18000/18001): paquete A→D; fallar B–D; paquete; restablecer; paquete | Rutas `[A,B,D]` → `[A,C,D]` → `[A,B,D]`; trace coherente; una línea nueva por paquete en el log |
| **TC-17** | Funcional | FR-01, FR-02, NFR-06 | Controller con: archivo inexistente; JSON corrupto; enlace que referencia nodo inexistente; p fuera de rango | Proceso vivo; `/health` = `degraded`; `/route` → 503 `TOPOLOGY_UNAVAILABLE`; ninguna excepción sin controlar |
| **TC-18** | No funcional | NFR-10 | Topología sintética de 200 nodos y 1000 enlaces; 100 consultas `GET /route` | p95 ≤ 200 ms |
| **TC-19** | No funcional | NFR-11, FR-07 | Router apuntando a un Controller inexistente o con respuesta lenta (> timeout); `CONTROLLER_TIMEOUT_S` = 1 | 503 en ≤ timeout + 1 s; `GET /health` del Router = 200 inmediatamente después |

## 3. Matriz de cobertura

| Requisito | Cubierto por |
|---|---|
| FR-01 | TC-13, TC-16, TC-17 |
| FR-02 | TC-11, TC-17 |
| FR-03 | TC-01, TC-07, TC-11, TC-12 |
| FR-04 | TC-02, TC-10 |
| FR-05 | TC-11, TC-16 |
| FR-06 | TC-03, TC-04, TC-11 |
| FR-07 | TC-05, TC-14, TC-19 |
| FR-08 | TC-06, TC-07, TC-12 |
| FR-09 | TC-07, TC-11, TC-17, TC-19 |
| FR-10 | TC-09, TC-13, TC-15 |
| NFR-01 | Revisión de código + `02` |
| NFR-02 / NFR-03 | TC-13 / TC-12 |
| NFR-04 | TC-11, TC-16 |
| NFR-05 | TC-16, TC-19 |
| NFR-06 | TC-07, TC-15, TC-17, TC-19 |
| NFR-07 / NFR-09 | TC-08, TC-09 |
| NFR-08 | `05-implementation-plan.md` |
| NFR-10 / NFR-11 | TC-18 / TC-19 |

## 4. Reglas de ejecución y reporte

1. Las pruebas unitarias y de aislamiento (TC-01, 02, 06, 08, 09, 10) **no** deben necesitar red ni archivos reales.
2. Las pruebas de arquitectura (TC-12 a TC-14) son automatizadas, pero el enunciado también pide una **revisión de código fuente** que verifique MVC y que los controladores no tengan algoritmos de enrutamiento o reenvío; registrar esa revisión manual en el README.
3. Si una prueba falla, **se registra honestamente** en `tests/test-results.txt` y en el README; no se modifican los requisitos para hacerla pasar.
4. Comando sugerido: `pytest -v | tee tests/test-results.txt` (los TC-16 y TC-19 pueden marcarse como `integration` para ejecutarlos por separado).
