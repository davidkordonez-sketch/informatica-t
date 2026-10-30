# Plan de Pruebas de Requisitos

*Documento de la Sesión 2 elaborado con la estructura de la plantilla "Requirements Test Plan Template". Detalle técnico de cada caso: `specs/06-test-specification.md` (v1.1).*

| Campo | Descripción |
|---|---|
| Curso | Informática para Telecomunicaciones |
| Programa | Ingeniería de Telecomunicaciones |
| Proyecto | Controlador y Enrutador SDN (simulación a nivel de aplicación) |
| Nombre del equipo | _completar_ |
| Integrantes | Estudiante A (Controller): _completar_ · Estudiante B (Router): _completar_ |
| Profesor | _completar_ |
| Fecha | 2026-10-26 |
| Versión | 1.0 |

## 1. Objetivo del plan de pruebas

Verificar que el sistema SDN cumple los requisitos definidos en `01-requirements.md`. Las pruebas validan la carga de la topología, el cálculo de rutas con Dijkstra y sus tres métricas, el fallo y el restablecimiento de enlaces, la obtención de rutas por HTTP desde el Router, la simulación del reenvío, el registro de resultados, el manejo de errores y el cumplimiento de la arquitectura MVC/DAO.

## 2. Alcance de las pruebas

| Incluido en las pruebas | Estado |
|---|---|
| Aplicación Controller | Sí |
| Aplicación Router | Sí |
| Protocolo de comunicación (HTTP REST) | Sí |
| Formato de mensajes JSON (contrato de `04-api-contract.md`) | Sí |
| Almacenamiento de la topología (`TopologyDAO`) | Sí |
| Algoritmo de enrutamiento (Dijkstra y métricas) | Sí |
| Fallo y restablecimiento de enlaces | Sí |
| Simulación del reenvío y registro (`ForwardingLogDAO`) | Sí |
| Manejo de errores | Sí |
| Arquitectura MVC/DAO (pruebas AST y de sustitución) | Sí |
| Concurrencia y rendimiento | Sí |

## 3. Entorno de pruebas

| Elemento | Entorno donde se registraron los resultados | Entorno del equipo (completar al ejecutar) |
|---|---|---|
| Sistema operativo | Linux 6.18 (x86_64) | _ej. Windows 11_ |
| Versión de Python | 3.13.17 | _completar_ |
| Protocolo de comunicación | HTTP/1.1 (REST) con JSON | igual |
| Librerías usadas | FastAPI 0.161.1, Uvicorn 0.54.0, Pydantic 2.13.5, NetworkX 3.7, httpx 0.28.1, pytest 9.1.1 | `pip install -r requirements.txt` |
| Número de aplicaciones Router | 1 | 1 |
| Dirección IP del Controller | 127.0.0.1 | 127.0.0.1 |
| Puerto del Controller | 8000 (TC-16 usa puertos libres aleatorios) | 8000 |
| Puerto del Router | 8001 | 8001 |
| Comando de ejecución | `pytest -v \| tee tests/test-results.txt` | igual |

## 4. Plantilla de caso de prueba

| Campo | Descripción |
|---|---|
| ID del caso | TC-XX |
| Requisito relacionado | FR-XX o NFR-XX |
| Nombre | Nombre corto de la prueba |
| Objetivo | Qué verifica la prueba |
| Precondiciones | Condiciones necesarias antes de ejecutar |
| Datos de entrada | Datos usados en la prueba |
| Pasos | Pasos ordenados para ejecutar la prueba |
| Resultado esperado | Comportamiento correcto del sistema |
| Resultado real | Comportamiento observado |
| Estado | Aprobado / Fallido |
| Evidencia | Captura, log, archivo o salida de terminal |
| Observaciones | Comentarios adicionales |

**Datos de prueba comunes.** Topología de referencia `tests/fixtures/topology.json`: nodos A–F; enlaces A–B (10 ms, 10 Mbps, p = 0,01), B–D (10, 10, 0,01), A–C (5, 100, 0,05), C–D (20, 100, 0,05) y D–E (5, 100, 0). F es un nodo aislado.

