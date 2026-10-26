# 03 — Arquitectura Dinámica

Versión 1.1 (2026-10-26). Cambios respecto a 1.0 registrados en `01-requirements.md` §9 (CH-01, CH-02, CH-03, CH-04).

Topología de referencia usada en los ejemplos: la de `06-test-spec.md` (nodos A–F; A→D por `delay` = `[A,B,D]`, costo 20).

**Convenciones de los diagramas (SPDR-04).**
- Todo participante es una clase de `02-static-architecture.md` y se nombra `Clase (App)`, por ejemplo `RouteController (Controller)`. Solo los actores externos (Cliente, Administrador) no son clases.
- `->>` es una llamada o petición; `-->>` es un retorno normal; `--x` es una excepción lanzada o un fallo de red.
- Los errores siempre se propagan hasta el `ErrorHandler (App)` correspondiente, que es el único que produce la respuesta HTTP de error.
- Las llamadas a `ForwardingLogDAO.save()` se muestran siempre con sus dos salidas: éxito o `PersistenceError`.

| Secuencia | Escenario | Exigida por el enunciado |
|---|---|---|
| 1 | Reenvío exitoso | Sí |
| 2 | Fallo y recuperación de enlace (incluye camino alternativo y destino inalcanzable) | Sí |
| 3 | Controller no disponible (conexión rechazada, timeout, 5xx) | Sí |
| 4 | Nodo inexistente y respuesta inválida del Controller | Complementaria (SPDR-03) |
| 5 | Consulta de ruta concurrente con un fallo de enlace | Complementaria (SPDR-02) |

---

## Secuencia 1 — Reenvío exitoso de un paquete

```mermaid
sequenceDiagram
    autonumber
    actor Cli as Cliente
    participant PC as PacketController (Router)
    participant FS as ForwardingService (Router)
    participant HC as HttpControllerClient (Router)
    participant FL as ForwardingLogDAO (Router)
    participant RC as RouteController (Controller)
    participant RS as RoutingService (Controller)
    participant TS as TopologyService (Controller)
    participant TD as TopologyDAO (Controller)

    Cli->>PC: POST /packets (packet_id, src A, dst D, metric delay)
    PC->>FS: forward_packet(Packet)
    FS->>HC: get_route(A, D, delay)
    HC->>RC: GET /route?src=A&dst=D&metric=delay
    RC->>RS: find_route(A, D, DELAY)
    RS->>TS: get_snapshot()
    opt topologia aun no cargada
        TS->>TD: load_topology()
        TD-->>TS: Topology version 1
        Note over TS: validate y publica la instantanea bajo write_lock
    end
    TS-->>RS: snapshot (Topology inmutable, version 1)
    RS->>TS: build_weighted_graph(snapshot, DELAY)
    TS-->>RS: Graph ponderado de enlaces activos de esa instantanea
    Note over RS: Dijkstra sobre el grafo, ruta A-B-D, costo 20, topology_version = snapshot.version
    RS-->>RC: Route
    RC-->>HC: 200 RouteResponse
    Note over HC: parse_route_response valida esquema y coherencia de la ruta
    HC-->>FS: RouteInfo
    Note over FS: simulate_hops, trace A a B y B a D, estado DELIVERED
    FS->>FL: save(ForwardingResult DELIVERED)
    alt escritura completa y fsync correcto
        FL-->>FS: ok
        Note over FS: log_persisted = true, warnings vacio
    else fallo de escritura (permisos, disco lleno, escritura parcial)
        FL--xFS: PersistenceError
        Note over FS: log_persisted = false, warning PERSISTENCE_ERROR, sin reintento
    end
    FS-->>PC: ForwardingResult
    PC-->>Cli: 200 ForwardingResultResponse (status DELIVERED)
```

