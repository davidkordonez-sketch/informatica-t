# 06 — Especificación de Pruebas

Versión 1.1 (2026-10-26). Cambios respecto a 1.0 registrados en `01-requirements.md` §9 (CH-01, CH-02, CH-03, CH-05, CH-06, CH-07, CH-08).

Herramientas: `pytest`, `FastAPI TestClient`, `httpx` (incluido `httpx.MockTransport`), `threading`/`concurrent.futures` para la prueba de concurrencia y `ast` (módulo estándar) para las pruebas de arquitectura. Resultados: `tests/test-results.txt` (se genera con `pytest -v | tee tests/test-results.txt`).

El enunciado exige **≥ 8 pruebas automatizadas exitosas**, incluidas TC-08 y TC-09. Este plan define **26** casos en tres niveles (ver `05` §1.2):

| Nivel | Casos | Cantidad |
|---|---|---|
| **Obligatoria** | TC-01…TC-09 (las del enunciado), TC-12, TC-24 | 11 |
| **Recomendada** | TC-10, TC-11, TC-13, TC-14, TC-15, TC-16, TC-17, TC-20, TC-23, TC-25 | 10 |
| **Extensión** | TC-18, TC-19, TC-21, TC-22, TC-26 | 5 |

Además, la **revisión arquitectónica manual** RA-01…RA-10 (§5) es obligatoria: el enunciado exige una revisión de código fuente que verifique MVC y que los controladores no contengan algoritmos de enrutamiento o reenvío.

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

### Dobles de prueba (fakes) compartidos
| Doble | Implementa | Comportamiento |
|---|---|---|
| `FakeTopologyDAO` | `TopologyDAO` | Devuelve una `Topology` en memoria (la de referencia por defecto); cuenta las llamadas a `load_topology()`; puede configurarse para lanzar un error de carga. |
| `FakeRouteProvider` | `RouteProvider` | Devuelve un `RouteInfo` fijo o lanza la excepción configurada (`RouteNotFoundError`, `NodeNotFoundError`, `ControllerUnavailableError`…); registra las llamadas. |
| `FakeForwardingLogDAO` | `ForwardingLogDAO` | Guarda los resultados en una lista en memoria; cuenta las llamadas a `save()`. |
| `FailingForwardingLogDAO` | `ForwardingLogDAO` | `save()` lanza `PersistenceError` (o, configurado, una excepción genérica como `RuntimeError`). |

## 2. Casos de prueba