## 5. Casos de prueba funcionales

Se documentan en detalle las **11 pruebas obligatorias**: TC-01 a TC-09, que son las que exige el enunciado, más TC-12 y TC-24. Las otras 15 se resumen en la sección 5.12 con los mismos campos.

### TC-01: Dijkstra elige el camino de costo mínimo

| Campo | Descripción |
|---|---|
| ID del caso | TC-01 |
| Requisito relacionado | FR-03 |
| Nombre | Dijkstra elige el camino de costo mínimo |
| Objetivo | Verificar que `RoutingService` calcula la ruta óptima y el caso origen = destino. |
| Precondiciones | Topología de referencia cargada mediante `FakeTopologyDAO`. |
| Datos de entrada | Consulta A→D con métrica `delay`; consulta A→A. |
| Pasos | 1. Crear `TopologyService` y `RoutingService`. 2. Ejecutar `find_route("A","D",DELAY)`. 3. Ejecutar `find_route("A","A",DELAY)`. |
| Resultado esperado | A→D: ruta `[A,B,D]`, costo 20, costos por salto `[10,10]`, versión 1. A→A: `[A]`, costo 0. |
| Resultado real | A→D: `[A,B,D]`, costo 20.0, `[10.0, 10.0]`, versión 1. A→A: `[A]`, costo 0.0. |
| Estado | Aprobado |
| Evidencia | `tests/controller/test_routing_services.py::test_tc01_…` en `tests/test-results.txt` |
| Observaciones | — |

### TC-02: Se soportan las tres métricas

| Campo | Descripción |
|---|---|
| ID del caso | TC-02 |
| Requisito relacionado | FR-04 |
| Nombre | Retardo, inverso del ancho de banda y pérdida |
| Objetivo | Verificar que cada métrica elige la ruta que le corresponde. |
| Precondiciones | Topología de referencia cargada. |
| Datos de entrada | Consulta A→D con `delay`, `bandwidth` y `loss`. |
| Pasos | 1. Ejecutar la consulta con cada métrica. 2. Comparar ruta y costo con la tabla de `06` §1. |
| Resultado esperado | `delay`: `[A,B,D]` con costo 20. `bandwidth`: `[A,C,D]` con costo 0,02. `loss`: `[A,B,D]` con costo ≈ 0,0201. |
| Resultado real | `[A,B,D]`/20.0; `[A,C,D]`/0.02; `[A,B,D]`/0.020101. |
| Estado | Aprobado |
| Evidencia | `test_tc02_all_three_metrics_supported[…]` (3 variantes) |
| Observaciones | Muestra que `1/b` prefiere enlaces anchos aunque tengan más retardo. |

### TC-03: Un enlace fallado se excluye de las rutas

| Campo | Descripción |
|---|---|
| ID del caso | TC-03 |
| Requisito relacionado | FR-06 |
| Nombre | Enlace fallado excluido |
| Objetivo | Verificar que, tras fallar B–D, Dijkstra ya no usa ese enlace. |
| Precondiciones | Topología de referencia en versión 1. |
| Datos de entrada | `fail_link("B","D")`; consulta A→D con `delay`. |
| Pasos | 1. Fallar B–D. 2. Consultar A→D. |
| Resultado esperado | Versión 2; ruta `[A,C,D]` con costo 25; B–D no aparece en la ruta. |
| Resultado real | Versión 2; `[A,C,D]`, costo 25.0. |
| Estado | Aprobado |
| Evidencia | `test_tc03_…`; también en vivo en `demo-evidence/02-fallo-BD.png` y `03-ruta-alternativa-ACD.png` |
| Observaciones | — |

### TC-04: Restablecer un enlace actualiza las rutas

