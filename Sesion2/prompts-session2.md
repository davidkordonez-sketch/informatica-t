# Registro de prompts — Sesión 2 (implementación, integración y verificación)

El enunciado pide, entre las dos sesiones, **al menos 6 prompts sustanciales** con técnica, objetivo, texto del prompt, salida relevante, problema encontrado, corrección y requisitos relacionados, e incluir prompts de especificación, revisión de arquitectura, generación de código y pruebas.

> Cada salida de la IA se verificó contra la especificación congelada (`specs/01`…`06`, v1.1) antes de aceptarla. Ejemplos de sugerencias incorrectas de la IA y su corrección: P2-03 (prueba mal escrita), P2-06 (defecto real que solo aparecía en Windows) y P2-07 (entregables que el README daba por hechos y no existían).

---

## P2-01 — Corrección de la especificación tras la revisión SPDR (revisión de arquitectura)

| Campo | Contenido |
|---|---|
| **Técnica** | Encuadre contextual (se adjuntaron los 6 documentos, el enunciado y el informe del revisor) + refinamiento iterativo |
| **Objetivo** | Corregir los 8 hallazgos SPDR-01…SPDR-08 de la Sesión 1 antes de implementar |
| **Prompt** | "mira esto es nuestra primera parte del trabajo… ya presentamos y nos mandó estas correcciones, quiero que me ayudes a modificar los documentos bien hecho para que quede bien completo, realízalo correctamente, sin saltarte nada, también me indicas dónde y cómo corregiste" |
| **Salida relevante** | Versión 1.1 de 01–06: modelo de concurrencia con instantáneas inmutables (A-14), tabla de decisión resultado × persistencia (01 §7.2), código 502 `CONTROLLER_BAD_RESPONSE`, pruebas TC-20…TC-26, lista RA, cronograma con niveles de prueba e informe `CORRECCIONES-SPDR.md`. |
| **Problema encontrado** | En la primera versión de las tablas que acompañan a los diagramas de secuencia, los números de mensaje no coincidían con la numeración automática de Mermaid (las notas no se numeran). |
| **Corrección** | Se recontaron los mensajes renderizando los diagramas con Mermaid CLI y se corrigieron las tablas de las Secuencias 1 y 5. |
| **Requisitos** | FR-03, FR-06, FR-08, FR-09, FR-10, NFR-08, NFR-10, NFR-12 |

## P2-02 — Generación del código de ambas aplicaciones (generación de código)

| Campo | Contenido |
|---|---|
| **Técnica** | Encuadre contextual con especificación congelada (el prompt remite a 01–06 v1.1) + restricciones explícitas de arquitectura (MVC, DAO, DI, Router sin Dijkstra) |
| **Objetivo** | Implementar el Controller y el Router siguiendo exactamente las clases de `02` y el contrato de `04` |
| **Prompt** | "comencemos a hacer esto… iniciemos con la sección 2, ayúdame a hacer los códigos" (con los documentos 01–06 v1.1 ya en el contexto de la conversación) |
| **Salida relevante** | `controller/` y `router/` con la estructura de `02` §8; `TopologyService` con `_write_lock` e instantáneas `frozen`; `ForwardingService._persist` en ambas ramas; `HttpControllerClient` con la tabla de 04 §3. |
| **Problema encontrado** | Verificación manual contra `02`: los nombres y responsabilidades coinciden, pero se agregaron parámetros que la especificación no tenía (`transport`, `opener`, `clock`) y `JsonTopologyDAO` puede lanzar `InvalidTopologyError` por errores de estructura. |
| **Corrección** | Se aceptaron (no cambian el contrato) y se documentaron como decisiones de implementación en el README §6, en lugar de cambiar los requisitos. |
| **Requisitos** | FR-01…FR-10, NFR-01…NFR-03, NFR-07 |

## P2-03 — Pruebas automáticas TC-01…TC-26 (pruebas)

