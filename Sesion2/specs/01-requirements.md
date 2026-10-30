# 01 — Especificación de Requisitos: Controlador y Enrutador SDN

| Campo | Valor |
|---|---|
| Curso | Informática para Telecomunicaciones |
| Proyecto | Simulación SDN a nivel de aplicación (Controller + Router) |
| Equipo | Estudiante A (Controller) · Estudiante B (Router) |
| Fecha | 2026-10-20 (v1.0) · 2026-10-26 (v1.1) |
| Versión | **1.1** — línea base congelada 1.0 + correcciones de la revisión SPDR (ver §9) |
| Estado | Congelado. Todo cambio posterior se registra en §9 con motivo y artefactos afectados. |
---

## 1. Introducción

### 1.1 Propósito
Definir **qué** debe hacer el sistema (requisitos funcionales y no funcionales, entradas, salidas, errores y criterios de aceptación verificables). El **cómo** se describe en `02-static-architecture.md` y `03-dynamic-architecture.md`.

### 1.2 Alcance
Dos aplicaciones Python independientes (procesos separados) que se comunican por HTTP/JSON:

- **Controller (plano de control):** carga la topología, administra el estado de los enlaces, calcula rutas con Dijkstra y las expone por API REST.
- **Router (plano de datos):** recibe paquetes simulados, **pide** la ruta al Controller, simula el reenvío salto a salto y registra el resultado.

Es una **simulación a nivel de aplicación**, no una solución OpenFlow para producción.

### 1.3 Fuera de alcance
Protocolos reales (OpenFlow, BGP/OSPF), tráfico de red real, autenticación/autorización, persistencia del estado de fallos entre reinicios, alta disponibilidad, balanceo de carga, **varias instancias (workers) del mismo proceso** y escritura del log de reenvíos desde varios procesos Router a la vez.

### 1.4 Actores
| Actor | Descripción |
|---|---|
| Cliente / Usuario | Envía paquetes simulados al Router (`POST /packets`). |
| Administrador | Simula fallos y restablecimientos de enlaces en el Controller. |
| Router SDN | Cliente HTTP del Controller; ejecuta el reenvío simulado. |
| Controller SDN | Servidor de decisiones de ruta y dueño de la topología. |
| Sistema de archivos | Origen de la topología (JSON) y destino del registro de reenvíos; **solo accesible vía DAO**. |

### 1.5 Glosario
| Término | Definición |
|---|---|
| Topología | Conjunto de nodos y enlaces con atributos físicos. |
| Enlace | Conexión **bidireccional y simétrica** entre dos nodos, con `delay_ms`, `bandwidth_mbps`, `loss_prob` y estado (`active` / `failed`). |
| Métrica | Criterio de costo: `delay`, `bandwidth` (costo = 1/b) o `loss` (costo = −ln(1−p)). |
| Ruta | Lista ordenada de nodos de origen a destino y su costo total acumulado. |
| Versión de topología | Entero que parte en 1 y aumenta en 1 con cada fallo/restablecimiento exitoso. |
| **Instantánea (snapshot) de topología** | Objeto `Topology` **inmutable** que representa un estado completo (nodos, enlaces con su estado y `version`). Cada cambio crea una instantánea nueva; nunca se modifica una existente (decisión A-14). |
| DAO | *Data Access Object*: abstracción que encapsula la lectura/escritura de datos. |
| Trace | Registro salto a salto de la simulación de reenvío. |
| **Simulación completada** | El Router respondió HTTP 200 con un `ForwardingResult` (`DELIVERED` o `UNREACHABLE`). |
| **Simulación auditable** | Simulación completada **y** con `log_persisted: true`: el registro quedó escrito de forma durable en el log (decisión A-16). |

### 1.6 Casos de uso

| ID | Caso de uso | Actor | Flujo principal | Flujo alterno / error | Requisitos |
|---|---|---|---|---|---|
| UC-01 | Iniciar el Controller y cargar la topología | Administrador | El Controller lee el JSON vía `TopologyDAO` y queda `topology_loaded: true`. | Archivo inexistente o inválido: estado `degraded`, el proceso sigue vivo. | FR-01, FR-02, NFR-05 |
| UC-02 | Consultar la topología activa | Cliente / Administrador | `GET /topology` devuelve nodos, enlaces y estado de **una sola** instantánea. | Topología no disponible: 503. | FR-05, NFR-12 |
| UC-03 | Consultar una ruta según una métrica | Cliente / Router | `GET /route` devuelve ruta, costo y la versión de la instantánea usada. | 400 parámetro inválido; 404 nodo o ruta ausente; 503 sin topología. | FR-03, FR-04, FR-05, NFR-12 |
| UC-04 | Simular la caída de un enlace | Administrador | `POST /links/fail` y la versión aumenta en 1. | 404 enlace inexistente; 409 ya fallado. | FR-06 |
| UC-05 | Restablecer un enlace | Administrador | `POST /links/restore` y la versión aumenta en 1. | 404 enlace inexistente; 409 ya activo. | FR-06 |
| UC-06 | Enviar un paquete y obtener el trace | Cliente | `POST /packets`: el Router pide la ruta, simula el reenvío, **registra el resultado** y responde 200 `DELIVERED`. | Fallo al registrar: 200 `DELIVERED` con `log_persisted: false` y aviso `PERSISTENCE_ERROR` (simulación completada pero **no auditable**). | FR-07, FR-08, FR-10 |
| UC-07 | Enviar un paquete a un destino inalcanzable o con nodo inválido | Cliente | Destino sin camino: el Router responde 200 `UNREACHABLE` **y lo registra**. Nodo inexistente: propaga 404 `NODE_NOT_FOUND` (no se registra). | Fallo al registrar un `UNREACHABLE`: 200 `UNREACHABLE` con `log_persisted: false` y aviso. | FR-03, FR-08, FR-09, FR-10 |
| UC-08 | Enviar un paquete con el Controller caído, lento o con respuesta inválida | Cliente | Caído o lento: el Router responde 503 y sigue vivo. Respuesta inválida: 502 `CONTROLLER_BAD_RESPONSE`. No se registra nada en el log. | n/a | FR-07, FR-09, NFR-11 |
| UC-09 | Verificar la disponibilidad | Cliente | `GET /health` en cada app. | Controller sin topología: `degraded`. | FR-05 |
---

