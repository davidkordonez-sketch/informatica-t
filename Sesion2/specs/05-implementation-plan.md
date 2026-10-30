# 05 — Plan de Implementación

Versión 1.1 (2026-10-26). Cambios respecto a 1.0 registrados en `01-requirements.md` §9 (CH-06, CH-07, CH-08).

Responsables: **A** = Estudiante A (Controller) · **B** = Estudiante B (Router) · **AB** = ambos. Una vez congelado `04-api-contract.md`, A y B trabajan **en paralelo** usando fakes del otro lado (Router con `FakeRouteProvider`; Controller con `FakeTopologyDAO`).

## 1. Cronograma de la Sesión 2 (108 min) — revisado *(SPDR-08)*

### 1.1 Entregables mínimos obligatorios

Es lo que **debe** existir al final de la sesión aunque todo lo demás falle. Todo lo que no esté en esta lista es recomendado o extensión y se recorta primero.

| # | Entregable mínimo | Evidencia |
|---|---|---|
| M1 | Controller con `GET /route` (3 métricas), `POST /links/fail`, `POST /links/restore`, `GET /topology`, `GET /health` | Demo en vivo |
| M2 | Router con `POST /packets` (DELIVERED, UNREACHABLE, 503) y `GET /health` | Demo en vivo |
| M3 | MVC + DAO + inyección por constructor en ambas apps; Router sin `networkx` | Revisión RA-01…RA-10 en `docs/architecture-review.md` |
| M4 | Persistencia de **todo** `ForwardingResult` (incluido `UNREACHABLE`) con manejo de `PersistenceError` | TC-09, TC-24 |
| M5 | Las **11 pruebas obligatorias** pasando: TC-01…TC-09 (las del enunciado), TC-12 y TC-24 (≥ 8 exigidas, con margen de 3) | `tests/test-results.txt` |
| M6 | `README.md` con pasos de reproducción, estado de cada requisito y fallos honestos; `demo-evidence/`; `prompts-session2.md` | Repositorio |

### 1.2 Niveles de prueba

| Nivel | Pruebas | Regla |
|---|---|---|
| **Obligatoria** (11) | TC-01, TC-02, TC-03, TC-04, TC-05, TC-06, TC-07, TC-08, TC-09, TC-12, TC-24 | Se escriben **junto con** el componente que prueban (no al final). No se entrega sin ellas. |
| **Recomendada** (10) | TC-10, TC-11, TC-13, TC-14, TC-15, TC-16, TC-17, TC-20, TC-23, TC-25 | Solo después del hito H2 y si sobra tiempo del bloque 7. |
| **Extensión** (5) | TC-18, TC-19, TC-21, TC-22, TC-26 | Solo si todo lo anterior está verde. Si no se implementan, se declaran "no implementadas" en el README (no se borran del plan). |

### 1.3 Bloques e hitos

| Bloque | Minutos | Foco | Tareas | Pruebas que deben quedar escritas |
|---|---|---|---|---|
| 1. Revisión de especificaciones y entorno | 0–8 (8) | Repo, entorno, reparto, fixture de referencia | T-00 | — |
| 2. Modelos y patrones | 8–23 (15) | Modelos inmutables, interfaces DAO/`RouteProvider`, excepciones | T-01, T-03, T-07, T-08 (interfaz), T-09 (interfaz) | — |
| 3. Servicios con fakes | 23–53 (30) | `LinkCostCalculator`, `TopologyService`, `RoutingService`, `ForwardingService` | T-02, T-04, T-05, T-08, T-09, T-10 | TC-01, TC-02, TC-03, TC-04, TC-06, TC-08, TC-09, TC-24 |
| **H1 (min 53)** | — | **8 pruebas obligatorias en verde sin HTTP** | — | — |
| 4. Controladores HTTP, esquemas, `main.py` | 53–70 (17) | REST, `ErrorHandler`, composición | T-06, T-11 | TC-05, TC-07, TC-12 |
| **H2 (min 70)** | — | **Ambas apps arrancan y las 11 obligatorias pasan** (entregable mínimo M5 cumplido) | — | — |
| 5. Integración y evidencias | 70–80 (10) | Dos procesos reales, guion de demo, capturas | T-15 | (TC-16 si da el tiempo) |
| **H3 (min 80)** | — | **Demo completa ejecutada y capturada** | — | — |
| 6. Corrección de defectos (reservado) | 80–92 (12) | Solo arreglar lo que falla; **no** se agregan funcionalidades nuevas | — | — |
| 7. Revisión arquitectónica + pruebas recomendadas | 92–100 (8) | Revisión cruzada RA (4 min); pruebas recomendadas baratas: TC-13, TC-14, TC-10 | T-18, T-14 | Recomendadas |
| 8. Entrega | 100–108 (8) | `pytest -v`, README, prompts, commit final | T-16, T-17 | — |