| Campo | Descripción |
|---|---|
| ID del caso | TC-04 |
| Requisito relacionado | FR-06 |
| Nombre | Restablecimiento de enlace |
| Objetivo | Verificar que, al restablecer B–D, vuelve la ruta original. |
| Precondiciones | B–D fallado (versión 2). |
| Datos de entrada | `restore_link("D","B")` (en orden invertido a propósito); consulta A→D. |
| Pasos | 1. Fallar B–D. 2. Restablecer D–B. 3. Consultar A→D. |
| Resultado esperado | Versión 3; ruta `[A,B,D]` con costo 20. |
| Resultado real | Versión 3; `[A,B,D]`, costo 20.0. |
| Estado | Aprobado |
| Evidencia | `test_tc04_…`; demo, paso 4c |
| Observaciones | Confirma que el orden de los nodos no importa (grafo no dirigido, A-01). |

### TC-05: El Router obtiene la ruta por HTTP

| Campo | Descripción |
|---|---|
| ID del caso | TC-05 |
| Requisito relacionado | FR-07 |
| Nombre | Ruta obtenida por HTTP, no calculada en el Router |
| Objetivo | Verificar que el Router pide la ruta con `GET /route` y usa exactamente la que recibe. |
| Precondiciones | Router con `HttpControllerClient` conectado a un Controller simulado (`httpx.MockTransport`) que registra las peticiones. |
| Datos de entrada | Paquete `{packet_id: "pkt-1", src: "A", dst: "D", metric: "delay"}`. El stub devuelve a propósito una ruta "rara": `[A,C,E,D]`, versión 7. |
| Pasos | 1. Enviar `POST /packets`. 2. Revisar las peticiones registradas. 3. Revisar el `trace`. |
| Resultado esperado | Exactamente un `GET /route?src=A&dst=D&metric=delay`; el `trace` sigue `[A,C,E,D]`. |
| Resultado real | 1 petición `GET /route` con esos parámetros; `trace` A→C, C→E, E→D; versión 7. |
| Estado | Aprobado |
| Evidencia | `tests/router/test_http_controller_client.py::test_tc05_…` |
| Observaciones | Si el Router calculara su propia ruta, no coincidiría con la del stub. |

### TC-06: El trace del reenvío es válido

| Campo | Descripción |
|---|---|
| ID del caso | TC-06 |
| Requisito relacionado | FR-08 |
| Nombre | Trace salto a salto |
| Objetivo | Verificar que `ForwardingService` produce un registro por salto, en orden. |
| Precondiciones | `FakeRouteProvider` que devuelve `[A,B,D]`. |
| Datos de entrada | Paquete A→D. |
| Pasos | 1. Ejecutar `forward_packet`. 2. Revisar `status` y `trace`. |
| Resultado esperado | `DELIVERED`; saltos (1, A→B) y (2, B→D), ambos `FORWARDED`. |
| Resultado real | Igual al esperado. |
| Estado | Aprobado |
| Evidencia | `test_tc06_…` |
| Observaciones | — |

### TC-07: Controller caído, destino inalcanzable y nodo inexistente

| Campo | Descripción |
|---|---|
| ID del caso | TC-07 |
| Requisito relacionado | FR-03, FR-08, FR-09, NFR-06 |
| Nombre | Manejo limpio de fallos |
| Objetivo | Verificar los tres casos de error esperados y que el Router sigue vivo. |
| Precondiciones | (a) Router apuntando a un puerto sin Controller. (b, c) Router conectado a un Controller real en proceso. |
| Datos de entrada | (a) Paquete A→D. (b) Paquete A→F. (c) Paquete A→Z. |
| Pasos | 1. Enviar cada paquete. 2. Revisar el código HTTP y el cuerpo. 3. Consultar `GET /health` del Router. 4. Contar las escrituras en el log. |
| Resultado esperado | (a) 503 `CONTROLLER_UNAVAILABLE` y `/health` en 200. (b) 200 `UNREACHABLE`, `trace` vacío, `reason: ROUTE_NOT_FOUND`. (c) 404 `NODE_NOT_FOUND`. Solo (b) se registra en el log. |
| Resultado real | Igual al esperado; el log recibió 0 escrituras en (a) y (c), y 1 en (b). |
| Estado | Aprobado |
| Evidencia | `tests/router/test_error_scenarios.py` (4 pruebas); demo, pasos 3d y 6 |
| Observaciones | También se verificó la validación de formato (campos vacíos, métrica inválida → 400). |

