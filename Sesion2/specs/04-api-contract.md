# 04 — Contrato de API

Versión 1.1 (2026-10-26). Cambios respecto a 1.0 registrados en `01-requirements.md` §9 (CH-02, CH-03, CH-09).

Todas las respuestas son `application/json`. Los nombres de endpoints y campos están en inglés (convención del contrato). Los puertos por defecto son **8000** (Controller) y **8001** (Router).

**Formato único de error** (todas las apps, todos los endpoints):
```json
{"error": {"code": "NODE_NOT_FOUND", "message": "Node 'Z' does not exist", "details": {"node": "Z"}}}
```

Resumen:

| App | Método y endpoint | Propósito | Req. |
|---|---|---|---|
| Controller | `GET /topology` | Topología activa con estado de enlaces (una instantánea) | FR-05, NFR-12 |
| Controller | `GET /route?src=&dst=&metric=` | Ruta seleccionada, costo y versión de la instantánea usada | FR-03, FR-05, NFR-12 |
| Controller | `POST /links/fail` | Deshabilitar un enlace existente | FR-06 |
| Controller | `POST /links/restore` | Restablecer un enlace existente | FR-06 |
| Router | `POST /packets` | Simular reenvío; devolver trace, estado y estado de persistencia | FR-07, FR-08, FR-10 |
| Ambas | `GET /health` | Disponibilidad | FR-05, FR-09 |

---

## 1. Controller

**Garantía de consistencia (A-14, `02` §7.1).** Cada respuesta del Controller se arma a partir de **una sola** instantánea de topología. En particular, en `GET /route` los campos `path`, `hop_costs`, `total_cost` y `topology_version` corresponden exactamente al mismo estado de la red; en `GET /topology`, `topology_version`, `nodes` y `links` también. Una consulta que empieza después de recibir el 200 de un `fail`/`restore` ve esa versión o una posterior.

### 1.1 `GET /health`
**200**
```json
{"status": "ok", "service": "controller", "topology_loaded": true, "topology_version": 1}
```
Si la topología no se pudo cargar: **200** con `{"status": "degraded", "service": "controller", "topology_loaded": false, "topology_version": 0}` (el proceso sigue vivo). `/health` **no** intenta cargar la topología (usa `peek_snapshot()`); los reintentos ocurren en los endpoints que la necesitan (A-13).

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

**Esquema `RouteResponse` (lo valida el Router, A-15)**

| Campo | Tipo | Restricción |
|---|---|---|
| `src`, `dst` | string | No vacíos; iguales a los de la consulta |
| `metric` | string | `delay` \| `bandwidth` \| `loss`; igual al de la consulta |
| `path` | array de string | No vacío; `path[0] = src`; `path[-1] = dst`; sin nodos repetidos |
| `hop_costs` | array de number | `len = len(path) − 1`; cada valor ≥ 0 |
| `total_cost` | number | ≥ 0 |
| `topology_version` | integer | ≥ 1 |

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
(`status` es `"active"` en `/links/restore`.) `topology_version` es la versión de la instantánea creada por **esta** operación. Las operaciones de cambio se procesan de una en una: si llegan dos `fail` simultáneos sobre el mismo enlace, uno recibe 200 y el otro 409.

| Código | `error.code` | Causa |
|---|---|---|
| 400 | `INVALID_PARAMETER` | Cuerpo ausente, campos faltantes o vacíos |
| 404 | `LINK_NOT_FOUND` | El par no es un enlace de la topología |
| 409 | `LINK_ALREADY_FAILED` | `fail` sobre un enlace ya fallado (versión sin cambios) |
| 409 | `LINK_ALREADY_ACTIVE` | `restore` sobre un enlace ya activo (versión sin cambios) |
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

**Esquema `ForwardingResultResponse`**

| Campo | Tipo | Significado |
|---|---|---|
| `packet_id`, `src`, `dst`, `metric` | string | Datos del paquete |
| `status` | `"DELIVERED"` \| `"UNREACHABLE"` | **Resultado de la simulación** |
| `route` | objeto `{path, total_cost, topology_version}` o `null` | Ruta entregada por el Controller (`null` si `UNREACHABLE`) |
| `trace` | array de `{hop, from_node, to_node, status}` | Un registro por salto (`[]` si `UNREACHABLE`) |
| `reason` | string o `null` | `"ROUTE_NOT_FOUND"` si `UNREACHABLE`; `null` si `DELIVERED` |
| `log_persisted` | boolean | **Resultado de la persistencia**: `true` solo si el registro quedó escrito de forma durable |
| `warnings` | array de `{code, message}` | Avisos no fatales; hoy solo `PERSISTENCE_ERROR` |
| `timestamp` | string ISO 8601 UTC | Momento en que se armó el resultado |

**Cómo interpretar la respuesta (SPDR-03).** HTTP 200 significa **simulación completada**. La simulación además es **auditable** solo si `log_persisted` es `true`. Un cliente que necesita trazabilidad debe comprobar `log_persisted` y no solo el código HTTP.

**200 — entregado y registrado** (fila D1)
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

**200 — entregado, registro NO garantizado** (fila D2)
```json
{
  "packet_id": "pkt-003",
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
  "log_persisted": false,
  "warnings": [{"code": "PERSISTENCE_ERROR", "message": "Forwarding log could not be persisted"}],
  "timestamp": "2026-10-20T15:06:00Z"
}
```