| ID | Nivel | Tipo | Req. | Escenario | Resultado esperado |
|---|---|---|---|---|---|
| **TC-01** | Obligatoria | Unitaria | FR-03 | `RoutingService.find_route("A","D",DELAY)` sobre la topología de referencia; además `src == dst` | Ruta `[A,B,D]`, `total_cost` = 20, `hop_costs` = `[10,10]`, `topology_version` = 1; con `A→A`: `[A]`, costo 0, `hop_costs` = `[]` |
| **TC-02** | Obligatoria | Unitaria | FR-04 | Consulta A→D con `delay`, `bandwidth` y `loss` | `[A,B,D]`/20; `[A,C,D]`/0,02; `[A,B,D]`/≈0,0201 (tolerancia 1e-4) |
| **TC-03** | Obligatoria | Funcional | FR-06 | Fallar B–D y consultar A→D (`delay`) | Ruta `[A,C,D]`, costo 25; el enlace B–D no aparece; `topology_version` = 2 |
| **TC-04** | Obligatoria | Funcional | FR-06 | Tras TC-03, restablecer B–D y consultar | Ruta `[A,B,D]`, costo 20; `topology_version` = 3 |
| **TC-05** | Obligatoria | Integración | FR-07 | Router con `HttpControllerClient` sobre `httpx.MockTransport` que registra peticiones y responde un `RouteResponse` válido; enviar paquete A→D | El transporte recibe exactamente un `GET /route?src=A&dst=D&metric=delay`; el `trace` del Router coincide con la ruta recibida (no calcula) |
| **TC-06** | Obligatoria | Funcional | FR-08 | `ForwardingService` con `FakeRouteProvider` que devuelve `[A,B,D]` y `FakeForwardingLogDAO` | `status` = DELIVERED; `trace` con 2 saltos (A→B, B→D) en orden; `hop` 1 y 2 |
| **TC-07** | Obligatoria | Funcional | FR-03, FR-08, FR-09 | (a) Controller detenido; (b) destino aislado F; (c) nodo inexistente Z | (a) 503 `CONTROLLER_UNAVAILABLE`, Router sigue vivo; (b) 200 `UNREACHABLE`, `trace` vacío, `reason` = `ROUTE_NOT_FOUND`; (c) 404 `NODE_NOT_FOUND`. En (a) y (c) el DAO de log recibe **0** llamadas |
| **TC-08** | Obligatoria | Aislamiento DAO | NFR-07, NFR-09 | `RoutingService` con `TopologyService(FakeTopologyDAO)` en memoria, **sin** servidor HTTP ni archivos | Devuelve la ruta correcta; el fake registra **una** llamada a `load_topology()` aunque se hagan varias consultas |
| **TC-09** | Obligatoria | Aislamiento DAO | FR-10, NFR-09 | `ForwardingService` con `FakeRouteProvider` y `FakeForwardingLogDAO` (resultado DELIVERED) | El fake recibe exactamente un `save(result)` con el mismo `packet_id` y `status`; `log_persisted` = true; la prueba corre sin archivos |
| **TC-10** | Recomendada | Unitaria | FR-04 | `LinkCostCalculator`: d=10 → 10; b=100 → 0,01; p=0,5 → ≈0,6931; p=0 → 0; p=1 → inutilizable; b=0 y b<0 → error; p>1 → error | Valores indicados; `INVALID_LINK_METRICS` en los casos de error; todo costo ≥ 0 |
| **TC-11** | Recomendada | API | FR-02, FR-05, FR-06, FR-09 | Casos contra los endpoints del Controller (TestClient) | Sin `src` → 400; `metric=foo` → 400; nodo Z → 404 `NODE_NOT_FOUND`; A→F → 404 `ROUTE_NOT_FOUND`; F aparece en `GET /topology`; fail de enlace inexistente → 404 `LINK_NOT_FOUND`; fail dos veces → 409; restore de enlace activo → 409; todos con formato `{"error": {...}}` y respuestas 200 acordes con `04` |
| **TC-12** | Obligatoria | Arquitectura (estática) | NFR-03 | Análisis AST de `controller/controllers/` y `router/controllers/` | Cero imports de `networkx`, `heapq`, `json`, `pathlib`; cero llamadas a `open()`; sin imports de `dao/` concretos |
| **TC-13** | Recomendada | Arquitectura (estática) | NFR-02 | Análisis AST de `controller/services/` y `router/services/` | Cero `open()`, `json.load/loads`, `pathlib`; sin imports de clases DAO concretas (solo interfaces) |
| **TC-14** | Recomendada | Arquitectura (estática) | FR-07 | Análisis AST de todo `router/` | Cero imports de `networkx`; sin funciones de camino mínimo |
| **TC-15** | Recomendada | Funcional | FR-10, NFR-06 | `ForwardingService` con `FakeRouteProvider` (ruta válida) y `FailingForwardingLogDAO`: (a) lanza `PersistenceError`; (b) lanza `RuntimeError` | En ambos: respuesta `DELIVERED`, `log_persisted` = false, `warnings` = `[{"code": "PERSISTENCE_ERROR", ...}]`, no se relanza la excepción, proceso vivo (fila D2) |
| **TC-16** | Recomendada | Integración E2E | FR-01, FR-05–FR-08, NFR-04, NFR-05 | Levantar ambos procesos en puertos configurables (p. ej. 18000/18001): paquete A→D; fallar B–D; paquete; restablecer; paquete | Rutas `[A,B,D]` → `[A,C,D]` → `[A,B,D]`; trace coherente; versiones 1 → 2 → 3; **una** línea nueva por paquete en el log |
| **TC-17** | Recomendada | Funcional | FR-01, FR-02, NFR-06 | **Válidas:** cargar topologías lineal (A–B–C), anillo (4 nodos), malla completa (4 nodos) y con nodo aislado, solo cambiando `TOPOLOGY_FILE`. **Inválidas:** archivo inexistente; JSON corrupto; enlace que referencia nodo inexistente; p fuera de rango | Válidas: `/health` = `ok`, `topology_loaded: true`, `GET /topology` lista todos los nodos/enlaces y una consulta de ruta conocida devuelve el resultado esperado. Inválidas: proceso vivo; `/health` = `degraded`; `/route` → 503 `TOPOLOGY_UNAVAILABLE`; ninguna excepción sin controlar |
| **TC-18** | Extensión | No funcional | NFR-10 | Protocolo reproducible de §4 sobre `large_topology_200n_1000l.json` | Las 100 consultas medidas devuelven 200 y costo correcto; mediana de 3 repeticiones del p95 ≤ 200 ms; entorno registrado en `tests/perf-environment.txt` |
| **TC-19** | Extensión | No funcional | NFR-11, FR-07 | Router apuntando a un Controller inexistente o con respuesta lenta (> timeout); `CONTROLLER_TIMEOUT_S` = 1 | 503 en ≤ timeout + 1 s; `GET /health` del Router = 200 inmediatamente después |
| **TC-20** | Recomendada | Concurrencia | FR-03, FR-06, NFR-12 | `TopologyService(FakeTopologyDAO)` + `RoutingService`. **(a)** 8 hilos lectores hacen 200 consultas A→D (`delay`) cada uno mientras 1 hilo escritor alterna 100 veces `fail_link(B,D)` / `restore_link(B,D)` empezando por `fail`. Para forzar intercalado, `build_weighted_graph` puede envolverse en la prueba con una pausa de 1 ms. **(b)** 2 hilos ejecutan `fail_link(B,D)` a la vez (sincronizados con `threading.Barrier`), repetido 50 veces restaurando entre intentos | (a) Toda respuesta con versión **impar** es `[A,B,D]`/20 y toda respuesta con versión **par** es `[A,C,D]`/25 (G1); en cada hilo las versiones observadas no disminuyen (G4); versión final = 101 (G3); ninguna excepción. (b) En cada intento, exactamente un `LinkChange` y un `LinkAlreadyFailedError`, y la versión aumenta en 1 |
| **TC-21** | Extensión | Sustitución de interfaz | FR-01, NFR-02, NFR-07 | **Prueba de contrato de `TopologyDAO`** parametrizada con `FakeTopologyDAO` y `JsonTopologyDAO(tests/fixtures/topology.json)`: mismas consultas con las 3 métricas, fallo y restablecimiento | Resultados idénticos con ambas implementaciones (prueba que `TopologyService`/`RoutingService` no dependen de la implementación y que el fake es fiel); `JsonTopologyDAO` devuelve los 6 nodos y 5 enlaces del fixture con `version = 1` |
| **TC-22** | Extensión | Sustitución de interfaz | FR-07, FR-10, NFR-02, NFR-07 | Mismo escenario de `ForwardingService` (A→D entregado y A→F inalcanzable) con **(i)** `FakeRouteProvider` + `FakeForwardingLogDAO` y **(ii)** `HttpControllerClient` sobre `httpx.MockTransport` + `JsonLinesForwardingLogDAO(tmp_path)`; además, prueba de contrato de `ForwardingLogDAO` (guardar 2 resultados y leerlos con `find_all`) sobre ambas implementaciones de DAO | Resultados iguales en (i) y (ii), excepto `timestamp`; `find_all` devuelve los mismos registros en ambas implementaciones; los registros no contienen `log_persisted` ni `warnings` |
| **TC-23** | Recomendada | Delegación MVC | NFR-01, NFR-03, FR-05, FR-08 | Con `app.dependency_overrides`, reemplazar `RoutingService`, `TopologyService` y `ForwardingService` por **servicios espía** que devuelven valores fijos o lanzan excepciones de dominio; llamar a `GET /route`, `POST /links/fail` y `POST /packets` | Cada endpoint llama **una vez** al método esperado del servicio con los argumentos ya convertidos (p. ej. `Metric.DELAY`); la respuesta JSON es exactamente la serialización del valor fijo; una excepción de dominio del espía se traduce al HTTP del catálogo. Si un controlador calculara rutas o simulara saltos por su cuenta, la respuesta no coincidiría con el valor fijo |
| **TC-24** | Obligatoria | Funcional / persistencia | FR-08, FR-09, FR-10 | `ForwardingService` con: **(a)** `FakeRouteProvider` que lanza `RouteNotFoundError` + `FakeForwardingLogDAO`; **(b)** igual con `FailingForwardingLogDAO`; **(c)** proveedor que lanza `NodeNotFoundError`, `ControllerUnavailableError`, `ControllerTimeoutError` y `ControllerBadResponseError` + `FakeForwardingLogDAO` | (a) `UNREACHABLE`, `reason` = `ROUTE_NOT_FOUND`, **un** `save()` con `status` = UNREACHABLE, `log_persisted` = true (fila D3). (b) `UNREACHABLE`, `log_persisted` = false, aviso `PERSISTENCE_ERROR` (fila D4). (c) La excepción se propaga y `save()` recibe **0** llamadas (filas E1, E3–E6) |
| **TC-25** | Recomendada | Contrato / errores | FR-07, FR-09 | `HttpControllerClient` sobre `httpx.MockTransport` con respuestas: (a) 200 no JSON; (b) 200 sin `path`; (c) 200 con `path[-1] ≠ dst`; (d) 200 con `len(hop_costs) ≠ len(path)−1`; (e) 404 con `code = "FOO"`; (f) 503 `TOPOLOGY_UNAVAILABLE`; (g) 500; (h) 409; (i) 400 `INVALID_PARAMETER`. Luego las mismas respuestas a través de `POST /packets` con `FakeForwardingLogDAO` | (a)–(e) y (h) → 502 `CONTROLLER_BAD_RESPONSE` con `details.reason`; (f) y (g) → 503 `CONTROLLER_UNAVAILABLE` con `details.upstream_status` (y `upstream_code` en f); (i) → 400 con `details.source = "controller"`. En todos: formato único de error, 0 llamadas a `save()`, Router vivo |
| **TC-26** | Extensión | Persistencia (robustez) | FR-10, NFR-06 | `JsonLinesForwardingLogDAO(tmp_path)` con la escritura del archivo interceptada (`monkeypatch`) para que escriba la mitad de los bytes y lance `OSError`; después, una escritura normal; después, `find_all()`. Variante: `fsync` lanza `OSError` | `save()` lanza `PersistenceError` (no `OSError`); a través de `ForwardingService`, la respuesta tiene `log_persisted` = false; la segunda escritura queda en una línea propia y válida; `find_all()` devuelve 1 registro válido e informa 1 línea omitida, sin excepción. Variante `fsync`: `log_persisted` = false |

