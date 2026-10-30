# Registro de prompts — Sesión 2 (implementación, integración y verificación)

El enunciado pide, entre las dos sesiones, **al menos 6 prompts sustanciales** con técnica, objetivo, texto del prompt, salida relevante, problema encontrado, corrección y requisitos relacionados, e incluir prompts de especificación, revisión de arquitectura, generación de código y pruebas.

> **Importante para la defensa.** Las entradas P2-01 a P2-06 corresponden a lo que realmente pasó al trabajar con el asistente de IA. **Revisen cada una, corrijan lo que no coincida con lo que ustedes hicieron y agreguen al menos una entrada propia** con un prompt que hayan escrito y verificado personalmente (por ejemplo, P2-07). En la defensa les pueden pedir "un ejemplo de una sugerencia incorrecta de la IA y cómo la corrigieron": P2-03 y P2-06 sirven para eso.

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
| **Prompt** | *No fue un mensaje del equipo:* el asistente hizo esta verificación por su cuenta. Para contarlo como prompt propio, ejecútenlo ustedes, por ejemplo: "Inyecta temporalmente un `import networkx` en un controlador y elimina el `save()` de la rama UNREACHABLE; ejecuta TC-12 y TC-24 y luego revierte." |
| **Salida relevante** | TC-12 y TC-24 (a y b) fallaron como se esperaba; tras revertir, 73/73 en verde. |
| **Problema encontrado** | Ninguno en el código. Se confirmó que las pruebas de arquitectura no son decorativas. |
| **Corrección** | — (evidencia anotada en el README §4) |
| **Requisitos** | NFR-03, FR-10 |

## P2-05 — Demo de integración con procesos reales (integración)

| Campo | Contenido |
|---|---|
| **Técnica** | Instrucción paso a paso basada en la sección "Mandatory live behavior" del enunciado |
| **Objetivo** | Generar `scripts/demo.py` y evidencias con ambas apps como procesos independientes |
| **Prompt** | *Parte del pedido de P2-02* (el asistente lo hizo como paso de la entrega). Formulación equivalente si lo repiten ustedes: "Escribe un guion de demo que envíe un paquete A→D, falle B–D, reenvíe, restablezca, repita y ejecute la prueba con DAO falso; ejecútalo con ambos procesos reales y guarda la salida." |
| **Salida relevante** | `demo-evidence/demo-log.txt`: rutas `[A,B,D]` (v1) → `[A,C,D]` (v2) → `UNREACHABLE` (v3) → `[A,B,D]` (v5); 503 con el Controller apagado y `/health` del Router en 200. |
| **Problema encontrado** | **Error de la IA:** la primera versión del script de arranque no esperaba a que los servidores respondieran y la demo falló con `ConnectError`; además, un `pkill -f controller.main` terminó también la terminal que lo ejecutaba. |
| **Corrección** | Se agregó una espera activa sobre `GET /health` antes de la demo y se detuvieron los procesos por PID. |
| **Requisitos** | FR-05…FR-08, NFR-05, NFR-11 |

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

## P2-07 — (completar por el equipo)

| Campo | Contenido |
|---|---|
| **Técnica** | |
| **Objetivo** | |
| **Prompt** | |
| **Salida relevante** | |
| **Problema encontrado** | |
| **Corrección** | |
| **Requisitos** | |