**200 — inalcanzable y registrado** (el Controller respondió `404 ROUTE_NOT_FOUND`; fila D3)
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

**200 — inalcanzable, registro NO garantizado** (fila D4)
```json
{
  "packet_id": "pkt-004",
  "status": "UNREACHABLE",
  "src": "A",
  "dst": "F",
  "metric": "delay",
  "route": null,
  "trace": [],
  "reason": "ROUTE_NOT_FOUND",
  "log_persisted": false,
  "warnings": [{"code": "PERSISTENCE_ERROR", "message": "Forwarding log could not be persisted"}],
  "timestamp": "2026-10-20T15:07:30Z"
}
```

**Errores** (en ninguno se crea `ForwardingResult` ni se escribe en el log)

| Código | `error.code` | Causa | `details` |
|---|---|---|---|
| 400 | `INVALID_PARAMETER` | Campos obligatorios faltantes o vacíos, `metric` no soportada; o 400 propagado del Controller | `field`; `source: "controller"` si viene del Controller |
| 404 | `NODE_NOT_FOUND` | El Controller indicó que `src` o `dst` no existe (propagado) | `node` |
| 502 | `CONTROLLER_BAD_RESPONSE` | La respuesta del Controller no cumple este contrato (A-15) | `reason` (p. ej. `"invalid_json"`, `"schema_mismatch"`, `"path_dst_mismatch"`, `"unexpected_status"`), `upstream_status` |
| 503 | `CONTROLLER_UNAVAILABLE` | Conexión rechazada, 5xx o `503 TOPOLOGY_UNAVAILABLE` del Controller | `upstream_status`, `upstream_code` (si hubo respuesta) |
| 503 | `CONTROLLER_TIMEOUT` | El Controller no respondió dentro de `CONTROLLER_TIMEOUT_S` | `timeout_s` |
| 500 | `INTERNAL_ERROR` | Error no previsto (el proceso sigue activo) | — |

### 2.3 Formato del registro persistido (`forwarding_log.jsonl`)

Una línea JSON por `ForwardingResult` (JSON Lines, UTF-8, terminada en `\n`). Contiene todos los campos de la respuesta **excepto** `log_persisted` y `warnings`, que describen la propia escritura y se calculan después de ella:

```json
{"packet_id": "pkt-002", "status": "UNREACHABLE", "src": "A", "dst": "F", "metric": "delay", "route": null, "trace": [], "reason": "ROUTE_NOT_FOUND", "timestamp": "2026-10-20T15:05:10Z"}
```

Semántica de escritura (A-16): una escritura completa por registro, serializada con un lock y seguida de `fsync`; a lo sumo una vez (sin reintentos); los fragmentos de escrituras parciales quedan aislados en su propia línea y `find_all()` los omite.

---

## 3. Reglas del contrato

1. `metric` se valida en **ambas** apps (400) para fallar rápido; el costo real solo lo calcula el Controller.
2. `topology_version` permite al Router y al cliente saber con qué estado de la red se decidió la ruta; siempre es la versión de la misma instantánea que produjo la ruta (A-14).
3. Un resultado `UNREACHABLE` no es un error HTTP en el Router (decisión A-03); sí lo es en el Controller (404).
4. El Router traduce **todas** las respuestas del Controller con esta tabla (la implementa `HttpControllerClient`; es la misma que `01` §7.2):

   | Respuesta del Controller | Acción del Router |
   |---|---|
   | `200` que cumple el esquema `RouteResponse` (§1.3) | `RouteInfo` → simulación `DELIVERED` |
   | `200` que no es JSON, no cumple el esquema o tiene ruta incoherente | `502 CONTROLLER_BAD_RESPONSE` |
   | `404` con `error.code = ROUTE_NOT_FOUND` | Resultado `UNREACHABLE` (HTTP 200) |
   | `404` con `error.code = NODE_NOT_FOUND` | `404 NODE_NOT_FOUND` propagado |
   | `404` con otro código, sin código o sin formato de error | `502 CONTROLLER_BAD_RESPONSE` |
   | `400` con `error.code = INVALID_PARAMETER` | `400 INVALID_PARAMETER` propagado (`details.source = "controller"`) |
   | `503` (incluido `TOPOLOGY_UNAVAILABLE`) u otro `5xx` | `503 CONTROLLER_UNAVAILABLE` (`details.upstream_status`, `details.upstream_code`) |
   | Conexión rechazada o error de red | `503 CONTROLLER_UNAVAILABLE` |
   | Sin respuesta dentro del timeout | `503 CONTROLLER_TIMEOUT` |
   | Cualquier otro código (`3xx`, `401`, `403`, `409`, `422`, …) | `502 CONTROLLER_BAD_RESPONSE` (`reason = "unexpected_status"`) |

5. Persistencia: todo resultado `DELIVERED` o `UNREACHABLE` se intenta guardar exactamente una vez antes de responder; un fallo de persistencia nunca cambia el código HTTP ni el `status`, solo `log_persisted` y `warnings`.
6. FastAPI genera `/docs` (OpenAPI); este documento es la referencia aprobada y las pruebas (TC-11, TC-16, TC-24, TC-25) verifican que la implementación coincide.
7. Los esquemas pueden refinarse **solo antes de la congelación**; después, cada cambio se registra en `01-requirements.md` §9.
