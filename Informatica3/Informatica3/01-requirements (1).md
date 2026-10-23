# 01 — Especificación de Requisitos: Controlador y Enrutador SDN

| Campo | Valor |
|---|---|
| Curso | Informática para Telecomunicaciones |
| Proyecto | Simulación SDN a nivel de aplicación (Controller + Router) |
| Equipo | Estudiante A (Controller) · Estudiante B (Router) |
| Versión | 1.0 (línea base de la Sesión 1) |
| Fecha | 2026-10-20 |
| Estado | Borrador para congelar al cierre de la Sesión 1 |

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
Protocolos reales (OpenFlow, BGP/OSPF), tráfico de red real, autenticación/autorización, persistencia del estado de fallos entre reinicios, alta disponibilidad y balanceo de carga.

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
| Versión de topología | Entero que parte en 1 y aumenta con cada fallo/restablecimiento exitoso. |
| DAO | *Data Access Object*: abstracción que encapsula la lectura/escritura de datos. |
| Trace | Registro salto a salto de la simulación de reenvío. |

---

## 2. Supuestos y decisiones sobre ambigüedades

El enunciado deja puntos abiertos. Cada decisión queda **congelada** con esta especificación; cualquier cambio posterior se registra en la sección 9.

| ID | Ambigüedad | Decisión | Afecta |
|---|---|---|---|
| A-01 | ¿Grafo dirigido o no dirigido? | **No dirigido** (`networkx.Graph`). Un enlace A–B sirve en ambos sentidos con los mismos atributos. El enlace se identifica por el par de nodos sin importar el orden. | FR-02, FR-06 |
| A-02 | ¿Se combinan métricas? | **No.** Cada consulta usa **una** métrica: `delay`, `bandwidth` o `loss`. Si falta `metric`, se usa `delay` por defecto. | FR-03, FR-04, FR-05 |
| A-03 | ¿"Sin ruta" es error o resultado válido? | **Controller:** `404 ROUTE_NOT_FOUND` (nodos válidos pero desconectados), distinto de `404 NODE_NOT_FOUND` (nodo inexistente). **Router:** un destino inalcanzable se reporta como resultado de simulación con estado `UNREACHABLE` (HTTP 200) y se registra; un nodo inexistente propaga `404 NODE_NOT_FOUND`. | FR-05, FR-08, FR-09 |
| A-04 | ¿Qué pasa si el Controller no responde? | El Router devuelve `503` (`CONTROLLER_UNAVAILABLE` o `CONTROLLER_TIMEOUT`) sin reintentos y sigue vivo. Timeout configurable, por defecto 2 s. | FR-07, FR-09, NFR-11 |
| A-05 | ¿Un enlace con p = 1? | Es **válido en el archivo** pero **inutilizable**: se excluye del grafo ponderado para **todas** las métricas. | FR-04 |
| A-06 | ¿Fallar un enlace ya caído, o restaurar uno activo? | `409 Conflict` (`LINK_ALREADY_FAILED` / `LINK_ALREADY_ACTIVE`). Enlace inexistente: `404 LINK_NOT_FOUND`. | FR-06 |
| A-07 | ¿Se persiste el estado de fallos? | **No.** Vive en memoria; al reiniciar el Controller todo vuelve al estado del JSON. | FR-06 |
| A-08 | ¿Origen = destino? | Ruta válida `[src]` con costo 0. | FR-03 |
| A-09 | ¿Quién valida que los nodos existan? | **Solo el Controller.** El Router solo valida el formato de entrada (campos presentes y no vacíos). | FR-07, FR-09 |
| A-10 | ¿Qué se registra en el log de reenvíos? | Todo `ForwardingResult` generado (`DELIVERED` o `UNREACHABLE`) como una línea JSON (JSON Lines). Las solicitudes rechazadas por error (400/404/503) no generan resultado y no se registran. | FR-10 |
| A-11 | ¿Quién valida la topología? | El **DAO solo lee y parsea**; la **validación semántica** (nodos referenciados, rangos) la hace `TopologyService` (lógica de dominio, no de persistencia). | FR-01, FR-02 |
| A-12 | ¿Qué hace el Router con un fallo del Controller a mitad del reenvío? | Fuera de alcance: la ruta se consulta **una vez por paquete** y se simula sobre esa instantánea (`topology_version`). | FR-08 |

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