## 2. Supuestos y decisiones sobre ambigüedades

| ID | Ambigüedad | Decisión | Afecta |
|---|---|---|---|
| A-01 | ¿Grafo dirigido o no dirigido? | **No dirigido** (`networkx.Graph`). Un enlace A–B sirve en ambos sentidos con los mismos atributos. El enlace se identifica por el par de nodos sin importar el orden. | FR-02, FR-06 |
| A-02 | ¿Se combinan métricas? | **No.** Cada consulta usa **una** métrica: `delay`, `bandwidth` o `loss`. Si falta `metric`, se usa `delay` por defecto. | FR-03, FR-04, FR-05 |
| A-03 | ¿"Sin ruta" es error o resultado válido? | **Controller:** `404 ROUTE_NOT_FOUND` (nodos válidos pero desconectados), distinto de `404 NODE_NOT_FOUND` (nodo inexistente). **Router:** un destino inalcanzable se reporta como resultado de simulación con estado `UNREACHABLE` (HTTP 200) y se registra; un nodo inexistente propaga `404 NODE_NOT_FOUND`. | FR-05, FR-08, FR-09 |
| A-04 | ¿Qué pasa si el Controller no responde **o responde algo inesperado**? | Sin respuesta: el Router devuelve `503` (`CONTROLLER_UNAVAILABLE` o `CONTROLLER_TIMEOUT`) sin reintentos y sigue vivo. Timeout configurable, por defecto 2 s. Respuesta que no cumple el contrato: `502 CONTROLLER_BAD_RESPONSE` (ver A-15). | FR-07, FR-09, NFR-11 |
| A-05 | ¿Un enlace con p = 1? | Es **válido en el archivo** pero **inutilizable**: se excluye del grafo ponderado para **todas** las métricas. | FR-04 |
| A-06 | ¿Fallar un enlace ya caído, o restaurar uno activo? | `409 Conflict` (`LINK_ALREADY_FAILED` / `LINK_ALREADY_ACTIVE`), sin cambiar la versión. Enlace inexistente: `404 LINK_NOT_FOUND`. | FR-06 |
| A-07 | ¿Se persiste el estado de fallos? | **No.** Vive en memoria; al reiniciar el Controller todo vuelve al estado del JSON. | FR-06 |
| A-08 | ¿Origen = destino? | Ruta válida `[src]` con costo 0 y `hop_costs` vacío. | FR-03 |
| A-09 | ¿Quién valida que los nodos existan? | **Solo el Controller.** El Router solo valida el **formato** de entrada: campos presentes y no vacíos, y `metric` dentro de los valores permitidos (`delay`, `bandwidth`, `loss`). Lo hace el esquema `PacketRequest` (capa Vista), no un servicio; el Router nunca evalúa costos ni existencia de nodos. | FR-07, FR-09 |
| A-10 | ¿Qué se registra en el log de reenvíos? | **Todo** `ForwardingResult` generado, sea `DELIVERED` o `UNREACHABLE`, se intenta guardar **exactamente una vez** con `ForwardingLogDAO.save()` antes de responder, como una línea JSON (JSON Lines). Las solicitudes rechazadas por error (400/404/502/503/500) no generan resultado y no se registran. Justificación: el log registra lo que ocurrió con el paquete en la red simulada; un error de solicitud o del Controller significa que el reenvío nunca ocurrió y queda en los registros HTTP de la aplicación. La tabla completa está en §7.2. | FR-08, FR-10 |
| A-11 | ¿Quién valida la topología? | El **DAO solo lee y parsea**; la **validación semántica** (nodos referenciados, rangos) la hace `TopologyService` (lógica de dominio, no de persistencia). | FR-01, FR-02 |
| A-12 | ¿Qué hace el Router con un fallo del Controller a mitad del reenvío? | Fuera de alcance: la ruta se consulta **una vez por paquete** y se simula sobre esa instantánea (`topology_version`). Si la topología cambia después, el resultado sigue indicando la versión con la que se decidió. | FR-08 |
| A-13 | ¿Cuándo se carga la topología? | Se intenta al **arrancar** el Controller (`ensure_loaded`). Si falla, el proceso sigue vivo (`degraded`) y se **reintenta** en la siguiente petición que requiera la topología. Los reintentos concurrentes se serializan: solo un hilo carga a la vez (A-14). | FR-01, FR-09 |
| **A-14** | ¿Cómo se sincronizan consultas de ruta simultáneas con fallos/restablecimientos de enlaces? *(SPDR-02)* | **Instantáneas inmutables con intercambio atómico (copy-on-write).** `TopologyService` guarda una referencia a la `Topology` vigente, que es inmutable. Las **escrituras** (`fail_link`, `restore_link`, carga inicial) se **serializan** con un `threading.Lock`: crean una instantánea nueva con `version + 1` y reemplazan la referencia dentro del lock. Las **lecturas** toman la referencia vigente **una sola vez** (`get_snapshot()`) y calculan todo (validación de nodos, grafo ponderado, Dijkstra, `topology_version`) sobre esa misma instantánea, sin tener el lock durante Dijkstra. **Garantía:** la ruta, sus costos y su `topology_version` provienen **exactamente del mismo estado** de la topología (ver garantías G1–G5 en `02` §7.1). El Controller se ejecuta con **un solo worker** de Uvicorn porque el estado vive en memoria del proceso. | FR-03, FR-06, NFR-12 |
| **A-15** | ¿Cómo se clasifican las respuestas del Controller que no son errores válidos de la aplicación? *(SPDR-03)* | `HttpControllerClient` valida **toda** respuesta contra `04-api-contract.md`. Se considera **respuesta inválida** → `502 CONTROLLER_BAD_RESPONSE`: cuerpo que no es JSON; 200 que no cumple el esquema `RouteResponse`; 200 con ruta incoherente (`path` vacío, `path[0] ≠ src`, `path[-1] ≠ dst`, nodos repetidos, `len(hop_costs) ≠ len(path) − 1`, costos negativos, `topology_version < 1`); 4xx con un `error.code` no documentado para ese estado o sin formato de error; cualquier código no previsto (3xx, 401, 409, 422…). `503 TOPOLOGY_UNAVAILABLE` y otros 5xx → `503 CONTROLLER_UNAVAILABLE` con `details.upstream_status` y `details.upstream_code`. Validar el formato de la ruta **no** es calcular rutas: el Router sigue sin evaluar costos ni caminos. | FR-07, FR-09 |
| **A-16** | ¿Qué significa exactamente "registrado" y qué pasa si la escritura falla a medias? *(SPDR-03)* | (1) El DAO serializa el registro completo **en memoria** antes de tocar el archivo; si falla la serialización, no escribe nada. (2) Agrega la línea con **una sola** escritura en modo *append*, bajo un `threading.Lock`, y luego `flush()` + `os.fsync()`. (3) `log_persisted: true` **solo** si `save()` terminó sin excepción después del `fsync`. (4) Cualquier excepción dentro de `save()`, incluso después de haber escrito bytes parciales, se trata como **no persistido**: el DAO la envuelve en `PersistenceError` y el Router responde 200 con `log_persisted: false` y el aviso `PERSISTENCE_ERROR`. (5) Si quedó un fragmento, la siguiente escritura inserta antes un salto de línea (si el archivo no termina en `\n`) para aislarlo, y `find_all()` **omite** las líneas que no son JSON válido y las cuenta, sin fallar. (6) Semántica **a lo sumo una vez** (sin reintentos): `log_persisted: false` significa "persistencia **no garantizada**", no "garantizado ausente" (p. ej., si la escritura funcionó pero el `fsync` falló, la línea podría existir). | FR-10 |