## 3. Matriz de cobertura *(SPDR-07)*

Clasificación: **P** = verificación primaria (ejecuta el comportamiento y comprueba un criterio de aceptación), **S** = verificación de soporte, **I** = inspección arquitectónica (estática o manual). Es la misma matriz de `05` §3.

| Requisito | Primaria (P) | Soporte (S) | Inspección (I) |
|---|---|---|---|
| FR-01 | TC-17, TC-21 | TC-08, TC-16 | TC-13, RA-03 |
| FR-02 | TC-17 | TC-11, TC-18 | — |
| FR-03 | TC-01, TC-20 | TC-07, TC-08, TC-11, TC-23 | TC-12, RA-02 |
| FR-04 | TC-02, TC-10 | — | — |
| FR-05 | TC-11 | TC-16, TC-23 | Inspección de `/docs` |
| FR-06 | TC-03, TC-04, TC-11, TC-20 | TC-16 | — |
| FR-07 | TC-05, TC-19, TC-25 | TC-16, TC-22 | TC-14, RA-09, RA-10 |
| FR-08 | TC-06, TC-07, TC-23 | TC-16, TC-24 | TC-12, RA-02 |
| FR-09 | TC-07, TC-11, TC-24, TC-25 | TC-15, TC-17, TC-19 | RA-06 |
| FR-10 | TC-09, TC-15, TC-24, TC-26 | TC-16, TC-22 | TC-13, RA-08 |
| NFR-01 | TC-23 | — | RA-01…RA-06 |
| NFR-02 | TC-21, TC-22 | TC-08, TC-09 | TC-13, RA-03 |
| NFR-03 | TC-23 | — | TC-12, RA-02 |
| NFR-04 | TC-11, TC-16 | TC-23, TC-25 | — |
| NFR-05 | TC-16, TC-19 | — | — |
| NFR-06 | TC-07, TC-15, TC-17, TC-19 | TC-25, TC-26 | — |
| NFR-07 | TC-08, TC-09 | TC-21, TC-22 | RA-04, RA-05 |
| NFR-08 | — | — | Revisión de `05` §3 |
| NFR-09 | TC-08, TC-09 | TC-21, TC-22, TC-24 | — |
| NFR-10 | TC-18 | — | — |
| NFR-11 | TC-19 | TC-07 (a) | — |
| NFR-12 | TC-20 | TC-03, TC-04 | RA-07 |

