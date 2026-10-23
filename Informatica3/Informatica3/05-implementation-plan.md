# 05 — Plan de Implementación

Responsables: **A** = Estudiante A (Controller) · **B** = Estudiante B (Router) · **AB** = ambos. Una vez congelado `04-api-contract.md`, A y B trabajan **en paralelo** usando fakes del otro lado (Router con `FakeRouteProvider`; Controller con `FakeTopologyDAO`).

## 1. Cronograma de la Sesión 2 (108 min)

| Bloque | Min | Foco | Tareas |
|---|---|---|---|
| 1. Revisar especificaciones y configuración | 10 | Entorno, repositorio, reparto | T-00 |
| 2. Modelos y patrones | 23 | Modelos, interfaces DAO, DI, excepciones | T-01, T-03, T-07, T-08 (interfaz), T-09 (interfaz) |
| 3. Desarrollo de ambas apps | 35 | Servicios, controladores, `main.py` | T-02, T-04, T-05, T-06, T-08, T-09, T-10, T-11 |
| 4. Integración | 15 | Procesos separados, HTTP real | T-15 |
| 5. Pruebas y verificación | 20 | Funcionales, integración, aislamiento DAO, arquitectura | T-12, T-13, T-14 |
| 6. Entrega | 5 | Commit, evidencias, README | T-16, T-17 |

## 2. Desglose de tareas

| ID | Tarea | Resp. | Depende de | Requisitos | Componente / artefacto | Pruebas |
|---|---|---|---|---|---|---|
| T-00 | Crear repo, estructura de carpetas, entorno virtual, instalar dependencias, verificar FastAPI básico | AB | — | NFR-05 | Estructura del repo, `requirements.txt` | — |
| T-01 | Modelos del Controller (`Link`, `Topology`, `Route`, `Metric`, `LinkStatus`) y excepciones de dominio | A | T-00 | FR-02, FR-03 | `controller/models/`, `exceptions.py` | TC-01 |
| T-02 | `LinkCostCalculator` (costos y utilizabilidad) | A | T-01 | FR-04 | `services/link_cost_calculator` | TC-02, TC-10 |
| T-03 | Interfaz `TopologyDAO` + `JsonTopologyDAO` | A | T-01 | FR-01, NFR-02, NFR-09 | `controller/dao/` | TC-17 |
| T-04 | `TopologyService` (carga diferida, validación, estado de enlaces, versión, grafo ponderado) | A | T-02, T-03 | FR-01, FR-02, FR-06 | `services/topology_service` | TC-03, TC-04, TC-17 |
| T-05 | `RoutingService` (Dijkstra, errores de nodo/ruta) | A | T-04 | FR-03, NFR-03 | `services/routing_service` | TC-01, TC-08 |
| T-06 | Esquemas, controladores REST, manejador de errores, `main.py` del Controller | A | T-05, `04` | FR-05, FR-06, FR-09, NFR-04, NFR-05 | `controllers/`, `schemas/`, `main.py` | TC-11, TC-16 |
| T-07 | Modelos del Router (`Packet`, `RouteInfo`, `HopRecord`, `ForwardingResult`) y excepciones | B | T-00 | FR-08 | `router/models/`, `exceptions.py` | TC-06 |
| T-08 | Interfaz `ForwardingLogDAO` + `JsonLinesForwardingLogDAO` | B | T-07 | FR-10, NFR-02 | `router/dao/` | TC-09, TC-15 |
| T-09 | Interfaz `RouteProvider` + `HttpControllerClient` (timeout, traducción de errores) | B | T-07, `04` | FR-07, NFR-11 | `router/clients/` | TC-05, TC-19 |
| T-10 | `ForwardingService` (simulación de saltos, UNREACHABLE, captura de `PersistenceError`) | B | T-08, T-09 | FR-08, FR-10 | `services/forwarding_service` | TC-06, TC-07, TC-09, TC-15 |
| T-11 | Esquemas, controladores REST, manejador de errores, `main.py` del Router | B | T-10, `04` | FR-08, FR-09, NFR-04, NFR-05 | `controllers/`, `schemas/`, `main.py` | TC-11, TC-16 |
| T-12 | Pruebas del Controller: unitarias de servicios, mock de DAO, API | A | T-06 | FR-01–FR-06, NFR-09 | `tests/controller/` | TC-01–TC-04, TC-08, TC-10, TC-11, TC-17, TC-18 |
| T-13 | Pruebas del Router: unitarias, mocks de `RouteProvider` y DAO, Controller caído | B | T-11 | FR-07–FR-10 | `tests/router/` | TC-05–TC-07, TC-09, TC-15, TC-19 |
| T-14 | Pruebas de arquitectura (AST/grep): controladores sin algoritmos ni acceso a datos, servicios sin I/O directa, Router sin NetworkX | AB | T-06, T-11 | NFR-01–NFR-03 | `tests/architecture/` | TC-12, TC-13, TC-14 |
| T-15 | Integración E2E con dos procesos reales: ruta, fallo, ruta alternativa, restablecimiento | AB | T-06, T-11 | FR-05–FR-08 | `tests/integration/` | TC-16 |
| T-16 | `tests/test-results.txt` (`pytest -v`), evidencias de la demo (capturas/video), `README.md` | AB | T-12–T-15 | NFR-08 | `README.md`, `demo-evidence/` | — |
| T-17 | `prompts-session2.md` (≥ 3 prompts de generación/prueba de código) | AB | durante toda la sesión | Registro de IA | `prompts-session2.md` | — |

