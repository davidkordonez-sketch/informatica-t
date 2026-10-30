# Registro de prompts — Sesión 1 (especificaciones y arquitectura)

Durante la Sesión 1 **no se generó código de implementación**: la IA se usó solo para redactar borradores de especificación, revisar la arquitectura y detectar ambigüedades. Cada salida fue revisada por el equipo contra el enunciado y contra los demás documentos (01–06). Las correcciones resultantes se aplicaron el 2026-10-23 (commits `bb4d07b`, `fd8c938`, `077ab8e`) y, después de la revisión del profesor, en la versión 1.1 (ver `01-requirements.md` §9 y `prompts-session2.md` P2-01).

## Resumen: técnica obligatoria → prompt donde se usó

| Técnica exigida por el enunciado | Prompts |
|---|---|
| Encuadre contextual (*contextual framing*) | P1-01, P1-04, P1-05 |
| Prompt estructurado (*structured prompting*) | P1-01, P1-02, P1-04, P1-06 |
| Asignación de rol (*role prompting*) | P1-01, P1-04, P1-06 |
| Ejemplos (*few-shot*) | P1-03 |
| Refinamiento iterativo (*iterative refinement*) | P1-05, P1-06 |
| Pedir IDs de requisito y criterios de aceptación verificables | P1-01, P1-03 |
| Pedir a la IA al menos tres ambigüedades y resolverlas con criterio propio | P1-02 |

---

## P1-01 — Borrador de requisitos funcionales y no funcionales (especificación)

| Campo | Contenido |
|---|---|
| **Técnica** | Asignación de rol + encuadre contextual + prompt estructurado |
| **Objetivo** | Obtener un primer borrador de `01-requirements.md` con IDs, entradas, salidas, errores y criterios de aceptación verificables |
| **Prompt** | "Actúa como ingeniero de requisitos de software para un curso de Informática para Telecomunicaciones. Te adjunto el enunciado del taller (Controller y Router SDN en Python con FastAPI, NetworkX, MVC y DAO). Redacta la especificación de requisitos con esta estructura: 1) propósito, alcance y fuera de alcance; 2) actores y glosario; 3) para cada FR-01…FR-10: historia de usuario, entradas, salidas, errores y una tabla de criterios de aceptación con ID (AC-xx.y) en formato Dado/Cuando/Entonces; 4) tabla de NFR-01…NFR-09 con un criterio medible y el método de verificación de cada uno; 5) propón dos NFR adicionales medibles con su verificación. No escribas código de implementación. Usa exactamente los IDs del enunciado." |
| **Salida relevante** | Borrador de `01` con FR-01…FR-10, criterios AC por requisito, tabla de NFR y propuestas de NFR adicionales (el equipo eligió rendimiento y resiliencia: NFR-10 y NFR-11). |
| **Problema encontrado** | (1) El borrador no tenía **casos de uso**, que el enunciado pide explícitamente en `01-requirements.md`. (2) La IA marcó el documento como "versión 1.0 — línea base" sin que el equipo lo hubiera revisado ni congelado. |
| **Corrección** | Se agregó la sección **1.6 Casos de uso** (UC-01…UC-09), cada uno con flujo principal, flujo de error y requisitos asociados. La versión se bajó a 0.9 "en revisión" hasta que ambos integrantes confirmaron la consistencia (commit `bb4d07b`). |
| **Requisitos** | FR-01…FR-10, NFR-01…NFR-11 |

## P1-02 — Detección de ambigüedades del enunciado (especificación)

| Campo | Contenido |
|---|---|
| **Técnica** | Prompt estructurado con salida en tabla |
| **Objetivo** | Que la IA identificara **al menos tres** puntos ambiguos del enunciado; la decisión final la toma el equipo |
| **Prompt** | "Revisa el enunciado y el borrador de requisitos. Identifica al menos tres ambigüedades o puntos que el enunciado deja abiertos y que afectan el diseño o las pruebas. Devuélvelas en una tabla con columnas: ID (A-xx), pregunta, opciones posibles con su ventaja y desventaja, y requisitos afectados. No tomes la decisión: solo presenta las opciones." |
| **Salida relevante** | Doce ambigüedades (A-01…A-12), entre ellas: grafo dirigido o no dirigido, si "sin ruta" es error o resultado, qué hacer si el Controller no responde, cómo tratar un enlace con p = 1, qué hacer al fallar un enlace ya caído y si el estado de fallos se persiste. |
| **Problema encontrado** | (1) En A-09 la IA solo pedía validar que los campos del paquete estuvieran presentes; no decía qué hacer con una `metric` desconocida, que el Router tendría que reenviar al Controller sin validar. (2) La IA no detectó una ambigüedad importante: **cuándo** se carga la topología y qué pasa si el archivo falla al arrancar. |
| **Corrección** | Decisiones del equipo, con criterio propio: **A-01** grafo no dirigido, porque un enlace físico sirve en ambos sentidos con los mismos atributos; **A-03** distinguir `404 NODE_NOT_FOUND` (nodo inexistente) de `404 ROUTE_NOT_FOUND` (nodos válidos pero desconectados), como pide el enunciado, y en el Router reportar el destino inalcanzable como resultado `UNREACHABLE` (200); **A-05** un enlace con p = 1 es válido en el archivo pero se excluye del grafo, porque −ln(1−p) no está definido; **A-07** el estado de fallos vive en memoria. Se amplió **A-09** (el Router valida que `metric` ∈ {delay, bandwidth, loss}) y se agregó **A-13** (carga al arrancar; si falla, estado `degraded` y reintento en la siguiente petición). |
| **Requisitos** | FR-01, FR-03, FR-04, FR-06, FR-07, FR-08, FR-09 |