---

## 3. Modelo de datos de entrada y costos

### 3.1 Formato del archivo de topología (`data/topology.json`)
```json
{
  "nodes": ["A", "B", "C", "D", "E", "F"],
  "links": [
    {"node_a": "A", "node_b": "B", "delay_ms": 10, "bandwidth_mbps": 10,  "loss_prob": 0.01},
    {"node_a": "B", "node_b": "D", "delay_ms": 10, "bandwidth_mbps": 10,  "loss_prob": 0.01}
  ]
}
```
Reglas de validez: ids de nodo únicos y no vacíos; cada enlace referencia nodos existentes; sin lazos (`node_a ≠ node_b`); sin enlaces duplicados (par no ordenado); `delay_ms ≥ 0`; `bandwidth_mbps > 0`; `0 ≤ loss_prob ≤ 1`. Se permiten nodos sin enlaces.

### 3.2 Costos de enlace (todos ≥ 0)
| Métrica | Costo | Dominio | Nota |
|---|---|---|---|
| `delay` | `d` | `d ≥ 0` | Suma de retardos a lo largo del camino. |
| `bandwidth` | `1 / b` | `b > 0` | **Heurística**: la suma de 1/b no equivale a maximizar el ancho de banda del cuello de botella. |
| `loss` | `−ln(1 − p)` | `0 ≤ p < 1` | La suma equivale a −ln(P(éxito)) si las pérdidas son **independientes**. `p = 1` → enlace inutilizable. |

Dijkstra exige pesos **no negativos**; con pesos negativos la garantía de optimalidad se pierde.

---

## 4. Requisitos funcionales

Prioridad **Alta (Must)** para todos. Formato de criterios: *Dado / Cuando / Entonces*. Los casos `TC-xx` están definidos en `06-test-specification.md`; los `RA-xx` son puntos de la revisión arquitectónica manual (`06` §5).

### FR-01 — Cargar la topología desde JSON mediante un DAO
- **Historia de usuario:** Como Controller SDN, quiero cargar la topología desde un archivo JSON a través de `TopologyDAO` para separar el almacenamiento de la lógica del sistema.
- **Actor:** Controller. **Precondición:** la ruta del archivo es configurable (NFR-05).
- **Entradas:** archivo JSON con nodos, enlaces y atributos físicos.
- **Salidas:** instantánea `Topology` inmutable en memoria (versión 1), entregada por el DAO y validada por `TopologyService`.
- **Errores:** archivo inexistente, ilegible o JSON corrupto → error controlado `TOPOLOGY_UNAVAILABLE`; el proceso **no se detiene** (estado `degraded`, los endpoints que requieren topología responden 503).

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-01.1 | Dado un JSON válido, cuando el Controller arranca, entonces `GET /health` indica `topology_loaded: true` y `GET /topology` lista todos los nodos y enlaces. | TC-17, TC-21, TC-16 |
| AC-01.2 | Dado un archivo inexistente, cuando el Controller arranca, entonces el proceso sigue activo, `/health` indica `degraded` y `GET /route` responde 503. | TC-17 |
| AC-01.3 | Dado un JSON corrupto, entonces ocurre lo mismo que en AC-01.2. | TC-17 |
| AC-01.4 | Ni los controladores HTTP ni los servicios contienen acceso directo a archivos; solo usan `TopologyDAO`. | TC-13, RA-03 (inspección) |

