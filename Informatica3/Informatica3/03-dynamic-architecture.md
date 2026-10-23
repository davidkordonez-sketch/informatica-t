# 03 — Arquitectura Dinámica

> Describe **cómo interactúan** los componentes definidos en `02-static-architecture.md`. Todo participante es una clase de ese documento y todo mensaje HTTP coincide con `04-api-contract.md`.

Topología de referencia usada en los ejemplos: la de `06-test-spec.md` (nodos A–F; A→D por `delay` = `[A,B,D]`, costo 20).

---

## Secuencia 1 — Reenvío exitoso de un paquete

```mermaid
sequenceDiagram
    autonumber
    actor Cli as Cliente
    participant PC as PacketController (Router)
    participant FS as ForwardingService
    participant HC as HttpControllerClient
    participant RC as RouteController (Controller)
    participant RS as RoutingService
    participant TS as TopologyService
    participant TD as TopologyDAO
    participant FL as ForwardingLogDAO

    Cli->>PC: POST /packets (packet_id, src A, dst D, metric delay)
    PC->>FS: forward_packet(Packet)
    FS->>HC: get_route(A, D, delay)
    HC->>RC: GET /route?src=A&dst=D&metric=delay
    RC->>RS: find_route(A, D, DELAY)
    RS->>TS: build_weighted_graph(DELAY)
    opt topologia aun no cargada
        TS->>TD: load_topology()
        TD-->>TS: Topology
    end
    TS-->>RS: Graph ponderado de enlaces activos
    Note over RS: Dijkstra, ruta A-B-D, costo 20
    RS-->>RC: Route
    RC-->>HC: 200 RouteResponse
    HC-->>FS: RouteInfo
    Note over FS: simulate_hops, trace A a B y B a D, estado DELIVERED
    FS->>FL: save(ForwardingResult)
    FL-->>FS: ok
    FS-->>PC: ForwardingResult
    PC-->>Cli: 200 ForwardingResultResponse
```

| # | Mensaje | Clase / método | Contrato |
|---|---|---|---|
| 1 | Paquete entra al Router | `PacketController.post_packet` | `POST /packets` |
| 2 | Se delega al servicio | `ForwardingService.forward_packet` | — |
| 3–4 | Se pide la ruta (el Router **no** calcula) | `HttpControllerClient.get_route` → `RouteController.get_route` | `GET /route` |
| 5–8 | Se construye el grafo activo y se obtiene la topología (carga diferida vía DAO) | `RoutingService.find_route`, `TopologyService.build_weighted_graph`, `TopologyDAO.load_topology` | — |
| 9–11 | Dijkstra → `Route` → respuesta JSON | `RoutingService`, `RouteController` | `200 RouteResponse` |
| 12–13 | Simulación salto a salto | `ForwardingService.simulate_hops` | — |
| 14–15 | Registro del resultado | `ForwardingLogDAO.save` | FR-10 |
| 16–17 | Respuesta final | `PacketController` | `200 ForwardingResultResponse` |

**Requisitos cubiertos:** FR-01, FR-03, FR-05, FR-07, FR-08, FR-10, NFR-03, NFR-09. **Pruebas:** TC-05, TC-06, TC-16.

---

## Secuencia 2 — Fallo y recuperación de un enlace

```mermaid
sequenceDiagram
    autonumber
    actor Adm as Administrador
    actor Cli as Cliente
    participant LC as LinkController (Controller)
    participant TS as TopologyService
    participant PC as PacketController (Router)
    participant FS as ForwardingService
    participant HC as HttpControllerClient
    participant RC as RouteController (Controller)
    participant RS as RoutingService

    Adm->>LC: POST /links/fail (node_a B, node_b D)
    LC->>TS: fail_link(B, D)
    Note over TS: estado FAILED, topology_version +1
    TS-->>LC: Link
    LC-->>Adm: 200 LinkStateResponse (status failed, version 2)

    Cli->>PC: POST /packets (A a D, delay)
    PC->>FS: forward_packet(Packet)
    FS->>HC: get_route(A, D, delay)
    HC->>RC: GET /route?src=A&dst=D&metric=delay
    RC->>RS: find_route(A, D, DELAY)
    RS->>TS: build_weighted_graph(DELAY)
    TS-->>RS: Graph sin el enlace B-D

    alt existe camino alternativo
        RS-->>RC: Route A-C-D costo 25
        RC-->>HC: 200 RouteResponse
        HC-->>FS: RouteInfo
        FS-->>PC: ForwardingResult DELIVERED
        PC-->>Cli: 200 trace A-C y C-D
    else no hay camino activo
        RS-->>RC: RouteNotFoundError
        RC-->>HC: 404 ROUTE_NOT_FOUND
        HC-->>FS: RouteNotFoundError
        FS-->>PC: ForwardingResult UNREACHABLE
        PC-->>Cli: 200 estado UNREACHABLE, trace vacio
    end

    Adm->>LC: POST /links/restore (node_a B, node_b D)
    LC->>TS: restore_link(B, D)
    Note over TS: estado ACTIVE, topology_version +1
    TS-->>LC: Link
    LC-->>Adm: 200 LinkStateResponse (status active, version 3)

    Cli->>PC: POST /packets (A a D, delay)
    Note over PC,RS: mismo flujo de la Secuencia 1
    PC-->>Cli: 200 DELIVERED por A-B-D, costo 20
```