**Cobertura mínima garantizada solo con las pruebas obligatorias.** FR-01 (S: TC-08), FR-03 (P: TC-01), FR-04 (P: TC-02), FR-06 (P: TC-03, TC-04), FR-07 (P: TC-05), FR-08 (P: TC-06, TC-07), FR-09 (P: TC-07, TC-24), FR-10 (P: TC-09, TC-24), NFR-03 (I: TC-12), NFR-07/NFR-09 (P: TC-08, TC-09). Los requisitos que en ese escenario solo quedan con evidencia de soporte o inspección (FR-01, FR-02, FR-05, NFR-12…) dependen de las pruebas recomendadas; si no se implementan, se declara en el README.

## 4. Protocolo reproducible de rendimiento (TC-18) *(SPDR-05)*

| Elemento | Definición fija |
|---|---|
| **Fixture** | `tests/fixtures/large_topology_200n_1000l.json`, generado **una vez**, versionado en el repositorio y verificado por SHA-256 al inicio de la prueba (el hash se anota en `tests/perf-environment.txt`). La prueba **lee** el fixture; no lo regenera. |
| **Generador** (`tests/fixtures/generate_large_topology.py`) | Con `rng = random.Random(42)`: (1) nodos `N000`…`N199`; (2) **anillo** `N(i)`–`N((i+1) mod 200)` para i = 0…199 (200 enlaces, garantiza que el grafo es conexo); (3) mientras haya menos de 1000 enlaces: `i = rng.randrange(200)`, `j = rng.randrange(200)`; se descarta si `i = j` o si el par no ordenado ya existe; (4) los atributos se sortean **al crear cada enlace**, en este orden: `delay_ms = rng.randint(1, 50)`, `bandwidth_mbps = rng.choice([10, 100, 1000])`, `loss_prob = round(rng.uniform(0.0, 0.05), 4)`. Todos los enlaces son utilizables (p < 1). |
| **Consultas** | Con `rng_q = random.Random(4242)`: 110 pares `(src, dst)` con `src ≠ dst`; la métrica de la consulta k es `["delay", "bandwidth", "loss"][k mod 3]`. Las 10 primeras son **calentamiento** y no se miden; las 100 siguientes se miden. |
| **Ejecución** | En proceso con `TestClient` sobre la app del Controller real (`JsonTopologyDAO` apuntando al fixture), **un hilo**, secuencial, sin otros procesos pesados. Se mide con `time.perf_counter()` alrededor de cada `client.get("/route", ...)`. Así se mide el procesamiento del Controller sin variaciones de la red TCP. |
| **Corrección (condición previa)** | Cada consulta medida debe responder 200 **y** ser correcta: el `path` empieza en `src` y termina en `dst`, cada par consecutivo es un enlace activo, `sum(hop_costs) = total_cost` y `total_cost` coincide (tolerancia relativa 1e-9) con un **oráculo**: `networkx.dijkstra_path_length` sobre un grafo construido de forma independiente en la prueba con las fórmulas de `01` §3.2. Se compara el **costo** y no el camino, porque puede haber empates. Si una sola consulta falla, **la prueba falla**: ninguna respuesta incorrecta se excluye del cálculo. |
| **Estadístico** | p95 por el método *nearest-rank*: se ordenan los 100 tiempos y se toma el elemento en la posición ⌈0,95 × 100⌉ = 95 (índice 94). Se hacen **3 repeticiones** completas (cada una con su calentamiento). Criterio: **mediana de los 3 p95 ≤ 200 ms**. Se informan además p50 y máximo de cada repetición. |
| **Entorno registrado** (`tests/perf-environment.txt`) | Modelo de CPU, núcleos, RAM, sistema operativo, versión de Python, versiones de `fastapi`, `networkx`, `httpx`, `uvicorn`, `pydantic`; si el portátil estaba conectado a la corriente; SHA-256 del fixture; fecha y commit. |
| **Marcador** | `@pytest.mark.perf` (se ejecuta por separado: `pytest -m perf`). |