### FR-02 — Soportar topologías válidas arbitrarias con NetworkX
- **Historia de usuario:** Como Controller SDN, quiero representar cualquier topología válida con NetworkX para no depender de un diseño preprogramado.
- **Entradas:** `Topology` entregada por `TopologyDAO`. **Salidas:** `networkx.Graph` (no dirigido, decisión A-01) con atributos por enlace.
- **Errores:** `INVALID_TOPOLOGY` si un enlace referencia un nodo inexistente, hay duplicados, lazos o atributos fuera de rango.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-02.1 | Dadas topologías distintas (lineal, anillo, malla, con nodo aislado), cuando se cargan, entonces se construyen **sin modificar código**, solo cambiando el JSON. | TC-17 |
| AC-02.2 | Dado un enlace que referencia un nodo inexistente, entonces la carga falla con `INVALID_TOPOLOGY` y el proceso sigue activo. | TC-17 |
| AC-02.3 | Dado un nodo sin enlaces, entonces el nodo existe en la topología y es consultable. | TC-11 |

### FR-03 — Calcular rutas más cortas con Dijkstra
- **Historia de usuario:** Como servicio de enrutamiento, quiero calcular rutas de costo mínimo con Dijkstra para elegir el camino más eficiente.
- **Entradas:** `src`, `dst`, métrica y la instantánea de topología vigente. **Salidas:** lista ordenada de nodos, costo total acumulado, costos por salto y `topology_version` **de la misma instantánea**.
- **Errores:** `NODE_NOT_FOUND` (nodo inexistente) y `ROUTE_NOT_FOUND` (sin camino viable), siempre distinguibles.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-03.1 | Dada la topología de referencia (`06-test-specification.md`), cuando se consulta A→D con `delay`, entonces la ruta es `[A,B,D]` con costo 20. | TC-01 |
| AC-03.2 | Dado `src == dst`, entonces la ruta es `[src]` con costo 0. | TC-01 |
| AC-03.3 | Dado un destino aislado (F), entonces el resultado es `ROUTE_NOT_FOUND`. | TC-07, TC-11 |
| AC-03.4 | La lógica de Dijkstra reside únicamente en `RoutingService`, no en controladores HTTP. | TC-23 (sustitución), TC-12 y RA-02 (inspección) |
| **AC-03.5** | Dadas consultas de ruta concurrentes con fallos/restablecimientos, entonces cada respuesta es coherente con su `topology_version` (la ruta es la óptima de **esa** versión) y nunca mezcla estados. | TC-20 |

### FR-04 — Modelar costos de enlace (retardo, ancho de banda inverso, pérdida)
- **Historia de usuario:** Como servicio de enrutamiento, quiero transformar los atributos del enlace en un costo no negativo para que Dijkstra refleje el impacto real de transmisión.
- **Entradas:** atributos crudos `(d, b, p)` y la métrica. **Salidas:** costo numérico ≥ 0.
- **Errores:** `INVALID_LINK_METRICS` si `b ≤ 0`, `p < 0`, `p > 1` o `d < 0`; el enlace con `p = 1` es inutilizable y se excluye (A-05).

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-04.1 | `delay`: costo = d. `bandwidth`: costo = 1/b. `loss`: costo = −ln(1−p) (p = 0,5 → ≈ 0,6931). | TC-10 |
| AC-04.2 | Dado `p = 1`, entonces el enlace no entra al grafo ponderado (no hay `ln(0)` ni división por cero). | TC-10 |
| AC-04.3 | Dado `b = 0` o `b < 0`, entonces se produce `INVALID_LINK_METRICS` controlado. | TC-10 |
| AC-04.4 | Todo peso entregado a Dijkstra es ≥ 0. | TC-10 |
| AC-04.5 | Con la topología de referencia, A→D usa `[A,B,D]` con `delay` y `loss`, y `[A,C,D]` con `bandwidth`. | TC-02 |

### FR-05 — Exponer consultas de ruta por API REST documentada
- **Historia de usuario:** Como Controller SDN, quiero exponer rutas, topología y salud por REST para que el Router las consuma por HTTP.
- **Entradas:** `GET /route?src=&dst=&metric=`. **Salidas:** JSON con `src`, `dst`, `metric`, `path`, `total_cost`, `hop_costs`, `topology_version`.
- **Errores:** 400 parámetros faltantes o métrica no soportada; 404 `NODE_NOT_FOUND` / `ROUTE_NOT_FOUND`; 503 topología no disponible.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-05.1 | Las respuestas coinciden con los esquemas y códigos de `04-api-contract.md`. | TC-11, TC-16 |
| AC-05.2 | Faltan `src` o `dst`, o `metric` inválida → 400 `INVALID_PARAMETER`. | TC-11 |
| AC-05.3 | Nodo inexistente → 404 `NODE_NOT_FOUND`; nodos desconectados → 404 `ROUTE_NOT_FOUND`. | TC-11 |
| AC-05.4 | `GET /topology` y `GET /health` existen y responden según el contrato; `GET /topology` devuelve una sola instantánea (versión y enlaces coherentes). | TC-11 |
| AC-05.5 | La API queda documentada (OpenAPI de FastAPI + `04-api-contract.md`). | Inspección |

### FR-06 — Simular fallos y restablecimiento de enlaces
- **Historia de usuario:** Como Administrador, quiero fallar y restablecer enlaces por REST para comprobar que las rutas posteriores se actualizan.
- **Entradas:** `POST /links/fail` y `POST /links/restore` con `{"node_a","node_b"}`. **Salidas:** 200 con el enlace actualizado y la nueva `topology_version`.
- **Errores:** 404 `LINK_NOT_FOUND`; 409 `LINK_ALREADY_FAILED` / `LINK_ALREADY_ACTIVE`; 400 cuerpo inválido.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-06.1 | Tras fallar B–D, A→D (`delay`) devuelve `[A,C,D]` con costo 25 (distinta a la ruta previa). | TC-03 |
| AC-06.2 | Un enlace fallado **no participa** en Dijkstra. | TC-03 |
| AC-06.3 | Tras restablecer B–D, A→D vuelve a `[A,B,D]` con costo 20. | TC-04 |
| AC-06.4 | Fallar un enlace ya fallado → 409; restaurar uno activo → 409; enlace inexistente → 404. | TC-11 |
| AC-06.5 | Cada fallo/restablecimiento exitoso incrementa `topology_version` en 1. | TC-03, TC-04 |
| **AC-06.6** | Dados dos `fail` simultáneos sobre el mismo enlace, entonces exactamente uno responde 200 y el otro 409, y la versión aumenta una sola vez (sin actualizaciones perdidas). Toda consulta que **empieza** después de recibir el 200 de un cambio ve esa versión o una posterior. | TC-20 |

