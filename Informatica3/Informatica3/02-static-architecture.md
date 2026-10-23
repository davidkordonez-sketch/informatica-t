# 02 — Arquitectura Estática

> Define **qué componentes existen** y cómo se relacionan. Todas las clases usadas en `03-dynamic-architecture.md` aparecen aquí. Los diagramas están en Mermaid (se renderizan en GitHub, VS Code con extensión Mermaid o https://mermaid.live para exportar a PNG).

## 1. Diagrama de componentes

```mermaid
flowchart LR
    CLI["Cliente / Administrador"]

    subgraph ROUTER["Proceso Router - FastAPI - puerto 8001"]
        direction TB
        subgraph RV["Vista y Controlador HTTP"]
            PC["PacketController"]
            RHC["Router HealthController"]
            RSCH["Schemas: PacketRequest, ForwardingResultResponse, ErrorResponse"]
        end
        subgraph RS["Servicios de dominio"]
            FS["ForwardingService"]
        end
        subgraph RM["Modelos"]
            RMOD["Packet, RouteInfo, HopRecord, ForwardingResult"]
        end
        subgraph RC["Cliente REST - frontera hacia el Controller"]
            RP["RouteProvider - interfaz"]
            HCC["HttpControllerClient"]
        end
        subgraph RD["Capa DAO - limite de persistencia"]
            FLD["ForwardingLogDAO - interfaz"]
            JLD["JsonLinesForwardingLogDAO"]
        end
        PC --> FS
        FS --> RP
        FS --> FLD
        HCC -. implementa .-> RP
        JLD -. implementa .-> FLD
    end

    subgraph CTRL["Proceso Controller - FastAPI - puerto 8000"]
        direction TB
        subgraph CV["Vista y Controladores HTTP"]
            RTC["RouteController"]
            LKC["LinkController"]
            TPC["TopologyController"]
            CHC["Controller HealthController"]
            CSCH["Schemas: RouteResponse, TopologyResponse, LinkRequest, ErrorResponse"]
        end
        subgraph CS["Servicios de dominio"]
            RS1["RoutingService"]
            TS["TopologyService"]
            LCC["LinkCostCalculator"]
        end
        subgraph CM["Modelos"]
            CMOD["Node, Link, Topology, Route, Metric, LinkStatus"]
        end
        subgraph CD["Capa DAO - limite de persistencia"]
            TDI["TopologyDAO - interfaz"]
            JTD["JsonTopologyDAO"]
        end
        RTC --> RS1
        LKC --> TS
        TPC --> TS
        RS1 --> TS
        TS --> LCC
        TS --> TDI
        JTD -. implementa .-> TDI
    end

    FILE1[("topology.json")]
    FILE2[("forwarding_log.jsonl")]

    CLI -->|"POST /packets"| PC
    CLI -->|"POST /links/fail, /links/restore, GET /topology"| LKC
    HCC -->|"HTTP GET /route"| RTC
    JTD --> FILE1
    JLD --> FILE2
```

**Lectura del diagrama**
- La única conexión entre procesos es **HTTP/JSON** (`HttpControllerClient` → `RouteController`).
- Los accesos a archivos solo ocurren dentro de las clases DAO concretas.
- Los controladores HTTP solo conocen servicios y esquemas; los servicios solo conocen **interfaces** DAO.

## 2. Diagrama de clases — Controller

```mermaid
classDiagram
    direction LR

    class Metric {
        <<enumeration>>
        DELAY
        BANDWIDTH
        LOSS
    }
    class LinkStatus {
        <<enumeration>>
        ACTIVE
        FAILED
    }
    class Link {
        +str node_a
        +str node_b
        +float delay_ms
        +float bandwidth_mbps
        +float loss_prob
        +LinkStatus status
        +key() frozenset
    }
    class Topology {
        +set~str~ nodes
        +list~Link~ links
        +int version
        +get_link(node_a, node_b) Link
        +has_node(node_id) bool
    }
    class Route {
        +str src
        +str dst
        +Metric metric
        +list~str~ path
        +float total_cost
        +list~float~ hop_costs
        +int topology_version
    }

    class TopologyDAO {
        <<interface>>
        +load_topology() Topology
    }
    class JsonTopologyDAO {
        -str file_path
        +load_topology() Topology
    }

    class LinkCostCalculator {
        +is_usable(link) bool
        +compute_cost(link, metric) float
    }
    class TopologyService {
        -TopologyDAO dao
        -LinkCostCalculator cost_calculator
        -Topology topology
        +ensure_loaded() void
        +is_loaded() bool
        +get_topology() Topology
        +validate(topology) void
        +fail_link(node_a, node_b) Link
        +restore_link(node_a, node_b) Link
        +build_weighted_graph(metric) Graph
        +has_node(node_id) bool
        +get_version() int
    }
    class RoutingService {
        -TopologyService topology_service
        +find_route(src, dst, metric) Route
    }

    class RouteController {
        -RoutingService routing_service
        +get_route(src, dst, metric) RouteResponse
    }
    class LinkController {
        -TopologyService topology_service
        +fail_link(request) LinkStateResponse
        +restore_link(request) LinkStateResponse
    }
    class TopologyController {
        -TopologyService topology_service
        +get_topology() TopologyResponse
    }
    class HealthController {
        -TopologyService topology_service
        +get_health() HealthResponse
    }

    class RouteResponse {
        <<schema>>
    }
    class LinkRequest {
        <<schema>>
        +str node_a
        +str node_b
    }
    class ErrorResponse {
        <<schema>>
        +str code
        +str message
        +dict details
    }

    TopologyDAO <|.. JsonTopologyDAO
    TopologyService --> TopologyDAO : usa interfaz
    TopologyService --> LinkCostCalculator
    TopologyService o-- Topology
    Topology "1" *-- "0..*" Link
    Link --> LinkStatus
    RoutingService --> TopologyService
    RoutingService ..> Route : crea
    RoutingService ..> Metric
    RouteController --> RoutingService
    LinkController --> TopologyService
    TopologyController --> TopologyService
    HealthController --> TopologyService
    RouteController ..> RouteResponse
    LinkController ..> LinkRequest
```

## 3. Diagrama de clases — Router

```mermaid
classDiagram
    direction LR

    class Packet {
        +str packet_id
        +str src
        +str dst
        +str metric
        +str payload
    }
    class RouteInfo {
        +list~str~ path
        +float total_cost
        +int topology_version
    }
    class HopRecord {
        +int hop
        +str from_node
        +str to_node
        +str status
    }
    class ForwardingStatus {
        <<enumeration>>
        DELIVERED
        UNREACHABLE
    }
    class ForwardingResult {
        +str packet_id
        +ForwardingStatus status
        +RouteInfo route
        +list~HopRecord~ trace
        +str reason
        +bool log_persisted
        +list~str~ warnings
        +str timestamp
    }

    class RouteProvider {
        <<interface>>
        +get_route(src, dst, metric) RouteInfo
    }
    class HttpControllerClient {
        -str base_url
        -float timeout_s
        +get_route(src, dst, metric) RouteInfo
    }
    class ForwardingLogDAO {
        <<interface>>
        +save(result) void
        +find_all() list
    }
    class JsonLinesForwardingLogDAO {
        -str file_path
        +save(result) void
        +find_all() list
    }
    class ForwardingService {
        -RouteProvider route_provider
        -ForwardingLogDAO log_dao
        +forward_packet(packet) ForwardingResult
        -simulate_hops(packet, route) list
    }
    class PacketController {
        -ForwardingService forwarding_service
        +post_packet(request) ForwardingResultResponse
    }
    class HealthController {
        +get_health() HealthResponse
    }
    class PacketRequest {
        <<schema>>
    }
    class ForwardingResultResponse {
        <<schema>>
    }

    RouteProvider <|.. HttpControllerClient
    ForwardingLogDAO <|.. JsonLinesForwardingLogDAO
    ForwardingService --> RouteProvider : usa interfaz
    ForwardingService --> ForwardingLogDAO : usa interfaz
    ForwardingService ..> Packet
    ForwardingService ..> ForwardingResult : crea
    ForwardingResult *-- HopRecord
    ForwardingResult --> RouteInfo
    ForwardingResult --> ForwardingStatus
    PacketController --> ForwardingService
    PacketController ..> PacketRequest
    PacketController ..> ForwardingResultResponse
```

## 4. Responsabilidades de las clases

### Controller
| Clase | Capa | Responsabilidad |
|---|---|---|
| `Node`/`Link`/`Topology`/`Route` | Modelo | Objetos de dominio sin dependencias de HTTP ni de almacenamiento. |
| `RouteResponse`, `TopologyResponse`, `LinkRequest`, `ErrorResponse` | Vista | Esquemas Pydantic de entrada/salida (contrato JSON). |
| `RouteController`, `LinkController`, `TopologyController`, `HealthController` | Controlador | Traducen HTTP ⇄ servicios; **sin** lógica de enrutamiento ni acceso a datos. |
| `RoutingService` | Servicio | Ejecuta Dijkstra sobre el grafo ponderado y produce `Route`. Lanza `NodeNotFoundError` / `RouteNotFoundError`. |
| `TopologyService` | Servicio | Carga bajo demanda (`ensure_loaded`), valida la topología, mantiene estado de enlaces y versión, construye el grafo ponderado activo. |
| `LinkCostCalculator` | Servicio | Convierte atributos del enlace en costo ≥ 0 según la métrica; decide si el enlace es utilizable. |
| `TopologyDAO` / `JsonTopologyDAO` | DAO | Leer y parsear el JSON; no valida semántica. |

### Router
| Clase | Capa | Responsabilidad |
|---|---|---|
| `Packet`, `RouteInfo`, `HopRecord`, `ForwardingResult` | Modelo | Objetos de dominio del plano de datos. |
| `PacketRequest`, `ForwardingResultResponse`, `ErrorResponse` | Vista | Esquemas JSON de entrada/salida. |
| `PacketController`, `HealthController` | Controlador | Reciben HTTP, delegan en `ForwardingService`. |
| `ForwardingService` | Servicio | Pide la ruta vía `RouteProvider`, simula el reenvío salto a salto, arma el resultado y lo guarda con el DAO; captura `PersistenceError`. |
| `RouteProvider` / `HttpControllerClient` | Cliente REST | Interfaz y adaptador HTTP hacia `GET /route`; traduce fallos de red en `ControllerUnavailableError` / `ControllerTimeoutError`. |
| `ForwardingLogDAO` / `JsonLinesForwardingLogDAO` | DAO | Guardar y recuperar resultados de reenvío. |

## 5. Mapeo MVC por aplicación

| Capa MVC | Controller | Router |
|---|---|---|
| **Modelo** | `models/` (Node, Link, Topology, Route, Metric, LinkStatus) | `models/` (Packet, RouteInfo, HopRecord, ForwardingResult) |
| **Vista** | `schemas/` | `schemas/` |
| **Controlador** | `controllers/` | `controllers/` |
| **Servicios de dominio** | `services/` (RoutingService, TopologyService, LinkCostCalculator) | `services/` (ForwardingService) |
| **DAO** | `dao/` (TopologyDAO, JsonTopologyDAO) | `dao/` (ForwardingLogDAO, JsonLinesForwardingLogDAO) |
| **Cliente externo** | — | `clients/` (RouteProvider, HttpControllerClient) |

## 6. Inyección de dependencias

La **raíz de composición** (`main.py` de cada app) es el único lugar que conoce las clases concretas:

| App | Ensamblado |
|---|---|
| Controller | `JsonTopologyDAO(TOPOLOGY_FILE)` → `TopologyService(dao, LinkCostCalculator())` → `RoutingService(topology_service)` → controladores |
| Router | `HttpControllerClient(CONTROLLER_URL, CONTROLLER_TIMEOUT_S)` y `JsonLinesForwardingLogDAO(FORWARDING_LOG_FILE)` → `ForwardingService(route_provider, log_dao)` → `PacketController` |

- Se inyecta por **constructor**; los controladores reciben servicios mediante `Depends` de FastAPI.
- En pruebas se inyecta un `FakeTopologyDAO` / `FakeRouteProvider` / `FakeForwardingLogDAO` **sin tocar** `RoutingService` ni `ForwardingService` (NFR-07, NFR-09; TC-08, TC-09).

## 7. Reglas de diseño (verificables)

| Regla | Verificación |
|---|---|
| R1: `controllers/` no importa `networkx`, `heapq`, `json`, `pathlib` ni usa `open()`. | TC-12 |
| R2: `services/` no usa `open()`, `json.load`, `pathlib` ni importa implementaciones DAO concretas. | TC-13 |
| R3: `router/` no importa `networkx` ni implementa Dijkstra. | TC-14 |
| R4: Toda dependencia entre servicio y almacenamiento pasa por una interfaz (`TopologyDAO`, `ForwardingLogDAO`, `RouteProvider`). | Revisión + TC-08, TC-09 |
| R5: Solo `main.py` instancia clases concretas de DAO y cliente. | Revisión |
| R6: Los errores de dominio son excepciones propias traducidas a HTTP en un manejador central, no en los servicios. | TC-11 |

## 8. Estructura de directorios propuesta

```text
sdn-workshop/
├── specs/                      # 01..06 (+ README de la línea base)
├── controller/
│   ├── main.py                 # raíz de composición
│   ├── config.py
│   ├── controllers/            # route_, link_, topology_, health_controller
│   ├── schemas/
│   ├── models/
│   ├── services/               # routing_service, topology_service, link_cost_calculator
│   ├── dao/                    # topology_dao (interfaz), json_topology_dao
│   ├── exceptions.py           # errores de dominio + manejador HTTP
│   └── data/topology.json
├── router/
│   ├── main.py
│   ├── config.py
│   ├── controllers/            # packet_, health_controller
│   ├── schemas/
│   ├── models/
│   ├── services/               # forwarding_service
│   ├── clients/                # route_provider (interfaz), http_controller_client
│   ├── dao/                    # forwarding_log_dao (interfaz), jsonlines_forwarding_log_dao
│   ├── exceptions.py
│   └── data/
├── tests/
│   ├── controller/  router/  architecture/  integration/
│   └── test-results.txt
├── prompts-session1.md
├── prompts-session2.md
├── demo-evidence/
└── README.md
```

## 9. Trazabilidad requisito → componente

| Requisito | Componentes principales |
|---|---|
| FR-01 | `TopologyDAO`, `JsonTopologyDAO`, `TopologyService` |
| FR-02 | `TopologyService.validate`, `build_weighted_graph`, `Topology`, `Link` |
| FR-03 | `RoutingService`, `Route` |
| FR-04 | `LinkCostCalculator`, `Metric` |
| FR-05 | `RouteController`, `TopologyController`, `HealthController`, esquemas |
| FR-06 | `LinkController`, `TopologyService.fail_link/restore_link` |
| FR-07 | `RouteProvider`, `HttpControllerClient` |
| FR-08 | `PacketController`, `ForwardingService`, `HopRecord`, `ForwardingResult` |
| FR-09 | `exceptions.py` (ambas apps), manejadores de errores |
| FR-10 | `ForwardingLogDAO`, `JsonLinesForwardingLogDAO`, `ForwardingService` |