Prioridad **Alta (Must)** para todos. Formato de criterios: *Dado / Cuando / Entonces*. Los casos `TC-xx` están definidos en `06-test-spec.md`.

### FR-01 — Cargar la topología desde JSON mediante un DAO
- **Historia de usuario:** Como Controller SDN, quiero cargar la topología desde un archivo JSON a través de `TopologyDAO` para separar el almacenamiento de la lógica del sistema.
- **Actor:** Controller. **Precondición:** la ruta del archivo es configurable (NFR-05).
- **Entradas:** archivo JSON con nodos, enlaces y atributos físicos.
- **Salidas:** objeto `Topology` en memoria (versión 1), entregado por el DAO y validado por `TopologyService`.
- **Errores:** archivo inexistente, ilegible o JSON corrupto → error controlado `TOPOLOGY_UNAVAILABLE`; el proceso **no se detiene** (estado `degraded`, los endpoints que requieren topología responden 503).

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-01.1 | Dado un JSON válido, cuando el Controller arranca, entonces `GET /health` indica `topology_loaded: true` y `GET /topology` lista todos los nodos y enlaces. | TC-16, TC-17 |
| AC-01.2 | Dado un archivo inexistente, cuando el Controller arranca, entonces el proceso sigue activo, `/health` indica `degraded` y `GET /route` responde 503. | TC-17 |
| AC-01.3 | Dado un JSON corrupto, entonces ocurre lo mismo que en AC-01.2. | TC-17 |
| AC-01.4 | Ni los controladores HTTP ni los servicios contienen acceso directo a archivos; solo usan `TopologyDAO`. | TC-13 |

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
- **Entradas:** `src`, `dst`, métrica y grafo ponderado activo. **Salidas:** lista ordenada de nodos, costo total acumulado, costos por salto y `topology_version`.
- **Errores:** `NODE_NOT_FOUND` (nodo inexistente) y `ROUTE_NOT_FOUND` (sin camino viable), siempre distinguibles.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-03.1 | Dada la topología de referencia (`06-test-spec.md`), cuando se consulta A→D con `delay`, entonces la ruta es `[A,B,D]` con costo 20. | TC-01 |
| AC-03.2 | Dado `src == dst`, entonces la ruta es `[src]` con costo 0. | TC-01 |
| AC-03.3 | Dado un destino aislado (F), entonces el resultado es `ROUTE_NOT_FOUND`. | TC-07, TC-11 |
| AC-03.4 | La lógica de Dijkstra reside únicamente en `RoutingService`, no en controladores HTTP. | TC-12 |

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
- **Entradas:** `GET /route?src=&dst=&metric=`. **Salidas:** JSON con `path`, `total_cost`, `hop_costs`, `metric`, `topology_version`.
- **Errores:** 400 parámetros faltantes o métrica no soportada; 404 `NODE_NOT_FOUND` / `ROUTE_NOT_FOUND`; 503 topología no disponible.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-05.1 | Las respuestas coinciden con los esquemas y códigos de `04-api-contract.md`. | TC-11, TC-16 |
| AC-05.2 | Faltan `src` o `dst`, o `metric` inválida → 400 `INVALID_PARAMETER`. | TC-11 |
| AC-05.3 | Nodo inexistente → 404 `NODE_NOT_FOUND`; nodos desconectados → 404 `ROUTE_NOT_FOUND`. | TC-11 |
| AC-05.4 | `GET /topology` y `GET /health` existen y responden según el contrato. | TC-11 |
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

