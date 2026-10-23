# 04 — Contrato de API

Todas las respuestas son `application/json`. Los nombres de endpoints y campos están en inglés (convención del contrato). Los puertos por defecto son **8000** (Controller) y **8001** (Router).

**Formato único de error** (todas las apps, todos los endpoints):
```json
{"error": {"code": "NODE_NOT_FOUND", "message": "Node 'Z' does not exist", "details": {"node": "Z"}}}
```

Resumen:

| App | Método y endpoint | Propósito | Req. |
|---|---|---|---|
| Controller | `GET /topology` | Topología activa con estado de enlaces | FR-05 |
| Controller | `GET /route?src=&dst=&metric=` | Ruta seleccionada, costo y versión | FR-03, FR-05 |
| Controller | `POST /links/fail` | Deshabilitar un enlace existente | FR-06 |
| Controller | `POST /links/restore` | Restablecer un enlace existente | FR-06 |
| Router | `POST /packets` | Simular reenvío; devolver trace y estado | FR-07, FR-08, FR-10 |
| Ambas | `GET /health` | Disponibilidad | FR-05, FR-09 |

---

## 1. Controller

### 1.1 `GET /health`
**200**
```json
{"status": "ok", "service": "controller", "topology_loaded": true, "topology_version": 1}
```
Si la topología no se pudo cargar: **200** con `{"status": "degraded", "service": "controller", "topology_loaded": false, "topology_version": 0}` (el proceso sigue vivo).

### 1.2 `GET /topology`
**200**
```json
{
  "topology_version": 1,
  "nodes": ["A", "B", "C", "D", "E", "F"],
  "links": [
    {"node_a": "A", "node_b": "B", "delay_ms": 10, "bandwidth_mbps": 10, "loss_prob": 0.01, "status": "active"}
  ]
}
```
| Código | `error.code` | Causa |
|---|---|---|
| 503 | `TOPOLOGY_UNAVAILABLE` | Archivo inexistente, corrupto o topología inválida |

### 1.3 `GET /route`
**Query:** `src` (obligatorio), `dst` (obligatorio), `metric` (opcional: `delay` \| `bandwidth` \| `loss`; por defecto `delay`).

Ejemplo: `GET /route?src=A&dst=D&metric=delay`

**200**
```json
{
  "src": "A",
  "dst": "D",
  "metric": "delay",
  "path": ["A", "B", "D"],
  "hop_costs": [10.0, 10.0],
  "total_cost": 20.0,
  "topology_version": 1
}
```
| Código | `error.code` | Causa |
|---|---|---|
| 400 | `INVALID_PARAMETER` | Falta `src` o `dst`, valor vacío o `metric` no soportada |
| 404 | `NODE_NOT_FOUND` | `src` o `dst` no existe (`details.node` indica cuál) |
| 404 | `ROUTE_NOT_FOUND` | Nodos válidos pero sin camino activo (`details.src`, `details.dst`) |
| 503 | `TOPOLOGY_UNAVAILABLE` | Topología no disponible |

### 1.4 `POST /links/fail` y `POST /links/restore`
**Cuerpo**
```json
{"node_a": "B", "node_b": "D"}
```
El orden de los nodos no importa (`B–D` equivale a `D–B`).

**200**
```json
{"link": {"node_a": "B", "node_b": "D", "status": "failed"}, "topology_version": 2}
```
(`status` es `"active"` en `/links/restore`.)

| Código | `error.code` | Causa |
|---|---|---|
| 400 | `INVALID_PARAMETER` | Cuerpo ausente, campos faltantes o vacíos |
| 404 | `LINK_NOT_FOUND` | El par no es un enlace de la topología |
| 409 | `LINK_ALREADY_FAILED` | `fail` sobre un enlace ya fallado |
| 409 | `LINK_ALREADY_ACTIVE` | `restore` sobre un enlace ya activo |
| 503 | `TOPOLOGY_UNAVAILABLE` | Topología no disponible |

---

## 2. Router

### 2.1 `GET /health`
**200**
```json
{"status": "ok", "service": "router"}
```
El Router responde 200 aunque el Controller esté caído (NFR-11).

### 2.2 `POST /packets`
**Cuerpo**
```json
{"packet_id": "pkt-001", "src": "A", "dst": "D", "metric": "delay", "payload": "hello"}
```
`packet_id`, `src`, `dst` obligatorios; `metric` opcional (por defecto `delay`); `payload` opcional.

**200 — entregado**
```json
{
  "packet_id": "pkt-001",
  "status": "DELIVERED",
  "src": "A",
  "dst": "D",
  "metric": "delay",
  "route": {"path": ["A", "B", "D"], "total_cost": 20.0, "topology_version": 1},
  "trace": [
    {"hop": 1, "from_node": "A", "to_node": "B", "status": "FORWARDED"},
    {"hop": 2, "from_node": "B", "to_node": "D", "status": "FORWARDED"}
  ],
  "reason": null,
  "log_persisted": true,
  "warnings": [],
  "timestamp": "2026-10-20T15:04:05Z"
}
```

**200 — inalcanzable** (el Controller respondió `404 ROUTE_NOT_FOUND`)
```json
{
  "packet_id": "pkt-002",
  "status": "UNREACHABLE",
  "src": "A",
  "dst": "F",
  "metric": "delay",
  "route": null,
  "trace": [],
  "reason": "ROUTE_NOT_FOUND",
  "log_persisted": true,
  "warnings": [],
  "timestamp": "2026-10-20T15:05:10Z"
}
```

**200 — fallo al registrar** (la simulación termina bien): igual que el primero con `"log_persisted": false` y `"warnings": ["Forwarding log could not be persisted"]`.

| Código | `error.code` | Causa |
|---|---|---|
| 400 | `INVALID_PARAMETER` | Campos obligatorios faltantes o vacíos, `metric` no soportada |
| 404 | `NODE_NOT_FOUND` | El Controller indicó que `src` o `dst` no existe (propagado) |
| 503 | `CONTROLLER_UNAVAILABLE` | Conexión rechazada o 5xx del Controller |
| 503 | `CONTROLLER_TIMEOUT` | El Controller no respondió dentro de `CONTROLLER_TIMEOUT_S` |
| 500 | `INTERNAL_ERROR` | Error no previsto (el proceso sigue activo) |

---

## 3. Reglas del contrato

1. `metric` se valida en **ambas** apps (400) para fallar rápido; el costo real solo lo calcula el Controller.
2. `topology_version` permite al Router y al cliente saber con qué estado de la red se decidió la ruta.
3. Un resultado `UNREACHABLE` no es un error HTTP en el Router (decisión A-03); sí lo es en el Controller (404).
4. El Router traduce las respuestas del Controller así: `200` → `RouteInfo`; `404 ROUTE_NOT_FOUND` → resultado `UNREACHABLE`; `404 NODE_NOT_FOUND` → 404 propagado; `400` → 400 propagado; fallo de red, timeout o 5xx → 503.
5. FastAPI genera `/docs` (OpenAPI); este documento es la referencia aprobada y las pruebas (TC-11, TC-16) verifican que la implementación coincide.
6. Los esquemas pueden refinarse **solo antes de la congelación**; después, cada cambio se registra en `01-requirements.md` §9.