| Campo | Contenido |
|---|---|
| **Técnica** | Prompt estructurado: cada prueba se pide con su ID, escenario y resultado esperado tomados literalmente de `06` §2 |
| **Objetivo** | Implementar las 26 pruebas con los marcadores de nivel (obligatoria / recomendada / extensión) |
| **Prompt** | Parte del mismo pedido de P2-02; las expectativas se copiaron de la tabla de `06-test-specification.md` |
| **Salida relevante** | 73 pruebas (con parametrizaciones) en `tests/`; `pytest.ini` con marcadores; fakes compartidos en `tests/fakes.py`. |
| **Problema encontrado** | **Error de la IA en una prueba:** TC-26 (escritura parcial) llamaba dos veces al DAO roto sobre el mismo archivo y esperaba 1 línea corrupta; el resultado real era 2. El DAO estaba bien; la prueba estaba mal. |
| **Corrección** | La segunda llamada se hace sobre otro archivo, de modo que el escenario coincide con el descrito en `06` (un fragmento + una escritura buena). Después: 73/73 en verde. |
| **Requisitos** | FR-10, NFR-06 (TC-26) |

## P2-04 — Verificación de que las pruebas detectan defectos (pruebas / revisión)

| Campo | Contenido |
|---|---|
| **Técnica** | Pregunta de verificación crítica: "¿las pruebas fallarían si el código violara la arquitectura?" |
| **Objetivo** | Evitar pruebas que siempre pasan |
| **Prompt** | "¿Cómo comprobamos que TC-12 y TC-24 realmente detectan una violación de la arquitectura y no pasan siempre? Indícanos qué defecto inyectar en cada caso." Procedimiento: agregar temporalmente `import networkx` en `controller/controllers/route_controller.py` y agregar `return result` al final del bloque `except RouteNotFoundError:` de `router/services/forwarding_service.py` (el `UNREACHABLE` se devuelve sin pasar por `save()`); ejecutar `pytest -k "tc12 or tc24"`; revertir con `git checkout -- controller router`. |
| **Salida relevante** | Con los defectos inyectados, TC-12 y TC-24 fallaron; tras revertir, `pytest -v` volvió a 76/76 en verde. |
| **Problema encontrado** | Ninguno en el código. La verificación la hizo primero el asistente por su cuenta; el procedimiento queda escrito en esta entrada para que cualquiera pueda repetirlo y comprobarlo. |
| **Corrección** | — (evidencia anotada en el README §4) |
| **Requisitos** | NFR-03, FR-10 |

## P2-05 — Guion de demo en vivo con verificación automática (integración)

| Campo | Contenido |
|---|---|
| **Técnica** | Prompt estructurado basado en la sección "Mandatory live behavior" del enunciado + refinamiento iterativo |
| **Objetivo** | Tener un guion reproducible para la demo y la evidencia `demo-evidence/demo-log.txt` |
| **Prompt** | "genera y redacta las correcciones necesarias para el prompts-session1 y para el README…" (el README describía `scripts/demo.py`, que no existía). Se pidió que el guion siguiera los pasos obligatorios del enunciado y verificara cada resultado. |
| **Salida relevante** | `scripts/demo.py` (solo biblioteca estándar): paquete A→D `[A,B,D]` (v1) → falla B–D → `[A,C,D]` (v2) → falla C–D → `UNREACHABLE` (v3) → restablece → `[A,B,D]` (v5); métrica `bandwidth`; 404 y 409; TC-08/TC-09 con DAO falso; Controller detenido → 503 y `/health` del Router en 200. Cada paso imprime `[OK]` o `[FALLÓ]`. |
| **Problema encontrado** | **Error de la IA:** (1) en una sesión anterior, la IA había escrito en el README y en `docs/` que existían `scripts/demo.py` y `demo-evidence/demo-log.txt`, pero nunca se subieron al repositorio. (2) En la primera versión del guion, si `pytest` no estaba disponible, el paso 7 marcaba `[FALLÓ]` sin decir por qué. (3) Si una ejecución anterior dejaba enlaces caídos, la siguiente demo empezaba en un estado distinto y las rutas esperadas no coincidían. |
| **Corrección** | Se agregó el guion al repositorio; ahora muestra la causa cuando falla el paso 7 y restablece al inicio los enlaces que encuentre caídos. La evidencia de la demo en vivo son las capturas `demo-evidence/01`…`09`, tomadas por el equipo desde `/docs` con los dos procesos reales; el README ya no cita archivos que no existen. |
| **Requisitos** | FR-05…FR-08, FR-09, NFR-05, NFR-06, NFR-09, NFR-11 |