### FR-07 — El Router solicita rutas al Controller por HTTP
- **Historia de usuario:** Como Router SDN, quiero pedir la ruta al Controller por HTTP para mantener la separación entre control y reenvío.
- **Entradas:** `src`, `dst`, `metric` del paquete. **Salidas:** petición `GET /route` y `RouteInfo` recibida.
- **Errores:** conexión rechazada, timeout o 503 del Controller → error controlado y documentado; el Router no se detiene.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-07.1 | El Router **no implementa** Dijkstra ni importa `networkx`. | TC-14 |
| AC-07.2 | Toda decisión de ruta sale del componente cliente HTTP (`HttpControllerClient`) hacia `GET /route`. | TC-05 |
| AC-07.3 | URL y timeout del Controller son configurables. | TC-19 |

### FR-08 — Simular el reenvío de paquetes
- **Historia de usuario:** Como Router SDN, quiero simular el reenvío salto a salto a lo largo de la ruta del Controller para verificar el plano de datos.
- **Entradas:** `POST /packets` con `{packet_id, src, dst, metric?, payload?}` (la ruta la obtiene el Router, **no** la envía el cliente). **Salidas:** `ForwardingResult` con estado (`DELIVERED`/`UNREACHABLE`), ruta usada y `trace`.
- **Errores:** ruta vacía/inalcanzable → estado `UNREACHABLE` con motivo explícito; nodo inexistente → 404 propagado.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-08.1 | El `trace` contiene un registro por salto, coherente con la lista de nodos del Controller (`[A,B,D]` → saltos A→B y B→D). | TC-06 |
| AC-08.2 | Destino aislado → HTTP 200, estado `UNREACHABLE`, `trace` vacío y `reason: "ROUTE_NOT_FOUND"`. | TC-07 |
| AC-08.3 | El procesamiento lo hace `ForwardingService`, no el controlador HTTP. | TC-12 |

### FR-09 — Gestionar nodos inválidos, destinos inalcanzables y fallos de comunicación
- **Historia de usuario:** Como sistema SDN integrado, quiero manejar errores esperados de forma controlada para que ambas aplicaciones sigan funcionando.
- **Entradas:** peticiones con datos inválidos, nodos ausentes, destinos desconectados, caída del Controller. **Salidas:** respuestas `{"error": {"code","message","details"}}` con HTTP 400/404/409/503 (ver sección 7).
- **Errores:** este requisito *es* la política de errores; las excepciones no previstas devuelven 500 `INTERNAL_ERROR` con el mismo formato.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-09.1 | Ninguna condición de error esperada cierra el proceso; `GET /health` sigue respondiendo. | TC-07, TC-17, TC-19 |
| AC-09.2 | La API distingue entrada inválida (400), nodo inexistente (404 `NODE_NOT_FOUND`) y ausencia de ruta (404 `ROUTE_NOT_FOUND` / `UNREACHABLE` en el Router). | TC-11 |
| AC-09.3 | Todos los errores usan el formato único de error. | TC-11 |

### FR-10 — Registrar resultados de reenvío mediante un DAO
- **Historia de usuario:** Como Router SDN, quiero persistir cada resultado con `ForwardingLogDAO` para tener un historial comprobable sin mezclar almacenamiento con lógica de dominio.
- **Entradas:** `ForwardingResult`. **Salidas:** línea JSON agregada al log.
- **Errores:** sin permisos de escritura o disco lleno → `PERSISTENCE_ERROR` capturado: la simulación termina bien, `log_persisted: false` y se agrega un aviso en `warnings`.

| ID | Criterio de aceptación | Prueba |
|---|---|---|
| AC-10.1 | Toda operación de almacenamiento ocurre dentro de `ForwardingLogDAO`. | TC-09, TC-13 |
| AC-10.2 | `ForwardingService` no contiene `open()`, `write()` ni acceso directo a archivos. | TC-13 |
| AC-10.3 | `ForwardingLogDAO` puede reemplazarse por un mock en pruebas. | TC-09 |
| AC-10.4 | Si el DAO falla, la respuesta es 200 con `log_persisted: false` y un aviso. | TC-15 |

---

## 5. Requisitos no funcionales