### FR-07 — El Router solicita rutas al Controller por HTTP
- **Historia de usuario:** Como Router SDN, quiero pedir la ruta al Controller por HTTP para mantener la separación entre control y reenvío.
- **Entradas:** `src`, `dst`, `metric` del paquete. **Salidas:** petición `GET /route` y `RouteInfo` recibida y **validada contra el contrato**.
- **Errores:** conexión rechazada, timeout o 5xx del Controller → 503 controlado; respuesta que no cumple el contrato → 502 `CONTROLLER_BAD_RESPONSE` (A-15); el Router no se detiene.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-07.1 | El Router **no implementa** Dijkstra ni importa `networkx`. | TC-14, RA-10 (inspección) |
| AC-07.2 | Toda decisión de ruta sale del componente cliente HTTP (`HttpControllerClient`) hacia `GET /route`. | TC-05 |
| AC-07.3 | URL y timeout del Controller son configurables. | TC-19 |
| **AC-07.4** | Toda respuesta del Controller fuera del contrato (no JSON, esquema inválido, ruta incoherente, código no previsto) se clasifica según A-15 y la tabla de §7.2. | TC-25 |

### FR-08 — Simular el reenvío de paquetes
- **Historia de usuario:** Como Router SDN, quiero simular el reenvío salto a salto a lo largo de la ruta del Controller para verificar el plano de datos.
- **Entradas:** `POST /packets` con `{packet_id, src, dst, metric?, payload?}` (la ruta la obtiene el Router, **no** la envía el cliente). **Salidas:** `ForwardingResult` con estado (`DELIVERED`/`UNREACHABLE`), ruta usada y `trace`.
- **Errores:** ruta vacía/inalcanzable → estado `UNREACHABLE` con motivo explícito; nodo inexistente → 404 propagado.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-08.1 | El `trace` contiene un registro por salto, coherente con la lista de nodos del Controller (`[A,B,D]` → saltos A→B y B→D). | TC-06 |
| AC-08.2 | Destino aislado → HTTP 200, estado `UNREACHABLE`, `trace` vacío y `reason: "ROUTE_NOT_FOUND"`. | TC-07 |
| AC-08.3 | El procesamiento lo hace `ForwardingService`, no el controlador HTTP. | TC-23 (sustitución), TC-12 y RA-02 (inspección) |
| **AC-08.4** | Tanto un resultado `DELIVERED` como uno `UNREACHABLE` pasan por `ForwardingLogDAO.save()` exactamente una vez antes de responder. | TC-09, TC-24 |

### FR-09 — Gestionar nodos inválidos, destinos inalcanzables y fallos de comunicación
- **Historia de usuario:** Como sistema SDN integrado, quiero manejar errores esperados de forma controlada para que ambas aplicaciones sigan funcionando.
- **Entradas:** peticiones con datos inválidos, nodos ausentes, destinos desconectados, caída del Controller, respuestas inesperadas del Controller. **Salidas:** respuestas `{"error": {"code","message","details"}}` con HTTP 400/404/409/502/503 (ver §7).
- **Errores:** este requisito *es* la política de errores; las excepciones no previstas devuelven 500 `INTERNAL_ERROR` con el mismo formato.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-09.1 | Ninguna condición de error esperada cierra el proceso; `GET /health` sigue respondiendo. | TC-07, TC-17, TC-19 |
| AC-09.2 | La API distingue entrada inválida (400), nodo inexistente (404 `NODE_NOT_FOUND`) y ausencia de ruta (404 `ROUTE_NOT_FOUND` / `UNREACHABLE` en el Router). | TC-11, TC-07 |
| AC-09.3 | Todos los errores usan el formato único de error. | TC-11, TC-25 |
| **AC-09.4** | Cada fila de la tabla de decisión resultado/persistencia (§7.2) produce exactamente el HTTP, estado, `log_persisted` y avisos indicados. | TC-24, TC-25, TC-15 |

### FR-10 — Registrar resultados de reenvío mediante un DAO
- **Historia de usuario:** Como Router SDN, quiero persistir cada resultado con `ForwardingLogDAO` para tener un historial comprobable sin mezclar almacenamiento con lógica de dominio.
- **Entradas:** `ForwardingResult` (`DELIVERED` o `UNREACHABLE`). **Salidas:** una línea JSON agregada al log (formato del registro en `04` §2.3).
- **Errores:** sin permisos de escritura, disco lleno, error de serialización o escritura parcial → `PERSISTENCE_ERROR` capturado: la simulación se considera **completada**, pero **no auditable** (`log_persisted: false` y aviso `PERSISTENCE_ERROR` en `warnings`). Semántica exacta en A-16 y §7.2.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-10.1 | Toda operación de almacenamiento ocurre dentro de `ForwardingLogDAO`. | TC-09, TC-13 |
| AC-10.2 | `ForwardingService` no contiene `open()`, `write()` ni acceso directo a archivos. | TC-13, RA-03 |
| AC-10.3 | `ForwardingLogDAO` puede reemplazarse por un mock en pruebas. | TC-09, TC-22 |
| AC-10.4 | Si el DAO falla al guardar un `DELIVERED` **o** un `UNREACHABLE`, la respuesta es 200 con el mismo `status`, `log_persisted: false` y el aviso `PERSISTENCE_ERROR`. | TC-15, TC-24 |
| **AC-10.5** | Si la escritura falla a medias, `save()` lanza `PersistenceError`, la respuesta indica `log_persisted: false`, la siguiente escritura produce una línea válida y `find_all()` omite el fragmento sin fallar. | TC-26 |
| **AC-10.6** | Un cliente puede distinguir una simulación completada (`HTTP 200` + `status`) de una simulación auditable (`log_persisted: true`) solo con la respuesta. | TC-15, TC-24 |