## P2-06 — Pruebas en el equipo del grupo (Windows) y corrección de un defecto (pruebas)

| Campo | Contenido |
|---|---|
| **Técnica** | Refinamiento iterativo: se compartió la salida real de `pytest` con el asistente para diagnosticar el fallo |
| **Objetivo** | Ejecutar las pruebas en el equipo del grupo antes de la entrega |
| **Prompt** | "mira lo que salió" (con la captura de `pytest`: `2 failed, 71 passed`; fallaban TC-07a y TC-19 con `'CONTROLLER_TIMEOUT' == 'CONTROLLER_UNAVAILABLE'`) |
| **Salida relevante** | Diagnóstico: en Windows, conectarse a un puerto cerrado no se rechaza al instante; el sistema reintenta y `httpx` lanza `ConnectTimeout` antes del rechazo. El código lo trataba como "Controller lento" (`CONTROLLER_TIMEOUT`). |
| **Problema encontrado** | **Defecto real del código generado**, que no aparecía al probar en Linux: no distinguía "no me pude conectar" de "conecté pero no respondió". |
| **Corrección** | `HttpControllerClient` captura `httpx.ConnectTimeout` → `CONTROLLER_UNAVAILABLE`; solo `ReadTimeout` → `CONTROLLER_TIMEOUT`. Se agregaron 3 pruebas en TC-25 (conexión rechazada, timeout de conexión, timeout de lectura). Resultado: 76/76. |
| **Requisitos** | FR-07, FR-09, NFR-11 |

## P2-07 — Auditoría del repositorio contra el enunciado (revisión)

| Campo | Contenido |
|---|---|
| **Técnica** | Encuadre contextual (se adjuntó el enunciado en PDF y el enlace del repositorio) + pedido de verificación crítica |
| **Objetivo** | Comprobar, antes de la entrega, que el repositorio cumple todos los requisitos del taller |
| **Prompt** | "soy estudiante de ingeniería electrónica y telecomunicaciones de sexto semestre, tengo que realizar un taller para la materia informática para telecomunicaciones, el taller está en inglés, analízalo y verifica si los documentos subidos a un repositorio público de github cumplen con todos los requerimientos del taller" |
| **Salida relevante** | Tabla de cumplimiento: FR-01…FR-10, NFR-01…NFR-12, los seis documentos, MVC/DAO y TC-01…TC-09 cumplen. Faltantes: `prompts-session1.md`; `scripts/demo.py` y archivos de evidencia citados en el README pero inexistentes; `tests/controller/test_ui_console.py` (TC-27) citado pero inexistente; notas internas de la IA visibles en `prompts-session2.md` y `docs/architecture-review.md`; todos los commits desde un mismo correo; `.gitignore` mal ubicado. |
| **Problema encontrado** | La propia IA había generado en una sesión anterior el README que afirmaba evidencias inexistentes: el contenido generado sonaba completo y verificado, pero no lo estaba. El equipo no lo había comprobado archivo por archivo. |
| **Corrección** | Se creó `prompts-session1.md`; se agregó `scripts/demo.py`; la sección 8 del README ahora cita las capturas reales de la demo; se eliminaron las notas internas de la IA; se movieron las especificaciones a `specs/` (CH-10); se corrigió `.gitignore`. Además se detectó que el TC-27 citado en el README no existía (se había subido una copia del controlador en `tests/`) y se escribió la prueba. |
| **Requisitos** | NFR-08 y entregables del enunciado (§5 "Required repository deliverables") |