### TC-08: RoutingService con un TopologyDAO falso

| Campo | Descripción |
|---|---|
| ID del caso | TC-08 |
| Requisito relacionado | NFR-07, NFR-09 |
| Nombre | Aislamiento del DAO del Controller |
| Objetivo | Verificar que `RoutingService` funciona sin servidor HTTP ni archivos, con un DAO inyectado. |
| Precondiciones | `FakeTopologyDAO` en memoria que cuenta las llamadas a `load_topology()`. |
| Datos de entrada | Consultas A→D, A→E, A→Z y A→F. |
| Pasos | 1. Inyectar el fake en `TopologyService`. 2. Ejecutar las consultas. 3. Revisar el contador del fake. |
| Resultado esperado | Rutas correctas; `NODE_NOT_FOUND` para Z; `ROUTE_NOT_FOUND` para F; una sola llamada a `load_topology()`. |
| Resultado real | Igual al esperado (`load_calls == 1`). |
| Estado | Aprobado |
| Evidencia | `test_tc08_…`; ejecutada en vivo en `demo-evidence/08-prueba-dao-falso.png` |
| Observaciones | Es la prueba que pide mostrar el enunciado en la demo. |

### TC-09: ForwardingService con su DAO de log

| Campo | Descripción |
|---|---|
| ID del caso | TC-09 |
| Requisito relacionado | FR-10, NFR-09 |
| Nombre | Aislamiento del DAO del Router |
| Objetivo | Verificar que `ForwardingService` guarda el resultado mediante el DAO inyectado y se prueba sin archivos. |
| Precondiciones | `FakeRouteProvider` y `FakeForwardingLogDAO` en memoria. |
| Datos de entrada | Paquete `pkt-001` A→D. |
| Pasos | 1. Ejecutar `forward_packet`. 2. Revisar lo que recibió el fake. |
| Resultado esperado | Exactamente un `save()` con `packet_id = pkt-001` y `status = DELIVERED`; `log_persisted = true`. |
| Resultado real | Igual al esperado. |
| Estado | Aprobado |
| Evidencia | `test_tc09_…`; también en la demo |
| Observaciones | — |

### TC-12: Los controladores HTTP no contienen algoritmos ni acceso a datos

| Campo | Descripción |
|---|---|
| ID del caso | TC-12 |
| Requisito relacionado | NFR-03 |
| Nombre | Prueba de arquitectura (AST) de los controladores |
| Objetivo | Verificar que `controllers/` de ambas apps no importa `networkx`, `heapq`, `json` ni `pathlib`, no llama a `open()` y no importa la capa DAO. |
| Precondiciones | Código fuente disponible. |
| Datos de entrada | Archivos `controller/controllers/*.py` y `router/controllers/*.py`. |
| Pasos | 1. Analizar cada archivo con el módulo `ast`. 2. Listar las violaciones. |
| Resultado esperado | Lista de violaciones vacía. |
| Resultado real | Vacía. Además, al **inyectar a propósito** un `import networkx` en un controlador, la prueba falló como se esperaba (y luego se revirtió). |
| Estado | Aprobado |
| Evidencia | `tests/architecture/test_layer_rules.py::test_tc12_…` |
| Observaciones | Se complementa con TC-23 (comportamiento) y la revisión manual RA. |

### TC-24: Persistencia de resultados UNREACHABLE y ramas de error