**Correspondencia con las actividades del enunciado** (mismo total de 108 min): actividad 1 → bloque 1 (+2 min a los bloques siguientes); actividad 2 → bloque 2; actividad 3 → bloques 3 y 4; actividad 4 → bloque 5; actividad 5 → bloques 6 y 7 (las pruebas obligatorias ya se escribieron en los bloques 3 y 4); actividad 6 → bloque 8. El cambio responde a SPDR-08: escribir las pruebas junto al código y reservar tiempo explícito para defectos.

### 1.4 Reglas de recorte

| Situación | Decisión |
|---|---|
| H1 se retrasa más de 5 min | Se elimina el bloque 7 (solo se hace la revisión RA, 4 min, dentro del bloque 6) y no se intenta ninguna prueba recomendada. |
| H2 se retrasa más de 5 min | La integración (bloque 5) se hace como demo manual con `curl` y capturas; TC-16 pasa a "no implementada". |
| Una prueba obligatoria falla al llegar a H3 | Se usa el bloque 6 solo para esa prueba. Si sigue fallando a los 100 min, se registra el fallo en `test-results.txt` y en el README (no se modifica el requisito). |
| Sobra tiempo después del bloque 7 | Se implementan pruebas de extensión en este orden: TC-26, TC-21, TC-22, TC-19, TC-18. |
| Siempre | TC-08 y TC-09 no se recortan nunca (las exige el enunciado). |

## 2. Desglose de tareas