---

## 5. Requisitos no funcionales

| ID | Categoría | Requisito | Criterio medible | Verificación | Prioridad de la prueba |
|---|---|---|---|---|---|
| NFR-01 | Mantenibilidad | Ambas apps implementan MVC con responsabilidades por capa documentadas. | 100 % de módulos en `controllers/`, `schemas/`, `models/`, `services/`, `dao/` (`clients/` en el Router). | Revisión arquitectónica RA-01…RA-06 + TC-23 + `02-static-architecture.md` | Obligatoria (revisión) |
| NFR-02 | Mantenibilidad | Carga, lectura y persistencia usan abstracciones DAO; los servicios no acceden a almacenamiento directo. | 0 usos de `open()`, `json.load`, `pathlib` en `services/`; los servicios funcionan igual con DAO falso o real. | TC-13 (AST), TC-21/TC-22 (sustitución), RA-03 | Recomendada |
| NFR-03 | Mantenibilidad | Dijkstra y el reenvío residen fuera de los manejadores HTTP. | 0 imports de `networkx`/`heapq` en `controllers/`; los controladores delegan en el servicio inyectado. | TC-12, TC-23, RA-02 | Obligatoria (TC-12) |
| NFR-04 | Interoperabilidad | Las interfaces HTTP/JSON cumplen el contrato aprobado. | 100 % de endpoints y esquemas coinciden con `04-api-contract.md`. | TC-11, TC-16 | Recomendada |
| NFR-05 | Configurabilidad | Puertos, ruta de topología, URL/timeout del Controller y ruta del log son configurables sin tocar código. | Cambiar variable de entorno → cambia el comportamiento. | TC-16, TC-19 | Recomendada |
| NFR-06 | Robustez | Los fallos previstos producen errores controlados y documentados; las apps siguen activas. | 0 caídas de proceso en TC-07, TC-15, TC-17, TC-19, TC-25. | Pruebas automatizadas | Obligatoria (TC-07) |
| NFR-07 | Calidad de diseño | Implementación orientada a objetos, modular, con dependencias inyectables. | Servicios reciben dependencias por constructor; sin globales ni singletons ocultos. | RA-04, RA-05 + TC-08, TC-09 | Obligatoria |
| NFR-08 | Trazabilidad | Cada requisito se vincula a tarea, componente y prueba, **clasificando el tipo de evidencia**. | 100 % de FR/NFR en la matriz, cada uno con al menos una prueba **primaria** o una inspección justificada. | `05-implementation-plan.md` §3 | Revisión |
| NFR-09 | Testabilidad | Las dependencias DAO son reemplazables por mocks/fakes. | RoutingService y ForwardingService probados sin servidor HTTP ni archivos. | TC-08, TC-09 | Obligatoria |
| **NFR-10** | Rendimiento | Una consulta de ruta responde rápido en una topología sintética grande. | Con el fixture fijo `large_topology_200n_1000l.json` (generado con semilla 42, ver `06` §4), tras 10 consultas de calentamiento, la **mediana de 3 repeticiones** del p95 (método *nearest-rank*) de 100 consultas `GET /route` **correctas** ≤ **200 ms**, medido en proceso con `TestClient` y registrando el entorno de ejecución. | TC-18 | Extensión |
| **NFR-11** | Disponibilidad / Resiliencia | Si el Controller no responde, el Router falla rápido y sigue operativo. | El Router responde 503 en ≤ **timeout + 1 s** (3 s con el valor por defecto de 2 s) y `GET /health` del Router sigue 200. | TC-19 (y TC-07a para la caída) | Extensión (TC-07a es obligatoria) |
| **NFR-12** | Consistencia | Toda respuesta de ruta del Controller proviene de una única instantánea de topología. *(SPDR-02)* | 0 respuestas incoherentes con su `topology_version` y 0 actualizaciones perdidas en la prueba concurrente (8 hilos lectores, 1 hilo escritor, 100 cambios). | TC-20, RA-07 | Recomendada |

---

## 6. Restricciones y reglas de arquitectura

1. **Tecnología:** Python 3.11+, FastAPI, Uvicorn, NetworkX, pytest y un cliente HTTP (`httpx`).
2. **MVC en ambas apps:** Modelo = objetos de dominio; Vista = esquemas de entrada/salida (JSON); Controlador = manejadores HTTP que coordinan servicios. La lógica de negocio vive en servicios de dominio.
3. **DAO:** `TopologyDAO` (Controller) y `ForwardingLogDAO` (Router). Sin acceso a archivos o DAO desde controladores HTTP.
4. **Inyección de dependencias:** servicios dependen de **interfaces** DAO; el ensamblado ocurre en la raíz de composición (`main.py`).
5. **Separación SDN:** el Router **nunca** calcula rutas.
6. **Procesos separados:** cada app se inicia de forma independiente en puertos configurables, **cada una con un solo worker** de Uvicorn (A-14).
7. **Concurrencia:** el estado mutable del Controller solo cambia mediante el intercambio atómico de instantáneas inmutables (A-14); el DAO del Router serializa sus escrituras con un lock (A-16).
8. **Sesión 1:** sin código de implementación; solo especificaciones, diagramas y prompts.