## 3. Trazabilidad completa (requisito → tarea → componente → prueba)

| Requisito | Tareas | Componentes fuente | Pruebas |
|---|---|---|---|
| FR-01 | T-03, T-04 | `TopologyDAO`, `JsonTopologyDAO`, `TopologyService` | TC-13, TC-16, TC-17 |
| FR-02 | T-01, T-04 | `Topology`, `Link`, `TopologyService.validate` | TC-11, TC-17 |
| FR-03 | T-01, T-05 | `RoutingService`, `Route` | TC-01, TC-07, TC-11, TC-12 |
| FR-04 | T-02 | `LinkCostCalculator` | TC-02, TC-10 |
| FR-05 | T-06 | `RouteController`, `TopologyController`, `HealthController` | TC-11, TC-16 |
| FR-06 | T-04, T-06 | `LinkController`, `TopologyService` | TC-03, TC-04, TC-11 |
| FR-07 | T-09 | `RouteProvider`, `HttpControllerClient` | TC-05, TC-14, TC-19 |
| FR-08 | T-10, T-11 | `ForwardingService`, `PacketController` | TC-06, TC-07, TC-12 |
| FR-09 | T-06, T-11 | `exceptions.py`, manejadores de errores | TC-07, TC-11, TC-17, TC-19 |
| FR-10 | T-08, T-10 | `ForwardingLogDAO`, `JsonLinesForwardingLogDAO` | TC-09, TC-13, TC-15 |
| NFR-01…03 | T-14 | Estructura MVC/DAO | TC-12, TC-13 |
| NFR-04 | T-06, T-11 | Esquemas | TC-11, TC-16 |
| NFR-05 | T-00, T-06, T-11 | `config.py` | TC-16, TC-19 |
| NFR-06 | T-06, T-11 | Manejadores de errores | TC-07, TC-15, TC-17, TC-19 |
| NFR-07, NFR-09 | T-05, T-10 | DI por constructor | TC-08, TC-09 |
| NFR-08 | T-16 | Este documento | Revisión |
| NFR-10 | T-12 | `RoutingService`, `TopologyService` | TC-18 |
| NFR-11 | T-09, T-13 | `HttpControllerClient` | TC-19 |

## 4. Puntos de sincronización y convenciones

1. **Contrato primero:** nadie cambia `04-api-contract.md` sin avisar al otro y registrar el cambio en `01` §9.
2. **Hitos de integración:** (a) al minuto ~45 ambos tienen servicios con fakes pasando pruebas; (b) al minuto ~70 ambas apps arrancan; (c) al minuto ~85 corre el E2E.
3. **Commits individuales y frecuentes** (el enunciado exige conservarlos); mensajes con el ID de tarea (p. ej. `T-05: RoutingService con Dijkstra`).
4. **Revisión cruzada:** A revisa el código de B y viceversa (Estudiante A y B tienen acuerdo conjunto de API, pruebas de integración y revisión de código). Importante para la defensa: **cada uno debe poder explicar todo**.
5. **Fallos honestos:** si un requisito queda incompleto o una prueba falla, se documenta en el README; no se cambian los requisitos para "pasar".

## 5. Definición de hecho (DoD) por tarea

- Código en la capa correcta (MVC/DAO) y sin violar las reglas R1–R6 de `02`.
- Dependencias inyectadas por constructor.
- Pruebas asociadas escritas y pasando (o falla documentada).
- Commit con ID de tarea y revisión del compañero.

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Controladores acaban con lógica de Dijkstra o de archivos | Pruebas de arquitectura TC-12/TC-13 desde temprano |
| Desalineación de JSON entre apps | Pruebas contra los ejemplos de `04`; E2E temprano |
| Fallar por tiempo en la Sesión 2 | Priorizar: modelos → servicios → API mínima → pruebas → mejoras |
| Uso acrítico de código generado por IA | Revisar cada salida contra `01`–`06`; registrar defectos en `prompts-session2.md` |

## 7. Preparación para la defensa (20 min por equipo)

| Bloque | Min | Qué preparar |
|---|---|---|
| Requisitos y arquitectura | 4 | Matriz de trazabilidad y decisiones MVC/DAO (`05` §3, `02` §5–7) |
| Ejecución en vivo | 6 | Arrancar ambas apps, paquete, fallo de enlace, nueva ruta, restablecer, mock de DAO |
| Inspección de código | 4 | Clases, interfaces y límites de servicio/DAO |
| Preguntas individuales | 6 | Ver lista de preguntas del taller; sin herramientas de IA |

Guion de demo: iniciar Controller (8000) y Router (8001) → `POST /packets` A→D → `POST /links/fail` B–D → repetir paquete (ruta `[A,C,D]`) → `POST /links/restore` → repetir (ruta `[A,B,D]`) → ejecutar TC-08 con DAO simulado.