| ID | Tarea | Resp. | Depende de | Requisitos | Componente / artefacto | Pruebas (nivel) |
|---|---|---|---|---|---|---|
| T-00 | Crear repo, estructura de carpetas, entorno virtual, instalar dependencias, verificar FastAPI básico, copiar `tests/fixtures/topology.json` | AB | — | NFR-05 | Estructura del repo, `requirements.txt` | — |
| T-01 | Modelos del Controller (`Link`, `Topology` y `LinkChange` inmutables, `Route`, `Metric`, `LinkStatus`) y excepciones de dominio | A | T-00 | FR-02, FR-03, NFR-12 | `controller/models/`, `exceptions.py` | TC-01 (Oblig.) |
| T-02 | `LinkCostCalculator` (costos y utilizabilidad) | A | T-01 | FR-04 | `services/link_cost_calculator` | TC-02 (Oblig.), TC-10 (Rec.) |
| T-03 | Interfaz `TopologyDAO` + `JsonTopologyDAO` | A | T-01 | FR-01, NFR-02, NFR-09 | `controller/dao/` | TC-17 (Rec.), TC-21 (Ext.) |
| T-04 | `TopologyService`: carga diferida con *double-checked locking*, validación, instantáneas inmutables con `write_lock`, `get_snapshot`/`peek_snapshot`, grafo ponderado a partir de una instantánea | A | T-02, T-03 | FR-01, FR-02, FR-06, NFR-12 | `services/topology_service` | TC-03, TC-04 (Oblig.), TC-17, TC-20 (Rec.) |
| T-05 | `RoutingService` (una instantánea por consulta, Dijkstra, errores de nodo/ruta) | A | T-04 | FR-03, NFR-03, NFR-12 | `services/routing_service` | TC-01, TC-08 (Oblig.), TC-20 (Rec.) |
| T-06 | Esquemas, controladores REST, manejador de errores, `main.py` del Controller (1 worker) | A | T-05, `04` | FR-05, FR-06, FR-09, NFR-04, NFR-05 | `controllers/`, `schemas/`, `main.py` | TC-12 (Oblig.), TC-11, TC-23 (Rec.) |
| T-07 | Modelos del Router (`Packet`, `RouteInfo`, `HopRecord`, `ResultWarning`, `ForwardingResult` con `to_log_record`) y excepciones (incluida `ControllerBadResponseError`) | B | T-00 | FR-08, FR-10 | `router/models/`, `exceptions.py` | TC-06 (Oblig.) |
| T-08 | Interfaz `ForwardingLogDAO` + `JsonLinesForwardingLogDAO` (lock, una escritura por línea, `fsync`, aislamiento de fragmentos, `find_all` tolerante) | B | T-07 | FR-10, NFR-02 | `router/dao/` | TC-09 (Oblig.), TC-15 (Rec.), TC-26 (Ext.) |
| T-09 | Interfaz `RouteProvider` + `HttpControllerClient` (timeout, validación de `RouteResponse`, tabla de traducción de `04` §3 regla 4) | B | T-07, `04` | FR-07, FR-09, NFR-11 | `router/clients/` | TC-05 (Oblig.), TC-25 (Rec.), TC-19 (Ext.) |
| T-10 | `ForwardingService` (simulación de saltos, `UNREACHABLE`, `persist()` en **todas** las ramas con resultado, captura de cualquier fallo de persistencia) | B | T-08, T-09 | FR-08, FR-10 | `services/forwarding_service` | TC-06, TC-07, TC-09, TC-24 (Oblig.), TC-15 (Rec.) |
| T-11 | Esquemas, controladores REST, manejador de errores (incluido 502), `main.py` del Router | B | T-10, `04` | FR-08, FR-09, NFR-04, NFR-05 | `controllers/`, `schemas/`, `main.py` | TC-07, TC-12 (Oblig.), TC-11, TC-23 (Rec.) |
| T-12 | Pruebas del Controller: unitarias de servicios, fake de DAO, API, concurrencia | A | T-06 | FR-01–FR-06, NFR-09, NFR-12 | `tests/controller/` | TC-01–TC-04, TC-08 (Oblig.); TC-10, TC-11, TC-17, TC-20 (Rec.); TC-18, TC-21 (Ext.) |
| T-13 | Pruebas del Router: unitarias, fakes de `RouteProvider` y DAO, Controller caído, respuestas inválidas | B | T-11 | FR-07–FR-10 | `tests/router/` | TC-05–TC-07, TC-09, TC-24 (Oblig.); TC-15, TC-25 (Rec.); TC-19, TC-22, TC-26 (Ext.) |
| T-14 | Pruebas de arquitectura (AST) y de delegación MVC | AB | T-06, T-11 | NFR-01–NFR-03 | `tests/architecture/` | TC-12 (Oblig.); TC-13, TC-14, TC-23 (Rec.) |
| T-15 | Integración E2E con dos procesos reales: ruta, fallo, ruta alternativa, restablecimiento | AB | T-06, T-11 | FR-05–FR-08 | `tests/integration/` | TC-16 (Rec.) |
| T-16 | `tests/test-results.txt` (`pytest -v`), evidencias de la demo (capturas/video), `README.md` con estado de requisitos y pruebas no implementadas | AB | T-12–T-15 | NFR-08 | `README.md`, `demo-evidence/` | — |
| T-17 | `prompts-session2.md` (prompts de generación y prueba de código, con técnica, problema y corrección) | AB | durante toda la sesión | Registro de IA | `prompts-session2.md` | — |
| **T-18** | **Revisión arquitectónica cruzada** con la lista RA-01…RA-10 (`06` §5): A revisa el Router y B el Controller; se registra archivo:línea, resultado y commit | AB | T-06, T-11 | NFR-01, NFR-02, NFR-03, NFR-07, NFR-12 | `docs/architecture-review.md` | RA-01…RA-10 |

## 3. Trazabilidad completa (requisito → tarea → componente → prueba) *(SPDR-07)*