| Escenario | Resultado esperado |
|---|---|
| Fallo B–D, camino alternativo (C–D activo) | Ruta `[A,C,D]`, costo 25, `topology_version` = 2 |
| Fallo B–D **y** C–D | Controller: 404 `ROUTE_NOT_FOUND`; Router: 200 con `UNREACHABLE` |
| Restablecer B–D | Ruta `[A,B,D]`, costo 20, `topology_version` = 3 |
| Fallar un enlace ya caído | 409 `LINK_ALREADY_FAILED` (sin cambio de versión) |

**Requisitos cubiertos:** FR-03, FR-06, FR-08, FR-09. **Pruebas:** TC-03, TC-04, TC-07, TC-11, TC-16.

---

## Secuencia 3 — Controller no disponible (error de conexión o timeout)

```mermaid
sequenceDiagram
    autonumber
    actor Cli as Cliente
    participant PC as PacketController (Router)
    participant FS as ForwardingService
    participant HC as HttpControllerClient
    participant EH as Manejador de errores (Router)
    participant CT as Controller (caido o lento)

    Cli->>PC: POST /packets (A a D, delay)
    PC->>FS: forward_packet(Packet)
    FS->>HC: get_route(A, D, delay)
    HC->>CT: GET /route?src=A&dst=D&metric=delay
    alt conexion rechazada
        CT--xHC: ConnectError
        HC-->>FS: ControllerUnavailableError
    else timeout excedido
        CT--xHC: Timeout
        HC-->>FS: ControllerTimeoutError
    end
    FS-->>PC: se propaga el error, sin registro en el log
    PC->>EH: excepcion de dominio
    EH-->>Cli: 503 CONTROLLER_UNAVAILABLE o CONTROLLER_TIMEOUT
    Note over PC: el Router sigue activo, GET /health responde 200
```

| Aspecto | Comportamiento |
|---|---|
| Detección | `HttpControllerClient` captura errores de `httpx` (conexión, timeout, 5xx) y lanza excepciones de dominio. |
| Tiempo máximo | `CONTROLLER_TIMEOUT_S` (2 s por defecto); respuesta 503 en ≤ timeout + 1 s (NFR-11). |
| Reintentos | Ninguno (decisión A-04). |
| Registro | No se crea `ForwardingResult`, por lo tanto no se escribe en el log (decisión A-10). |
| Respuesta estable | `{"error": {"code": "CONTROLLER_UNAVAILABLE", "message": "...", "details": {}}}` |

**Requisitos cubiertos:** FR-07, FR-09, NFR-06, NFR-11. **Pruebas:** TC-07, TC-19.

---

## Coherencia entre diagramas, clases y API

| Verificación | Resultado |
|---|---|
| Todo participante de las secuencias existe en `02-static-architecture.md` | Sí (PacketController, ForwardingService, HttpControllerClient, RouteController, RoutingService, TopologyService, TopologyDAO, ForwardingLogDAO, LinkController) |
| Todo mensaje HTTP existe en `04-api-contract.md` | `POST /packets`, `GET /route`, `POST /links/fail`, `POST /links/restore` |
| Todo método llamado existe en el diagrama de clases | `forward_packet`, `get_route`, `find_route`, `build_weighted_graph`, `load_topology`, `save`, `fail_link`, `restore_link`, `post_packet` |
| Los códigos de error coinciden con el catálogo de `01-requirements.md` §7 | Sí |