| # | Mensaje | Clase / método | Contrato |
|---|---|---|---|
| 1 | Paquete entra al Router | `PacketController.post_packet` | `POST /packets` |
| 2 | Se delega al servicio | `ForwardingService.forward_packet` | — |
| 3–4 | Se pide la ruta (el Router **no** calcula) | `HttpControllerClient.get_route` → `RouteController.get_route` | `GET /route` |
| 5–9 | Se toma **una** instantánea; si no hay topología, carga diferida vía DAO | `RoutingService.find_route`, `TopologyService.get_snapshot`, `TopologyDAO.load_topology` | A-13, A-14 |
| 10–11 | Grafo ponderado de **esa** instantánea | `TopologyService.build_weighted_graph(snapshot, metric)` | R8 |
| 12–13 | Dijkstra → `Route` → respuesta JSON | `RoutingService`, `RouteController` | `200 RouteResponse` |
| 14 | Respuesta validada y entregada al servicio; luego simulación salto a salto (nota) | `HttpControllerClient.parse_route_response`, `ForwardingService.simulate_hops` | A-15 |
| 15–17 | Registro del resultado con sus dos salidas | `ForwardingService.persist` → `ForwardingLogDAO.save` | FR-10, `01` §7.2 filas D1/D2 |
| 18–19 | Respuesta final | `PacketController` | `200 ForwardingResultResponse` |

**Requisitos cubiertos:** FR-01, FR-03, FR-05, FR-07, FR-08, FR-10, NFR-03, NFR-09, NFR-12. **Pruebas:** TC-05, TC-06, TC-09, TC-15, TC-16.

---

## Secuencia 2 — Fallo y recuperación de un enlace

Escenario: el Administrador falla B–D, el Cliente envía un paquete A→D, el Administrador restablece B–D y el Cliente vuelve a enviar el paquete. La rama "no hay camino activo" corresponde al caso en que además C–D está fallado.

```mermaid
sequenceDiagram
    autonumber
    actor Adm as Administrador
    actor Cli as Cliente
    participant LC as LinkController (Controller)
    participant CEH as ErrorHandler (Controller)
    participant TS as TopologyService (Controller)
    participant PC as PacketController (Router)
    participant FS as ForwardingService (Router)
    participant HC as HttpControllerClient (Router)
    participant FL as ForwardingLogDAO (Router)
    participant RC as RouteController (Controller)
    participant RS as RoutingService (Controller)

    Adm->>LC: POST /links/fail (node_a B, node_b D)
    LC->>TS: fail_link(B, D)
    alt enlace existe y esta activo
        Note over TS: bajo write_lock crea instantanea nueva con B-D FAILED y version 2, publica current
        TS-->>LC: LinkChange (link B-D failed, topology_version 2)
        LC-->>Adm: 200 LinkStateResponse (status failed, version 2)
    else enlace ya fallado
        TS--xLC: LinkAlreadyFailedError
        LC--xCEH: se propaga la excepcion
        CEH-->>Adm: 409 LINK_ALREADY_FAILED, version sin cambios
    end

    Cli->>PC: POST /packets (A a D, delay)
    PC->>FS: forward_packet(Packet)
    FS->>HC: get_route(A, D, delay)
    HC->>RC: GET /route?src=A&dst=D&metric=delay
    RC->>RS: find_route(A, D, DELAY)
    RS->>TS: get_snapshot()
    TS-->>RS: snapshot version 2
    RS->>TS: build_weighted_graph(snapshot, DELAY)
    TS-->>RS: Graph sin el enlace B-D

    alt existe camino alternativo
        Note over RS: Dijkstra, ruta A-C-D, costo 25
        RS-->>RC: Route (topology_version 2)
        RC-->>HC: 200 RouteResponse
        Note over HC: parse_route_response valida la respuesta
        HC-->>FS: RouteInfo
        Note over FS: simulate_hops, trace A a C y C a D, estado DELIVERED
        FS->>FL: save(ForwardingResult DELIVERED)
        alt guardado correcto
            FL-->>FS: ok
            Note over FS: log_persisted = true
        else fallo de persistencia
            FL--xFS: PersistenceError
            Note over FS: log_persisted = false, warning PERSISTENCE_ERROR
        end
        FS-->>PC: ForwardingResult DELIVERED
        PC-->>Cli: 200 DELIVERED, trace A-C y C-D, version 2
    else no hay camino activo
        RS--xRC: RouteNotFoundError
        RC--xCEH: se propaga la excepcion
        CEH-->>HC: 404 ROUTE_NOT_FOUND
        HC--xFS: RouteNotFoundError
        Note over FS: arma ForwardingResult UNREACHABLE, route null, trace vacio, reason ROUTE_NOT_FOUND
        FS->>FL: save(ForwardingResult UNREACHABLE)
        alt guardado correcto
            FL-->>FS: ok
            Note over FS: log_persisted = true
        else fallo de persistencia
            FL--xFS: PersistenceError
            Note over FS: log_persisted = false, warning PERSISTENCE_ERROR
        end
        FS-->>PC: ForwardingResult UNREACHABLE
        PC-->>Cli: 200 UNREACHABLE, trace vacio
    end

    Adm->>LC: POST /links/restore (node_a B, node_b D)
    LC->>TS: restore_link(B, D)
    Note over TS: bajo write_lock crea instantanea nueva con B-D ACTIVE y version 3, publica current
    TS-->>LC: LinkChange (link B-D active, topology_version 3)
    LC-->>Adm: 200 LinkStateResponse (status active, version 3)

    Cli->>PC: POST /packets (A a D, delay)
    PC->>FS: forward_packet(Packet)
    FS->>HC: get_route(A, D, delay)
    HC->>RC: GET /route?src=A&dst=D&metric=delay
    RC->>RS: find_route(A, D, DELAY)
    RS->>TS: get_snapshot()
    TS-->>RS: snapshot version 3
    RS->>TS: build_weighted_graph(snapshot, DELAY)
    TS-->>RS: Graph con el enlace B-D
    Note over RS: Dijkstra, ruta A-B-D, costo 20
    RS-->>RC: Route (topology_version 3)
    RC-->>HC: 200 RouteResponse
    HC-->>FS: RouteInfo
    Note over FS: simulate_hops, trace A a B y B a D, estado DELIVERED
    FS->>FL: save(ForwardingResult DELIVERED)
    alt guardado correcto
        FL-->>FS: ok
    else fallo de persistencia
        FL--xFS: PersistenceError
        Note over FS: log_persisted = false, warning PERSISTENCE_ERROR
    end
    FS-->>PC: ForwardingResult DELIVERED
    PC-->>Cli: 200 DELIVERED por A-B-D, costo 20, version 3
```