---

## 7. Catálogo de errores

Formato único: `{"error": {"code": "...", "message": "...", "details": {}}}`

| HTTP | Código | Cuándo | App |
|---|---|---|---|
| 400 | `INVALID_PARAMETER` | Parámetro faltante, vacío, métrica no soportada o cuerpo mal formado | Ambas |
| 404 | `NODE_NOT_FOUND` | El nodo no existe en la topología | Controller (propagado por Router) |
| 404 | `ROUTE_NOT_FOUND` | Nodos válidos sin camino activo | Controller |
| 404 | `LINK_NOT_FOUND` | El enlace no existe en la topología | Controller |
| 409 | `LINK_ALREADY_FAILED` / `LINK_ALREADY_ACTIVE` | Transición de estado redundante | Controller |
| **502** | **`CONTROLLER_BAD_RESPONSE`** | El Controller respondió algo que no cumple el contrato (A-15) | Router |
| 503 | `TOPOLOGY_UNAVAILABLE` | Topología no cargada o inválida | Controller |
| 503 | `CONTROLLER_UNAVAILABLE` | Conexión rechazada, respuesta 5xx o `TOPOLOGY_UNAVAILABLE` del Controller | Router |
| 503 | `CONTROLLER_TIMEOUT` | El Controller excede el timeout | Router |
| 500 | `INTERNAL_ERROR` | Excepción no prevista (proceso sigue activo) | Ambas |

### 7.1 Códigos internos y avisos (no se devuelven como error HTTP)

| Código interno | Origen | Traducción HTTP |
|---|---|---|
| `INVALID_TOPOLOGY` | `TopologyService.validate` | La topología queda sin cargar, `/health` = `degraded` y los endpoints que la requieren responden 503 `TOPOLOGY_UNAVAILABLE`. |
| `INVALID_LINK_METRICS` | `LinkCostCalculator` | Se detecta al validar la topología; mismo tratamiento que `INVALID_TOPOLOGY`. |
| `PERSISTENCE_ERROR` | `ForwardingLogDAO` | No es error HTTP: el Router responde 200 con el `status` de la simulación, `log_persisted: false` y el aviso `{"code": "PERSISTENCE_ERROR", ...}` en `warnings`. |

### 7.2 Tabla de decisión: resultado de la simulación × persistencia *(SPDR-03)*

**Definiciones.** *Simulación completada* = HTTP 200 con `status` `DELIVERED` o `UNREACHABLE`. *Simulación auditable* = completada **y** `log_persisted: true`. Un cliente que necesita auditoría debe comprobar `log_persisted`, no solo el código HTTP.

| # | Respuesta del Controller a `GET /route` | Resultado de `ForwardingLogDAO.save()` | HTTP del Router | `status` | `route` / `trace` | `log_persisted` | `warnings` | ¿Se llama a `save()`? |
|---|---|---|---|---|---|---|---|---|
| D1 | 200 válida según contrato | Éxito | 200 | `DELIVERED` | ruta / un registro por salto | `true` | `[]` | Sí, 1 vez |
| D2 | 200 válida según contrato | Falla (`PersistenceError` o cualquier otra excepción del DAO, incluida escritura parcial) | 200 | `DELIVERED` | ruta / un registro por salto | `false` | `[PERSISTENCE_ERROR]` | Sí, 1 vez (sin reintento) |
| D3 | 404 `ROUTE_NOT_FOUND` | Éxito | 200 | `UNREACHABLE` | `null` / `[]`, `reason: "ROUTE_NOT_FOUND"` | `true` | `[]` | Sí, 1 vez |
| D4 | 404 `ROUTE_NOT_FOUND` | Falla (igual que D2) | 200 | `UNREACHABLE` | `null` / `[]`, `reason: "ROUTE_NOT_FOUND"` | `false` | `[PERSISTENCE_ERROR]` | Sí, 1 vez (sin reintento) |
| E1 | 404 `NODE_NOT_FOUND` | — | 404 `NODE_NOT_FOUND` (`details.node`) | — | — | — | — | No |
| E2 | 400 `INVALID_PARAMETER` | — | 400 `INVALID_PARAMETER` (`details.source: "controller"`) | — | — | — | — | No |
| E3 | 503 `TOPOLOGY_UNAVAILABLE` u otro 5xx | — | 503 `CONTROLLER_UNAVAILABLE` (`details.upstream_status`, `details.upstream_code`) | — | — | — | — | No |
| E4 | Conexión rechazada / error de red | — | 503 `CONTROLLER_UNAVAILABLE` | — | — | — | — | No |
| E5 | Sin respuesta dentro de `CONTROLLER_TIMEOUT_S` | — | 503 `CONTROLLER_TIMEOUT` | — | — | — | — | No |
| E6 | Respuesta fuera del contrato (A-15): no JSON, esquema inválido, ruta incoherente, 4xx con código no documentado, 3xx u otro código no previsto | — | 502 `CONTROLLER_BAD_RESPONSE` (`details.reason`) | — | — | — | — | No |
| E7 | (no se consulta) — la petición al Router es inválida | — | 400 `INVALID_PARAMETER` | — | — | — | — | No |
| E8 | Excepción no prevista en el Router **fuera** de `save()` | — | 500 `INTERNAL_ERROR` | — | — | — | — | No |

Reglas complementarias: (a) `ForwardingService` es el único que llama a `save()` y lo hace **después** de armar el resultado y **antes** de responder; (b) un fallo del DAO nunca convierte una simulación completada en un error HTTP; (c) el registro persistido no incluye `log_persisted` ni `warnings` (se calculan después de guardar).

---

## 8. Configuración