| Campo | Descripción |
|---|---|
| ID del caso | TC-24 |
| Requisito relacionado | FR-08, FR-09, FR-10 |
| Nombre | Persistencia en todos los resultados |
| Objetivo | Verificar la tabla de decisión de `01` §7.2: `UNREACHABLE` también se guarda y los errores no se guardan. |
| Precondiciones | `ForwardingService` con fakes. |
| Datos de entrada | (a) Proveedor que lanza `RouteNotFoundError` y DAO correcto. (b) Igual, con un DAO que falla. (c) Proveedor que lanza `NodeNotFound`, `ControllerUnavailable`, `ControllerTimeout` o `ControllerBadResponse`. |
| Pasos | 1. Ejecutar `forward_packet` en cada escenario. 2. Revisar el resultado y las llamadas a `save()`. |
| Resultado esperado | (a) `UNREACHABLE`, 1 `save()`, `log_persisted = true`. (b) `UNREACHABLE`, `log_persisted = false` y aviso `PERSISTENCE_ERROR`. (c) La excepción se propaga y hay 0 llamadas a `save()`. |
| Resultado real | Igual al esperado en los 6 escenarios. Al eliminar a propósito el `save()` de la rama `UNREACHABLE`, la prueba falló (y luego se revirtió). |
| Estado | Aprobado |
| Evidencia | `tests/router/test_forwarding_service.py::test_tc24…` |
| Observaciones | Prueba agregada por la corrección SPDR-01. |

### 5.12 Resumen de los demás casos (recomendados y de extensión)

| ID | Req. | Objetivo | Resultado esperado | Resultado real | Estado | Evidencia |
|---|---|---|---|---|---|---|
| TC-10 | FR-04 | Costos de `LinkCostCalculator` | d = 10 → 10; b = 100 → 0,01; p = 0,5 → 0,6931; p = 1 inutilizable; b ≤ 0 → error | Igual; además, un enlace con p = 1 se excluye en las 3 métricas | Aprobado | `test_tc10_…` (2) |
| TC-11 | FR-02, FR-05, FR-06, FR-09 | Contrato de la API del Controller | Respuestas 200 según `04`; 400/404/409 con formato único de error | Igual | Aprobado | `test_tc11_…` |
| TC-13 | NFR-02 | AST: servicios sin E/S directa | 0 violaciones | 0 | Aprobado | `test_tc13_…` |
| TC-14 | FR-07 | AST: el Router no calcula rutas | 0 imports de `networkx` ni funciones de camino mínimo | 0 | Aprobado | `test_tc14_…` |
| TC-15 | FR-10, NFR-06 | Fallo del DAO al guardar un `DELIVERED` | 200 `DELIVERED`, `log_persisted: false`, aviso, sin reintento | Igual con `PersistenceError` y con `RuntimeError` | Aprobado | `test_tc15_…` (2) |
| TC-16 | FR-01, FR-05…FR-08 | E2E con dos procesos reales | Rutas `[A,B,D]` → `[A,C,D]` → `[A,B,D]`, versiones 1 → 2 → 3, una línea de log por paquete | Igual | Aprobado | `test_tc16_…`; `demo-evidence/` |
| TC-17 | FR-01, FR-02, NFR-06 | Topologías válidas e inválidas | Válidas cargan; inválidas → `degraded` y 503; reintento al aparecer el archivo | Igual en 4 válidas, 7 inválidas y el reintento | Aprobado | `test_tc17_…` (12) |
| TC-18 | NFR-10 | Rendimiento en 200 nodos y 1000 enlaces | Mediana del p95 ≤ 200 ms con 100 consultas correctas | p95 = 12,04 / 8,68 / 11,62 ms; mediana 11,62 ms | Aprobado | `tests/perf-environment.txt` |
| TC-19 | NFR-11 | Controller lento o inexistente | 503 en ≤ timeout + 1 s; `/health` en 200 | Igual (timeout de 1 s) | Aprobado | `test_tc19_…` (2) |
| TC-20 | NFR-12 | Concurrencia: ruta y versión del mismo estado | 0 respuestas incoherentes; versión final 101; un 200 y un 409 en `fail` simultáneos | Igual (1600 consultas, 100 cambios; 50 intentos simultáneos) | Aprobado | `test_tc20…` (2) |
| TC-21 | FR-01, NFR-02 | Sustitución de `TopologyDAO` | Resultados idénticos con el DAO falso y con el DAO JSON | Igual | Aprobado | `test_tc21_…` (4) |
| TC-22 | FR-07, FR-10 | Sustitución en el Router | Resultados idénticos con fakes y con adaptadores reales | Igual | Aprobado | `test_tc22_…` (3) |
| TC-23 | NFR-01, NFR-03 | Delegación MVC con servicios espía | Cada endpoint llama una vez al servicio y devuelve su valor sin cambios | Igual en `/route`, `/links/fail` y `/packets` | Aprobado | `test_tc23_…` (3) |
| TC-25 | FR-07, FR-09 | Respuestas inesperadas del Controller | 502/503/400 según la tabla; 0 escrituras en el log | Igual en 16 casos (incluye fallos de red: conexión rechazada, timeout de conexión y timeout de lectura) | Aprobado | `test_tc25_…` (17) |
| TC-27 | FR-05 (Vista) | Consola visual del Controller | Se sirve en `/ui/`; solo usa la API REST; el Router acepta su origen y rechaza otros | Igual; además se probó en un navegador real (Chromium) con ambas apps corriendo | Aprobado | `tests/controller/test_ui_console.py` (3) |
| TC-26 | FR-10, NFR-06 | Escritura parcial y fallo de `fsync` | `PersistenceError`; fragmento aislado; `find_all` lo omite | Igual; además, 50 escrituras simultáneas dan 50 líneas completas | Aprobado | `test_tc26_…` (3) |