| Escenario | Resultado esperado | ¿Se llama a `save()`? |
|---|---|---|
| Fallo B–D, camino alternativo (C–D activo) | Ruta `[A,C,D]`, costo 25, `topology_version` = 2 | Sí (filas D1/D2 de `01` §7.2) |
| Fallo B–D **y** C–D | Controller: 404 `ROUTE_NOT_FOUND`; Router: 200 con `UNREACHABLE` | Sí (filas D3/D4) |
| Restablecer B–D | Ruta `[A,B,D]`, costo 20, `topology_version` = 3 | Sí (filas D1/D2) |
| Fallar un enlace ya caído | 409 `LINK_ALREADY_FAILED` (sin cambio de versión) | No aplica (no hay paquete) |

**Requisitos cubiertos:** FR-03, FR-06, FR-08, FR-09, FR-10, NFR-12. **Pruebas:** TC-03, TC-04, TC-07, TC-09, TC-11, TC-16, TC-24.

---

## Secuencia 3 — Controller no disponible (conexión rechazada, timeout o 5xx)

El participante `RouteController (Controller)` es el destino de la petición HTTP; en las dos primeras ramas su proceso no responde (está detenido o bloqueado), por eso el fallo lo detecta `httpx` dentro de `HttpControllerClient`.

```mermaid
sequenceDiagram
    autonumber
    actor Cli as Cliente
    participant PC as PacketController (Router)
    participant RHC as HealthController (Router)
    participant FS as ForwardingService (Router)
    participant HC as HttpControllerClient (Router)
    participant REH as ErrorHandler (Router)
    participant RC as RouteController (Controller)

    Cli->>PC: POST /packets (A a D, delay)
    PC->>FS: forward_packet(Packet)
    FS->>HC: get_route(A, D, delay)
    HC->>RC: GET /route?src=A&dst=D&metric=delay
    alt conexion rechazada (proceso Controller detenido)
        RC--xHC: httpx.ConnectError
        HC--xFS: ControllerUnavailableError
    else timeout excedido (CONTROLLER_TIMEOUT_S)
        RC--xHC: httpx.TimeoutException
        HC--xFS: ControllerTimeoutError
    else el Controller responde 5xx o 503 TOPOLOGY_UNAVAILABLE
        RC-->>HC: 5xx con cuerpo de error
        HC--xFS: ControllerUnavailableError (details upstream_status y upstream_code)
    end
    Note over FS: no se crea ForwardingResult, no se llama a save (A-10, filas E3 a E5)
    FS--xPC: se propaga la excepcion de dominio
    PC--xREH: se propaga al manejador central
    REH-->>Cli: 503 CONTROLLER_UNAVAILABLE o CONTROLLER_TIMEOUT
    Cli->>RHC: GET /health
    RHC-->>Cli: 200 status ok, el Router sigue activo
```