| ID | Categoría | Requisito | Criterio medible | Verificación |
|---|---|---|---|---|
| NFR-01 | Mantenibilidad | Ambas apps implementan MVC con responsabilidades por capa documentadas. | 100 % de módulos en `controllers/`, `schemas/`, `models/`, `services/`, `dao/`. | Revisión de código + `02-static-architecture.md` |
| NFR-02 | Mantenibilidad | Carga, lectura y persistencia usan abstracciones DAO; los servicios no acceden a almacenamiento directo. | 0 usos de `open()`, `json.load`, `pathlib` en `services/`. | TC-13 (análisis estático/AST) |
| NFR-03 | Mantenibilidad | Dijkstra y el reenvío residen fuera de los manejadores HTTP. | 0 imports de `networkx`/`heapq` en `controllers/`. | TC-12 |
| NFR-04 | Interoperabilidad | Las interfaces HTTP/JSON cumplen el contrato aprobado. | 100 % de endpoints y esquemas coinciden con `04-api-contract.md`. | TC-11, TC-16 |
| NFR-05 | Configurabilidad | Puertos, ruta de topología, URL/timeout del Controller y ruta del log son configurables sin tocar código. | Cambiar variable de entorno → cambia el comportamiento. | TC-16, TC-19 |
| NFR-06 | Robustez | Los fallos previstos producen errores controlados y documentados; las apps siguen activas. | 0 caídas de proceso en TC-07, TC-15, TC-17, TC-19. | Pruebas automatizadas |
| NFR-07 | Calidad de diseño | Implementación orientada a objetos, modular, con dependencias inyectables. | Servicios reciben dependencias por constructor; sin globales ni singletons ocultos. | Revisión de código + TC-08, TC-09 |
| NFR-08 | Trazabilidad | Cada requisito se vincula a tarea, componente y prueba. | 100 % de FR/NFR en la matriz de trazabilidad. | `05-implementation-plan.md` |
| NFR-09 | Testabilidad | Las dependencias DAO son reemplazables por mocks/fakes. | RoutingService y ForwardingService probados sin servidor HTTP ni archivos. | TC-08, TC-09 |
| **NFR-10** | Rendimiento | Una consulta de ruta responde rápido en una topología sintética grande. | En 200 nodos y 1000 enlaces, p95 de 100 consultas `GET /route` ≤ **200 ms** (en la máquina de desarrollo). | TC-18 (`time.perf_counter`) |
| **NFR-11** | Disponibilidad / Resiliencia | Si el Controller no responde, el Router falla rápido y sigue operativo. | El Router responde 503 en ≤ **timeout + 1 s** (3 s con el valor por defecto de 2 s) y `GET /health` del Router sigue 200. | TC-19 |

---

## 6. Restricciones y reglas de arquitectura

1. **Tecnología:** Python 3.11+, FastAPI, Uvicorn, NetworkX, pytest y un cliente HTTP (`httpx`).
2. **MVC en ambas apps:** Modelo = objetos de dominio; Vista = esquemas de entrada/salida (JSON); Controlador = manejadores HTTP que coordinan servicios. La lógica de negocio vive en servicios de dominio.
3. **DAO:** `TopologyDAO` (Controller) y `ForwardingLogDAO` (Router). Sin acceso a archivos o DAO desde controladores HTTP.
4. **Inyección de dependencias:** servicios dependen de **interfaces** DAO; el ensamblado ocurre en la raíz de composición (`main.py`).
5. **Separación SDN:** el Router **nunca** calcula rutas.
6. **Procesos separados:** cada app se inicia de forma independiente en puertos configurables.
7. **Sesión 1:** sin código de implementación; solo especificaciones, diagramas y prompts.

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
| 503 | `TOPOLOGY_UNAVAILABLE` | Topología no cargada o inválida | Controller |
| 503 | `CONTROLLER_UNAVAILABLE` | Conexión rechazada o respuesta 5xx del Controller | Router |
| 503 | `CONTROLLER_TIMEOUT` | El Controller excede el timeout | Router |
| 500 | `INTERNAL_ERROR` | Excepción no prevista (proceso sigue activo) | Ambas |

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

---

## 9. Registro de cambios
| Versión | Fecha | Cambio | Motivo | Artefactos afectados |
|---|---|---|---|---|
| 1.0 | 2026-10-20 | Línea base de la Sesión 1 | Congelación de especificaciones | 01–06 |