| Variable | Por defecto | App | Descripción |
|---|---|---|---|
| `CONTROLLER_PORT` | `8000` | Controller | Puerto HTTP |
| `TOPOLOGY_FILE` | `data/topology.json` | Controller | Ruta del archivo de topología |
| `ROUTER_PORT` | `8001` | Router | Puerto HTTP |
| `CONTROLLER_URL` | `http://localhost:8000` | Router | URL base del Controller |
| `CONTROLLER_TIMEOUT_S` | `2.0` | Router | Timeout de las llamadas al Controller |
| `FORWARDING_LOG_FILE` | `data/forwarding_log.jsonl` | Router | Archivo del log de reenvíos |

Ambas apps se inician con **un solo worker** (`uvicorn ... --workers 1`, valor por defecto), porque la topología y el lock del DAO viven en la memoria del proceso (A-14, A-16).

---

## 9. Registro de cambios posteriores a la congelación

El enunciado exige registrar todo cambio de diseño posterior a la congelación con su motivo y los artefactos afectados.

| ID | Fecha | Origen | Cambio | Motivo | Artefactos afectados |
|---|---|---|---|---|---|
| CH-01 | 2026-10-26 | SPDR-01 (mayor) | Se agrega `ForwardingService → ForwardingLogDAO.save()` con confirmación y manejo de fallo en **ambas** ramas de la Secuencia 2 (camino alternativo y `UNREACHABLE`), y en la Secuencia 1. | El diagrama contradecía FR-10 y A-10: una implementación literal podía no guardar resultados. | `03` (Secuencias 1, 2 y 4), `01` A-10, AC-08.4, `06` TC-24 |
| CH-02 | 2026-10-26 | SPDR-02 (mayor) | Modelo de concurrencia: instantáneas inmutables + intercambio atómico bajo lock; lectura única por consulta; un solo worker. Garantías G1–G5. Nuevo NFR-12. | No estaba definido cómo se sincronizan consultas y cambios de enlace, ni si ruta y versión provienen del mismo estado. | `01` A-13, A-14, AC-03.5, AC-06.6, NFR-12, §6, §8; `02` §2, §6, §7, §7.1; `03` Secuencia 5; `04` §1, §3; `06` TC-20 |
| CH-03 | 2026-10-26 | SPDR-03 (mayor) | Tabla de decisión resultado × persistencia (§7.2); semántica de escritura parcial (A-16); clasificación de respuestas inesperadas del Controller (A-15) con nuevo código 502 `CONTROLLER_BAD_RESPONSE`; `warnings` pasa a objetos `{code, message}`; definiciones de simulación completada vs auditable. | Quedaban sin especificar los casos `UNREACHABLE` sin persistencia, escritura parcial, distinción completada/auditable y respuestas inválidas del Controller. | `01` §1.5, UC-06–08, A-04, A-10, A-15, A-16, FR-07, FR-09, FR-10, §7; `02` §3, §3.1, §4; `03` Secuencias 3 y 4; `04` §2, §3; `06` TC-15, TC-24, TC-25, TC-26 |
| CH-04 | 2026-10-26 | SPDR-04 (menor) | Nombres de participantes normalizados como `Clase (App)` en todas las secuencias; la Secuencia 3 usa `RouteController (Controller)` en lugar de un participante genérico; propagación de errores explícita por `ErrorHandler`; la Secuencia 2 ya no abrevia el reenvío. | Alineación clase ↔ diagrama incompleta. | `03` completo |
| CH-05 | 2026-10-26 | SPDR-05 (menor) | NFR-10/TC-18: fixture fijo con generador y semilla, calentamiento, validación de corrección de cada respuesta, método de percentil, repeticiones y registro del entorno. | Prueba de rendimiento poco reproducible. | `01` NFR-10; `06` TC-18, §4 |
| CH-06 | 2026-10-26 | SPDR-06 (menor) | Lista de revisión arquitectónica RA-01…RA-10 y pruebas de sustitución de interfaces (TC-21, TC-22) y de delegación MVC (TC-23). | La verificación arquitectónica dependía solo de chequeos estáticos. | `01` NFR-01–03, NFR-07; `05` T-14, T-18; `06` §2, §5 |
| CH-07 | 2026-10-26 | SPDR-07 (menor) | La trazabilidad clasifica cada vínculo como **primaria**, **de soporte** o **inspección arquitectónica**; se corrige FR-01 ↔ TC-13 (pasa a inspección) y se agrega evidencia primaria (TC-17 ampliado, TC-21). | Vínculos requisito–prueba débiles. | `01` NFR-08, tablas AC; `05` §3; `06` §3 |
| CH-08 | 2026-10-26 | SPDR-08 (menor) | Cronograma de la Sesión 2 con entregables mínimos obligatorios, pruebas por nivel (obligatoria / recomendada / extensión), hitos con reglas de recorte y 12 min reservados para corregir defectos. | Cronograma optimista. | `05` §1, §6; `06` §2 |
| CH-09 | 2026-10-26 | Revisión interna | Se corrige el nombre del archivo `01-requirements (1).md` → `01-requirements.md`; se elimina el modelo `Node` (no existía en el diagrama de clases) de `02` §4–5; se definen los esquemas `LinkStateResponse`, `TopologyResponse` y `HealthResponse` que se usaban sin declararse; se crea esta sección §9, referenciada por `04` y `05` pero inexistente. | Inconsistencias detectadas al aplicar las correcciones. | `01`, `02`, `04`, `05` |
| CH-10 | 2026-10-29 | Revisión de entregables | Las especificaciones pasan de `Informatica3/Informatica3/` a `Sesion2/specs/` y `06-test-spec.md` se renombra `06-test-specification.md`, como pide el enunciado. Sin cambios de contenido en requisitos, diseño, API ni pruebas. | Nombres y ubicación exigidos en "Required repository deliverables". | `01`, `03`, `docs/01-scrum-requirements.md`, `docs/02-test-plan.md`, `docs/03-system-architecture.md`, `docs/architecture-review.md`, `prompts-session2.md`, `README.md` |