| Aspecto | Comportamiento |
|---|---|
| Detección | `HttpControllerClient` captura errores de `httpx` (conexión, timeout) y respuestas 5xx, y lanza excepciones de dominio. |
| Tiempo máximo | `CONTROLLER_TIMEOUT_S` (2 s por defecto); respuesta 503 en ≤ timeout + 1 s (NFR-11). |
| Reintentos | Ninguno (decisión A-04). |
| Registro | No se crea `ForwardingResult`, por lo tanto no se escribe en el log (decisión A-10). |
| Respuesta estable | `{"error": {"code": "CONTROLLER_UNAVAILABLE", "message": "...", "details": {}}}` |

**Requisitos cubiertos:** FR-07, FR-09, NFR-06, NFR-11. **Pruebas:** TC-07, TC-19, TC-25.

---

## Secuencia 4 — Nodo inexistente y respuesta inválida del Controller *(SPDR-03)*

```mermaid
sequenceDiagram
    autonumber
    actor Cli as Cliente
    participant PC as PacketController (Router)
    participant FS as ForwardingService (Router)
    participant HC as HttpControllerClient (Router)
    participant REH as ErrorHandler (Router)
    participant RC as RouteController (Controller)
    participant CEH as ErrorHandler (Controller)
    participant RS as RoutingService (Controller)

    Cli->>PC: POST /packets (A a Z, delay)
    PC->>FS: forward_packet(Packet)
    FS->>HC: get_route(A, Z, delay)
    HC->>RC: GET /route?src=A&dst=Z&metric=delay
    RC->>RS: find_route(A, Z, DELAY)
    alt el nodo no existe en la instantanea
        RS--xRC: NodeNotFoundError (node Z)
        RC--xCEH: se propaga la excepcion
        CEH-->>HC: 404 NODE_NOT_FOUND
        HC--xFS: NodeNotFoundError
        Note over FS: no se crea ForwardingResult, no se llama a save (fila E1)
        FS--xPC: se propaga la excepcion
        PC--xREH: se propaga al manejador central
        REH-->>Cli: 404 NODE_NOT_FOUND (details node Z)
    else el Controller devuelve una respuesta fuera del contrato
        RS-->>RC: Route
        RC-->>HC: 200 con cuerpo invalido o ruta incoherente
        Note over HC: parse_route_response detecta el problema, por ejemplo path final distinto de dst
        HC--xFS: ControllerBadResponseError
        Note over FS: no se crea ForwardingResult, no se llama a save (fila E6)
        FS--xPC: se propaga la excepcion
        PC--xREH: se propaga al manejador central
        REH-->>Cli: 502 CONTROLLER_BAD_RESPONSE (details reason)
    end
```

La segunda rama representa un defecto o una versión incompatible del Controller (o un proxy intermedio). Se incluye para dejar explícita la frontera de validación del Router.