## 5. Revisión arquitectónica manual (RA) *(SPDR-06)*

Las pruebas AST (TC-12…TC-14) detectan imports y llamadas prohibidas, pero no garantizan por sí solas un MVC/DAO correcto. Por eso se complementan con (a) pruebas de **comportamiento** de la arquitectura — sustitución de interfaces (TC-08, TC-09, TC-21, TC-22) y delegación de controladores (TC-23) — y (b) esta **revisión manual cruzada**: A revisa el Router y B revisa el Controller (tarea T-18). El resultado se registra en `docs/architecture-review.md` con: ítem, archivo:línea revisado, resultado (OK / NO OK), observación, revisor y hash del commit.

| ID | Punto de revisión | Cómo se verifica | Relación |
|---|---|---|---|
| RA-01 | Cada módulo está en la capa correcta (`models`, `schemas`, `controllers`, `services`, `dao`, `clients`). | Recorrer el árbol de carpetas y las clases de cada archivo contra `02` §5. | NFR-01 |
| RA-02 | Cada manejador HTTP solo hace: convertir la entrada → llamar **un** método de servicio → serializar la salida. No hay bucles sobre nodos/enlaces, cálculo de costos ni construcción de `trace`. | Leer cada función de `controllers/` en ambas apps. | NFR-03, FR-03, FR-08, R1 |
| RA-03 | Toda lectura/escritura de archivos está en `dao/` concretos; servicios y controladores no tocan el sistema de archivos. | Buscar `open`, `Path`, `json.` fuera de `dao/` y revisar cada aparición. | NFR-02, R2 |
| RA-04 | Los servicios reciben sus dependencias por constructor y sus anotaciones de tipo son las **interfaces** (`TopologyDAO`, `ForwardingLogDAO`, `RouteProvider`). | Leer los `__init__` de los servicios. | NFR-07, R4 |
| RA-05 | Solo `main.py` instancia DAO y clientes concretos; los controladores obtienen servicios con `Depends`. | Buscar `JsonTopologyDAO(`, `JsonLinesForwardingLogDAO(`, `HttpControllerClient(` en todo el código. | NFR-07, R5 |
| RA-06 | Las excepciones de dominio no conocen HTTP; solo el `ErrorHandler` asigna códigos de estado; no hay `HTTPException` en servicios. | Leer `exceptions.py` y buscar `status_code`/`HTTPException` en `services/`. | FR-09, R6 |
| RA-07 | `Link`, `Topology` y `LinkChange` son inmutables (`frozen=True`); `current` solo se reasigna dentro de `write_lock`; `find_route` llama a `get_snapshot()` una sola vez; no se mantiene el lock durante Dijkstra. | Leer `models/` y `topology_service`/`routing_service`. | NFR-12, R7, R8 |
| RA-08 | `ForwardingService` llama a `save()` en las ramas `DELIVERED` y `UNREACHABLE` y en ninguna rama de error; captura cualquier excepción de `save()`; el DAO serializa antes de escribir, usa el lock, una sola escritura y `fsync`. | Leer `forwarding_service` y `jsonlines_forwarding_log_dao`. | FR-10, R9, R10 |
| RA-09 | `HttpControllerClient` implementa todas las filas de la tabla de `04` §3 regla 4 y nunca devuelve un `RouteInfo` sin validar. | Comparar el código fila por fila con la tabla. | FR-07, FR-09, R11 |
| RA-10 | El Router no importa `networkx` ni calcula costos o caminos. | Lectura de `router/` (complementa TC-14). | FR-07, R3 |

## 6. Reglas de ejecución y reporte

1. Las pruebas unitarias, de aislamiento y de concurrencia (TC-01, 02, 06, 08, 09, 10, 15, 20, 24) **no** deben necesitar red ni archivos reales. TC-21, TC-22 y TC-26 usan solo `tmp_path` y fixtures del repositorio.
2. Cada prueba lleva un marcador de nivel (`@pytest.mark.mandatory`, `@pytest.mark.recommended`, `@pytest.mark.extension`) y, si corresponde, `integration` o `perf`. Comandos: `pytest -m mandatory -v` (verificación mínima en H1/H2) y `pytest -v | tee tests/test-results.txt` (entrega).
3. Si una prueba falla, **se registra honestamente** en `tests/test-results.txt` y en el README; no se modifican los requisitos para hacerla pasar. Las pruebas recomendadas o de extensión que no se alcancen a implementar se listan en el README como "no implementadas", con el requisito afectado.
4. La revisión RA-01…RA-10 se ejecuta en el bloque 7 de la Sesión 2 (`05` §1.3) y su resultado se enlaza desde el README.
5. TC-18 registra su entorno en `tests/perf-environment.txt`; sin ese archivo el resultado de rendimiento no se considera válido.