## 6. Matriz de trazabilidad de requisitos

| ID requisito | Descripción | Casos de prueba | Estado de las pruebas |
|---|---|---|---|
| FR-01 | Carga de topología mediante DAO | TC-17, TC-21 (+ TC-08, TC-16) | Aprobado |
| FR-02 | Topologías arbitrarias con NetworkX | TC-17 (+ TC-11, TC-18) | Aprobado |
| FR-03 | Cálculo de rutas con Dijkstra | TC-01, TC-20 (+ TC-07, TC-08, TC-11) | Aprobado |
| FR-04 | Costos de enlace (3 métricas) | TC-02, TC-10 | Aprobado |
| FR-05 | API REST del Controller | TC-11 (+ TC-16, TC-23) | Aprobado |
| FR-06 | Fallo y restablecimiento de enlaces | TC-03, TC-04, TC-11, TC-20 | Aprobado |
| FR-07 | El Router pide rutas por HTTP | TC-05, TC-19, TC-25 (+ TC-14) | Aprobado |
| FR-08 | Simulación del reenvío | TC-06, TC-07, TC-23 (+ TC-24) | Aprobado |
| FR-09 | Manejo de errores | TC-07, TC-11, TC-24, TC-25 | Aprobado |
| FR-10 | Registro mediante DAO | TC-09, TC-15, TC-24, TC-26 | Aprobado |
| NFR-01…NFR-03 | MVC, DAO, separación de lógica | TC-12, TC-13, TC-23 + revisión RA | Aprobado (revisión RA pendiente de firma) |
| NFR-04, NFR-05 | Contrato y configurabilidad | TC-11, TC-16, TC-19 | Aprobado |
| NFR-06 | Robustez | TC-07, TC-15, TC-17, TC-19 | Aprobado |
| NFR-07, NFR-09 | Inyección de dependencias y testabilidad | TC-08, TC-09, TC-21, TC-22 | Aprobado |
| NFR-10 | Rendimiento | TC-18 | Aprobado |
| NFR-11 | Resiliencia | TC-19 | Aprobado |
| NFR-12 | Consistencia | TC-20 | Aprobado |