**Requisitos cubiertos:** FR-07, FR-09. **Pruebas:** TC-07 (c), TC-25.

---

## Secuencia 5 — Consulta de ruta concurrente con un fallo de enlace *(SPDR-02)*

Muestra por qué una consulta que empezó antes del fallo devuelve una respuesta coherente con la versión 1, aunque el fallo termine mientras se ejecuta Dijkstra.

```mermaid
sequenceDiagram
    autonumber
    participant HC as HttpControllerClient (Router)
    participant RC as RouteController (Controller)
    participant RS as RoutingService (Controller)
    participant TS as TopologyService (Controller)
    participant LC as LinkController (Controller)
    actor Adm as Administrador

    HC->>RC: GET /route?src=A&dst=D&metric=delay
    RC->>RS: find_route(A, D, DELAY)
    RS->>TS: get_snapshot()
    TS-->>RS: S1 (version 1, B-D ACTIVE)
    par hilo de la consulta
        RS->>TS: build_weighted_graph(S1, DELAY)
        TS-->>RS: Graph de S1
        Note over RS: Dijkstra sobre S1, no tiene el lock
    and hilo del fallo
        Adm->>LC: POST /links/fail (B, D)
        LC->>TS: fail_link(B, D)
        Note over TS: adquiere write_lock, crea S2 = S1.with_link_status(B, D, FAILED) con version 2, publica current = S2, libera el lock
        TS-->>LC: LinkChange (topology_version 2)
        LC-->>Adm: 200 LinkStateResponse (version 2)
    end
    Note over RS: S1 no cambio porque es inmutable
    RS-->>RC: Route A-B-D, costo 20, topology_version 1
    RC-->>HC: 200 RouteResponse coherente con la version 1
    HC->>RC: GET /route?src=A&dst=D&metric=delay (consulta posterior)
    RC->>RS: find_route(A, D, DELAY)
    RS->>TS: get_snapshot()
    TS-->>RS: S2 (version 2, B-D FAILED)
    Note over RS: Dijkstra sobre S2
    RS-->>RC: Route A-C-D, costo 25, topology_version 2
    RC-->>HC: 200 RouteResponse coherente con la version 2
```

| Garantía demostrada (`02` §7.1) | Dónde se ve |
|---|---|
| G1 coherencia ruta-versión | Mensajes 11–12 (versión 1) y 17–18 (versión 2) |
| G2 sin estados parciales | Nota "S1 no cambió porque es inmutable" |
| G4 orden en tiempo real | La consulta posterior al 200 del fallo ve la versión 2 |

**Requisitos cubiertos:** FR-03, FR-06, NFR-12. **Pruebas:** TC-20.

---

## Coherencia entre diagramas, clases y API

| Verificación | Resultado |
|---|---|
| Todo participante de las secuencias existe en `02-static-architecture.md` con el mismo nombre | Sí: `PacketController`, `HealthController` (Router), `ForwardingService`, `HttpControllerClient`, `ForwardingLogDAO`, `ErrorHandler` (ambas apps), `RouteController`, `LinkController`, `RoutingService`, `TopologyService`, `TopologyDAO` |
| Todo mensaje HTTP existe en `04-api-contract.md` | `POST /packets`, `GET /route`, `POST /links/fail`, `POST /links/restore`, `GET /health` |
| Todo método llamado existe en el diagrama de clases | `post_packet`, `forward_packet`, `get_route`, `find_route`, `get_snapshot`, `build_weighted_graph`, `load_topology`, `save`, `fail_link`, `restore_link`, `with_link_status`, `parse_route_response` |
| Toda rama que produce `ForwardingResult` llama a `save()` y muestra éxito y fallo | Secuencia 1 (1 llamada), Secuencia 2 (3 llamadas: alternativo, `UNREACHABLE`, tras restablecer) |
| Ninguna rama de error llama a `save()` | Secuencias 3 y 4 |
| Los códigos de error coinciden con el catálogo de `01-requirements.md` §7 | Sí, incluido 502 `CONTROLLER_BAD_RESPONSE` |