**Clasificación de la evidencia.**
- **Primaria (P):** la prueba ejecuta el comportamiento y verifica directamente al menos un criterio de aceptación del requisito.
- **Soporte (S):** la prueba ejerce el requisito como parte de otro escenario, pero no lo verifica por sí sola (p. ej., un E2E que pasa por la carga de topología).
- **Inspección arquitectónica (I):** chequeo estático (AST) o revisión manual RA que verifica la **estructura**, no el comportamiento.

Regla: todo requisito funcional tiene al menos una evidencia **P**. Las inspecciones nunca cuentan como evidencia primaria de un comportamiento.

| Requisito | Tareas | Componentes fuente | Primaria (P) | Soporte (S) | Inspección (I) |
|---|---|---|---|---|---|
| FR-01 | T-03, T-04 | `TopologyDAO`, `JsonTopologyDAO`, `TopologyService` | TC-17, TC-21 | TC-08, TC-16 | TC-13, RA-03 |
| FR-02 | T-01, T-04 | `Topology`, `Link`, `TopologyService.validate` | TC-17 | TC-11, TC-18 | — |
| FR-03 | T-01, T-05 | `RoutingService`, `Route` | TC-01, TC-20 | TC-07, TC-08, TC-11, TC-23 | TC-12, RA-02 |
| FR-04 | T-02 | `LinkCostCalculator` | TC-02, TC-10 | — | — |
| FR-05 | T-06 | `RouteController`, `TopologyController`, `HealthController` | TC-11 | TC-16, TC-23 | Inspección de `/docs` |
| FR-06 | T-04, T-06 | `LinkController`, `TopologyService` | TC-03, TC-04, TC-11, TC-20 | TC-16 | — |
| FR-07 | T-09 | `RouteProvider`, `HttpControllerClient` | TC-05, TC-19, TC-25 | TC-16, TC-22 | TC-14, RA-09, RA-10 |
| FR-08 | T-10, T-11 | `ForwardingService`, `PacketController` | TC-06, TC-07, TC-23 | TC-16, TC-24 | TC-12, RA-02 |
| FR-09 | T-06, T-09, T-11 | `exceptions.py`, `ErrorHandler`, `HttpControllerClient` | TC-07, TC-11, TC-24, TC-25 | TC-15, TC-17, TC-19 | RA-06 |
| FR-10 | T-08, T-10 | `ForwardingLogDAO`, `JsonLinesForwardingLogDAO`, `ForwardingService.persist` | TC-09, TC-15, TC-24, TC-26 | TC-16, TC-22 | TC-13, RA-08 |
| NFR-01 | T-14, T-18 | Estructura MVC de ambas apps | TC-23 | — | RA-01…RA-06 |
| NFR-02 | T-14, T-18 | DAO de ambas apps | TC-21, TC-22 | TC-08, TC-09 | TC-13, RA-03 |
| NFR-03 | T-14, T-18 | Controladores HTTP | TC-23 | — | TC-12, RA-02 |
| NFR-04 | T-06, T-11 | Esquemas | TC-11, TC-16 | TC-23, TC-25 | — |
| NFR-05 | T-00, T-06, T-11 | `config.py` | TC-16, TC-19 | — | — |
| NFR-06 | T-06, T-11 | Manejadores de errores | TC-07, TC-15, TC-17, TC-19 | TC-25, TC-26 | — |
| NFR-07 | T-05, T-10, T-18 | DI por constructor | TC-08, TC-09 | TC-21, TC-22 | RA-04, RA-05 |
| NFR-08 | T-16 | Este documento | — | — | Revisión de esta matriz |
| NFR-09 | T-05, T-10 | Interfaces DAO / `RouteProvider` | TC-08, TC-09 | TC-21, TC-22, TC-24 | — |
| NFR-10 | T-12 | `RoutingService`, `TopologyService` | TC-18 | — | — |
| NFR-11 | T-09, T-13 | `HttpControllerClient` | TC-19 | TC-07 (a) | — |
| NFR-12 | T-04, T-05, T-18 | `TopologyService`, `Topology` inmutable, `RoutingService` | TC-20 | TC-03, TC-04 | RA-07 |