## P1-03 — Criterios de aceptación y contrato de API con ejemplos (especificación / API)

| Campo | Contenido |
|---|---|
| **Técnica** | *Few-shot*: se dieron dos ejemplos completos y se pidió seguir el mismo formato |
| **Objetivo** | Obtener criterios de aceptación y ejemplos JSON uniformes, verificables y con números concretos de la topología de referencia |
| **Prompt** | "Usa la topología de referencia: nodos A–F; enlaces A–B (d=10, b=10, p=0.01), B–D (10, 10, 0.01), A–C (5, 100, 0.05), C–D (20, 100, 0.05), D–E (5, 100, 0). Sigue exactamente el formato de estos ejemplos.<br>Ejemplo 1 (criterio): `AC-03.1 — Dada la topología de referencia, cuando se consulta A→D con delay, entonces la ruta es [A,B,D] con costo 20.`<br>Ejemplo 2 (error): `GET /route?src=A&dst=Z → 404 {"error": {"code": "NODE_NOT_FOUND", "message": "Node 'Z' does not exist", "details": {"node": "Z"}}}`<br>Escribe con este formato los criterios de FR-03, FR-04 y FR-06, y los ejemplos de petición/respuesta y de error de cada endpoint del contrato mínimo." |
| **Salida relevante** | Criterios con valores esperados (por ejemplo, A→D con `bandwidth` = `[A,C,D]`, costo 0,02; con `loss` = `[A,B,D]`, costo ≈ 0,0201) y ejemplos JSON para `GET /route`, `POST /links/fail`, `POST /links/restore`, `POST /packets` y `GET /health`. |
| **Problema encontrado** | (1) Los costos se verificaron a mano: delay A-B-D = 10+10 = 20 y A-C-D = 5+20 = 25; bandwidth A-B-D = 0,1+0,1 = 0,2 y A-C-D = 0,01+0,01 = 0,02; loss A-B-D = 2·(−ln 0,99) ≈ 0,0201 y A-C-D = 2·(−ln 0,95) ≈ 0,1026. Coincidían. (2) El contrato prometía `400 INVALID_PARAMETER` para parámetros inválidos, pero FastAPI responde **422** por defecto cuando falla la validación de un parámetro: la implementación literal no cumpliría el contrato. |
| **Corrección** | Se dejó escrito en `02` (responsabilidad de `ErrorHandler`) que el `RequestValidationError` (422) de FastAPI se convierte en `400 INVALID_PARAMETER` con el formato único de error (commits `fd8c938` y `077ab8e`). Los costos verificados se usaron en TC-01 y TC-02 de `06`. |
| **Requisitos** | FR-03, FR-04, FR-05, FR-06, FR-09, NFR-04 |

## P1-04 — Arquitectura estática: componentes, clases, MVC y DAO (arquitectura)

| Campo | Contenido |
|---|---|
| **Técnica** | Asignación de rol + encuadre contextual + prompt estructurado (salida en Mermaid) |
| **Objetivo** | Diagrama de componentes y de clases de ambas apps con MVC, DAO, interfaces e inyección de dependencias |
| **Prompt** | "Actúa como arquitecto de software. Con base en `01-requirements.md` (adjunto), genera en Mermaid: 1) un diagrama de componentes con los procesos Controller y Router, la conexión REST, las capas MVC, los servicios de dominio, los DAO y el límite de persistencia; 2) un diagrama de clases por aplicación con atributos, métodos públicos, asociaciones y las interfaces `TopologyDAO` y `ForwardingLogDAO`. Reglas: los controladores HTTP no contienen Dijkstra ni reenvío; los servicios dependen de interfaces DAO inyectadas por constructor; el Router nunca calcula rutas. Agrega una tabla de responsabilidades por clase y el mapeo MVC de cada app." |
| **Salida relevante** | Diagrama de componentes, diagramas de clases del Controller y del Router, tabla de responsabilidades y mapeo MVC (base de `02-static-architecture.md`). |
| **Problema encontrado** | (1) El diagrama listaba un modelo `Node` que **no existía** en el diagrama de clases ni en ningún método. (2) En el diagrama de componentes, `GET /topology` llegaba al `LinkController` y faltaban las flechas de `GET /health`. (3) `ForwardingResult` no tenía `src`, `dst` ni `metric`; en un resultado `UNREACHABLE` (`route = null`) el log no podría indicar a qué destino iba el paquete. (4) No aparecía ninguna clase encargada de traducir errores de dominio a HTTP. |
| **Corrección** | Se eliminó `Node` del diagrama (y de las tablas de §4–5 en la v1.1, CH-09); `GET /topology` se dirigió a `TopologyController` y se agregaron las flechas de `/health`; se agregaron `src`, `dst` y `metric` a `ForwardingResult`; se agregó `ErrorHandler` y la sección **3.1 Manejo de errores** con la jerarquía de excepciones (commit `fd8c938`). |
| **Requisitos** | FR-05, FR-08, FR-10, NFR-01, NFR-02, NFR-03, NFR-07, NFR-09 |