Entre paréntesis van las pruebas de soporte. La clasificación completa (primaria, de soporte o de inspección) está en `05-implementation-plan.md` §3.

## 7. Resumen de la ejecución

| Total de casos de prueba | Aprobados | Fallidos | Pendientes | Porcentaje de éxito |
|---|---|---|---|---|
| 27 casos (79 pruebas automáticas contando las variantes parametrizadas) | 27 casos / 79 pruebas | 0 | 0 | 100 % |

Por nivel: obligatorias 11/11 (21 pruebas), recomendadas 11/11 (45 pruebas) y extensión 5/5 (13 pruebas). Tiempo total de ejecución: ≈ 8 s.

## 8. Informe final de pruebas

Las 26 pruebas definidas en el plan se implementaron y aprobaron, incluidas TC-08 y TC-09, que exige el enunciado, y las de arquitectura (TC-12, TC-13, TC-14 y TC-23). Para comprobar que las pruebas detectan defectos reales, se inyectaron dos fallas a propósito (un `import networkx` en un controlador y la eliminación del `save()` de la rama `UNREACHABLE`): TC-12 y TC-24 fallaron como se esperaba, y después se revirtieron los cambios. Durante el proceso aparecieron dos problemas, en una prueba y en el guion de la demo (ISS-01 e ISS-02), ambos ya corregidos. Antes de la entrega final falta capturar evidencia visual de la demo y completar la revisión arquitectónica firmada por ambos integrantes.

| ID problema | Descripción | Severidad | Requisito relacionado | Corrección |
|---|---|---|---|---|
| ISS-01 | La prueba TC-26 llamaba dos veces al DAO roto sobre el mismo archivo y esperaba 1 línea corrupta en vez de 2. El defecto estaba en la prueba, no en el DAO. | Baja | FR-10 | Corregido: la segunda llamada usa otro archivo. |
| ISS-02 | El guion de la demo arrancaba sin esperar a que los servidores respondieran y fallaba con `ConnectError`. | Baja | FR-05…FR-08 | Corregido: espera activa sobre `GET /health` antes de la demo. |
| ISS-03 | `demo-evidence/` no tenía imágenes ni video, que pide el enunciado; además el README citaba un `demo-log.txt` que no existía. | Media | — (entregable) | Corregido: capturas `01`…`09` de la demo en vivo tomadas en el equipo del grupo; el README solo cita archivos existentes. |
| ISS-04 | La revisión arquitectónica RA-01…RA-10 está preparada, pero falta la confirmación de cada integrante. | Media | NFR-01…NFR-03 | Pendiente: firmar `docs/architecture-review.md`. |
| ISS-06 | Al ejecutar en **Windows**, TC-07a y TC-19 fallaron: con el Controller apagado, Windows no rechaza la conexión al instante sino que la reintenta, se agotaba el timeout de 1 s y el Router respondía `CONTROLLER_TIMEOUT` en vez de `CONTROLLER_UNAVAILABLE`. | Media | FR-07, FR-09, NFR-11 | Corregido: `HttpControllerClient` trata `ConnectTimeout` (no se pudo conectar) como `CONTROLLER_UNAVAILABLE` y solo un `ReadTimeout` (conectó pero no respondió) como `CONTROLLER_TIMEOUT`. Se agregaron 3 pruebas en TC-25. |
| ISS-07 | El README y este plan citaban TC-27 en `tests/controller/test_ui_console.py`, pero el archivo no existía: se había subido `tests/controller/ui_controller.py`, una copia del controlador que pytest no ejecuta. | Media | FR-05 | Corregido: se escribió la prueba TC-27 (3 casos) y se eliminó la copia. |
| ISS-05 | `tests/perf-environment.txt` refleja el entorno donde se ejecutó TC-18, no el equipo del grupo. | Baja | NFR-10 | Corregido: el archivo se regenera al ejecutar `pytest -v` en el equipo del grupo, junto con `tests/test-results.txt`. |