**Correcciones respecto a la versión 1.0.** FR-01 ya no usa TC-13 como evidencia de carga exitosa (TC-13 solo inspecciona que no haya I/O en servicios): la evidencia primaria pasa a ser TC-17 (ampliado con topologías válidas) y TC-21. FR-03 y FR-08 dejan de usar TC-12 como evidencia de comportamiento (pasa a inspección) y se agrega TC-23. FR-07 deja de usar TC-14 como primaria.

## 4. Puntos de sincronización y convenciones

1. **Contrato primero:** nadie cambia `04-api-contract.md` sin avisar al otro y registrar el cambio en `01` §9.
2. **Hitos de integración:** H1 (min 53) servicios con fakes y 8 pruebas obligatorias en verde; H2 (min 70) ambas apps arrancan y las 11 obligatorias pasan; H3 (min 80) demo completa capturada. Las reglas de recorte de §1.4 se aplican en cada hito.
3. **Commits individuales y frecuentes** (el enunciado exige conservarlos); mensajes con el ID de tarea (p. ej. `T-05: RoutingService con Dijkstra`).
4. **Revisión cruzada:** A revisa el código de B y viceversa con la lista RA (T-18). Importante para la defensa: **cada uno debe poder explicar todo**, incluido el modelo de concurrencia (`02` §7.1) y la tabla de decisión (`01` §7.2).
5. **Fallos honestos:** si un requisito queda incompleto o una prueba falla, se documenta en el README; no se cambian los requisitos para "pasar".

## 5. Definición de hecho (DoD) por tarea

- Código en la capa correcta (MVC/DAO) y sin violar las reglas R1–R11 de `02` §7.
- Dependencias inyectadas por constructor.
- Pruebas **obligatorias** asociadas escritas y pasando (o falla documentada); recomendadas y de extensión según §1.2.
- Commit con ID de tarea y revisión del compañero.

## 6. Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| **No terminar en 108 min** (SPDR-08) | Alta | Entregables mínimos (§1.1), pruebas por nivel (§1.2), hitos con reglas de recorte (§1.4) y 12 min reservados para defectos. Las pruebas obligatorias se escriben junto al código. |
| Controladores acaban con lógica de Dijkstra o de archivos | Media | TC-12 (obligatoria) desde el bloque 4; TC-23 y revisión RA |
| Desalineación de JSON entre apps | Media | Pruebas contra los ejemplos de `04`; validación de `RouteResponse` en el Router (TC-25); E2E temprano |
| Condiciones de carrera en `TopologyService` | Media | Instantáneas inmutables + `write_lock` (`02` §7.1); TC-20; RA-07 |
| Resultados no persistidos sin que nadie lo note | Media | `persist()` en todas las ramas (R9); TC-24; `log_persisted` en la respuesta |
| Uso acrítico de código generado por IA | Media | Revisar cada salida contra `01`–`06`; registrar defectos en `prompts-session2.md` |

## 7. Preparación para la defensa (20 min por equipo)

| Bloque | Min | Qué preparar |
|---|---|---|
| Requisitos y arquitectura | 4 | Matriz de trazabilidad con tipos de evidencia (`05` §3), decisiones MVC/DAO (`02` §5–7), modelo de concurrencia (`02` §7.1) y tabla de decisión (`01` §7.2) |
| Ejecución en vivo | 6 | Arrancar ambas apps, paquete, fallo de enlace, nueva ruta, restablecer, mock de DAO |
| Inspección de código | 4 | Clases, interfaces y límites de servicio/DAO; dónde se toma la instantánea y dónde se llama a `save()` |
| Preguntas individuales | 6 | Ver lista de preguntas del taller; sin herramientas de IA |

Guion de demo: iniciar Controller (8000) y Router (8001) → `POST /packets` A→D → `POST /links/fail` B–D → repetir paquete (ruta `[A,C,D]`) → `POST /links/restore` → repetir (ruta `[A,B,D]`) → ejecutar TC-08 con DAO simulado → (opcional) ejecutar TC-24 para mostrar un `UNREACHABLE` con `log_persisted: false`.