## P1-05 — Arquitectura dinámica: tres diagramas de secuencia (arquitectura)

| Campo | Contenido |
|---|---|
| **Técnica** | Encuadre contextual (se adjuntaron `02` y `04`) + refinamiento iterativo |
| **Objetivo** | Las tres secuencias del enunciado, usando solo clases de `02` y mensajes de `04` |
| **Prompt** | "Con las clases de `02-static-architecture.md` y los endpoints de `04-api-contract.md` (adjuntos), dibuja en Mermaid tres diagramas de secuencia: 1) reenvío exitoso: paquete → API del Router → ForwardingService → API del Controller → RoutingService → TopologyDAO → ruta → ForwardingLogDAO → respuesta; 2) fallo de un enlace, nueva consulta con camino alternativo o inalcanzable, y restablecimiento; 3) Controller caído o con timeout → manejo del error en el Router → respuesta estable al cliente. Cada participante debe ser una clase de `02`." — Segunda iteración: "Revisa que cada participante exista en `02` con el mismo nombre y que cada mensaje HTTP coincida con `04`; corrige los que no." |
| **Salida relevante** | Secuencias 1, 2 y 3 de `03-dynamic-architecture.md` y una tabla de coherencia entre diagramas, clases y API. |
| **Problema encontrado** | Aunque el prompt lo exigía, la Secuencia 3 usaba participantes genéricos que no eran clases: "Manejador de errores (Router)" y "Controller (caído o lento)". Además, la tabla de coherencia del final afirmaba que todos los participantes existían en `02`, lo cual era falso: la IA "verificó" su propia salida sin hacerlo. |
| **Corrección** | Se agregó `ErrorHandler` a `02` y se usó en la secuencia. En la v1.1 (CH-04) todos los participantes quedaron como `Clase (App)` y el Controller caído se representa con `RouteController (Controller)`, cuyo proceso no responde. Lección para el equipo: la tabla de coherencia se revisa a mano, participante por participante. |
| **Requisitos** | FR-06, FR-07, FR-08, FR-09, FR-10, NFR-06 |

## P1-06 — Revisión cruzada y congelación de la línea base (revisión de arquitectura)

| Campo | Contenido |
|---|---|
| **Técnica** | Asignación de rol (revisor crítico) + prompt estructurado + refinamiento iterativo |
| **Objetivo** | Encontrar inconsistencias entre 01–06 antes de congelar |
| **Prompt** | "Actúa como un revisor exigente que debe encontrar errores, no confirmar que todo está bien. Compara los seis documentos adjuntos y reporta en una tabla (documento, sección, problema, corrección propuesta): requisitos sin prueba, pruebas sin requisito, clases de las secuencias que no estén en el diagrama de clases, endpoints o códigos de error que no coincidan con `04`, y nombres de archivo distintos a los que pide el enunciado." |
| **Salida relevante** | Lista de inconsistencias usada para la revisión del 2026-10-23 y matriz de trazabilidad de `05` §3. |
| **Problema encontrado** | (1) El archivo se llamaba `01-requirements (1).md` (copia descargada) y otros documentos lo citaban como `01-requirements.md`. (2) `04` y `05` citaban una sección 9 "Registro de cambios" de `01` que se había eliminado durante las ediciones (commit `6ccf2b4`). (3) Los esquemas `LinkStateResponse`, `TopologyResponse` y `HealthResponse` se usaban en `04` sin estar declarados en `02`. |
| **Corrección** | Se renombró el archivo a `01-requirements.md`, se reescribió la sección §9 como registro formal de cambios (CH-01…CH-09) y se declararon los tres esquemas en `02` (todo registrado en CH-09). Ambos integrantes revisaron 01–06 antes de la congelación. |
| **Requisitos** | NFR-04, NFR-08 |
