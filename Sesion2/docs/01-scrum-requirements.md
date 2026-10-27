# Recolección de Requisitos basada en Scrum

*Documento de la Sesión 2 elaborado con la estructura de la plantilla "Scrum-Based Requirements Collection Template". Fuente de detalle: `Informatica3/Informatica3/01-requirements.md` (v1.1).*

| Campo | Descripción |
|---|---|
| Curso | Informática para Telecomunicaciones |
| Programa | Ingeniería de Telecomunicaciones |
| Proyecto | Controlador y Enrutador SDN (simulación a nivel de aplicación) |
| Integrantes | Paula Andrea Montero, Gabriel Navia, David Ordoñez |
| Profesor | Oscar Mauricio Caicedo Rendon |
| Fecha | 2026-10-27 |
| Versión | 1.0 |

## 1. Visión del producto

Desarrollar un sistema de enrutamiento centralizado inspirado en SDN, compuesto por dos aplicaciones Python independientes. El **Controller** (plano de control) es el único que conoce la topología de la red y calcula las rutas. El **Router** (plano de datos) no calcula caminos: le pide la ruta al Controller por HTTP para cada paquete, simula el reenvío salto a salto y registra el resultado. El sistema debe reaccionar a fallos y restablecimientos de enlaces, y estar organizado con MVC y DAO para que cada parte sea reemplazable y comprobable.

## 2. Objetivo del producto

Implementar en Python, con FastAPI y NetworkX, un Controller que cargue una topología desde JSON, calcule rutas de costo mínimo con Dijkstra según tres métricas (retardo, inverso del ancho de banda y pérdida) y las exponga por REST, y un Router que obtenga esas rutas por HTTP/JSON, simule el reenvío y lo registre en un log, demostrando el funcionamiento con pruebas automáticas y una demo en vivo.

## 3. Interesados (stakeholders)

| Interesado | Rol | Interés |
|---|---|---|
| Profesor | Evaluador y guía del proyecto | Verificar la aplicación correcta de requisitos, MVC/DAO, pruebas y conceptos de redes |
| Estudiante A | Desarrollador del Controller | Topología, Dijkstra, fallos de enlace y API REST del Controller |
| Estudiante B | Desarrollador del Router | Reenvío simulado, cliente HTTP, log de reenvíos y API REST del Router |
| Aplicación Controller | Componente del sistema | Mantener la topología y decidir rutas |
| Aplicación Router | Componente del sistema | Pedir rutas, simular el reenvío y registrar resultados |
| Cliente / usuario | Usuario | Enviar paquetes simulados y ver el trace |
| Administrador de red | Usuario | Simular fallos y restablecimientos de enlaces y verificar que las rutas cambian |

## 4. Formato de historia de usuario

Como **[tipo de usuario]**, quiero **[funcionalidad]**, para **[beneficio]**.

## 5. Backlog de requisitos funcionales

Estado al 2026-10-26: implementado y verificado con las pruebas indicadas (`tests/test-results.txt`: 76 pruebas aprobadas).

| ID | Historia de usuario | Prioridad | Criterios de aceptación | Sprint | Estado |
|---|---|---|---|---|---|
| FR-01 | Como Controller, quiero cargar la topología desde un archivo JSON mediante un `TopologyDAO`, para separar el almacenamiento de la lógica. | Alta | Con un JSON válido, `/health` indica `topology_loaded: true`. Si el archivo no existe o está corrupto, el proceso sigue vivo en modo `degraded` y `/route` responde 503. | Sprint 2 | Hecho (TC-17, TC-21) |
| FR-02 | Como Controller, quiero representar cualquier topología válida con NetworkX, para no depender de un diseño fijo. | Alta | Topologías lineal, anillo, malla y con nodo aislado cargan sin cambiar código. Un enlace a un nodo inexistente deja la topología sin cargar. | Sprint 2 | Hecho (TC-17) |
| FR-03 | Como servicio de enrutamiento, quiero calcular rutas de costo mínimo con Dijkstra, para elegir el camino más eficiente. | Alta | A→D por `delay` = `[A,B,D]` con costo 20. `src = dst` da `[src]` con costo 0. Un nodo aislado da `ROUTE_NOT_FOUND`. | Sprint 2 | Hecho (TC-01, TC-20) |
| FR-04 | Como servicio de enrutamiento, quiero convertir los atributos del enlace en un costo no negativo, para que Dijkstra refleje la calidad del enlace. | Alta | `delay` = d; `bandwidth` = 1/b; `loss` = −ln(1−p). Un enlace con p = 1 queda excluido. b ≤ 0 produce un error controlado. | Sprint 2 | Hecho (TC-02, TC-10) |
| FR-05 | Como Controller, quiero exponer rutas, topología y salud por REST, para que el Router las consuma por HTTP. | Alta | `GET /route`, `GET /topology` y `GET /health` responden según `04-api-contract.md`. Parámetro inválido → 400; nodo inexistente → 404 `NODE_NOT_FOUND`. | Sprint 2 | Hecho (TC-11) |
| FR-06 | Como administrador, quiero fallar y restablecer enlaces por REST, para comprobar que las rutas se actualizan. | Alta | Tras fallar B–D, A→D = `[A,C,D]` (costo 25, versión 2). Al restablecer vuelve `[A,B,D]` (versión 3). Fallar dos veces el mismo enlace → 409. | Sprint 2 | Hecho (TC-03, TC-04, TC-11) |
| FR-07 | Como Router, quiero pedir la ruta al Controller por HTTP, para mantener separados el control y el reenvío. | Alta | El Router no importa `networkx`. Cada paquete genera un `GET /route`. Controller caído → 503; respuesta inválida → 502. | Sprint 2 | Hecho (TC-05, TC-14, TC-25) |
| FR-08 | Como Router, quiero simular el reenvío salto a salto, para verificar el plano de datos. | Alta | `[A,B,D]` produce los saltos A→B y B→D. Un destino aislado responde 200 con `UNREACHABLE` y `trace` vacío. | Sprint 2 | Hecho (TC-06, TC-07) |
| FR-09 | Como sistema SDN, quiero manejar errores esperados de forma controlada, para que ninguna aplicación se caiga. | Alta | Errores 400/404/409/502/503 con formato único `{"error": {code, message, details}}`. `/health` sigue respondiendo. | Sprint 2 | Hecho (TC-07, TC-11, TC-25) |
| FR-10 | Como Router, quiero registrar cada resultado con `ForwardingLogDAO`, para tener un historial comprobable. | Alta | Se guardan los resultados `DELIVERED` y `UNREACHABLE`. Si el log falla, la respuesta es 200 con `log_persisted: false` y un aviso. | Sprint 2 | Hecho (TC-09, TC-15, TC-24, TC-26) |

## 6. Backlog de requisitos no funcionales

| ID | Requisito | Descripción | Prioridad | Criterios de aceptación |
|---|---|---|---|---|
| NFR-01 | MVC | Ambas apps separan Modelo, Vista (esquemas) y Controlador (manejadores HTTP). | Alta | Módulos en `models/`, `schemas/`, `controllers/`, `services/`, `dao/`. Revisión RA-01…RA-06. |
| NFR-02 | DAO | El acceso a archivos pasa solo por `TopologyDAO` y `ForwardingLogDAO`. | Alta | 0 usos de `open()` o `json.load` en `services/` (TC-13). |
| NFR-03 | Separación de lógica | Dijkstra y el reenvío están fuera de los manejadores HTTP. | Alta | 0 imports de `networkx` en `controllers/` (TC-12); delegación verificada con TC-23. |
| NFR-04 | Interoperabilidad | La comunicación usa HTTP con mensajes JSON según el contrato. | Alta | Endpoints y esquemas coinciden con `04-api-contract.md` (TC-11, TC-16). |
| NFR-05 | Configurabilidad | Puertos, archivos y URL/timeout del Controller se cambian sin tocar código. | Media | Variables de entorno `CONTROLLER_PORT`, `TOPOLOGY_FILE`, `CONTROLLER_URL`… (TC-16, TC-19). |
| NFR-06 | Robustez | Los fallos previstos no detienen las aplicaciones. | Media | 0 caídas de proceso en TC-07, TC-15, TC-17, TC-19. |
| NFR-07 | Diseño orientado a objetos | Las clases reciben sus dependencias por el constructor. | Media | Sin variables globales ocultas; revisión RA-04 y RA-05. |
| NFR-08 | Trazabilidad | Cada requisito se vincula con tareas, componentes y pruebas. | Media | Matriz en `05-implementation-plan.md` §3. |
| NFR-09 | Testabilidad | Los DAO se reemplazan por dobles de prueba. | Alta | TC-08 y TC-09 corren sin HTTP ni archivos. |
| NFR-10 | Rendimiento | Las consultas de ruta son rápidas en una red grande. | Baja | p95 ≤ 200 ms en 200 nodos y 1000 enlaces (TC-18; medido ≈ 12 ms). |
| NFR-11 | Resiliencia | Si el Controller no responde, el Router falla rápido y sigue vivo. | Media | 503 en ≤ timeout + 1 s y `/health` en 200 (TC-19). |
| NFR-12 | Consistencia | La ruta y su versión de topología salen del mismo estado aunque haya cambios simultáneos. | Media | 0 respuestas incoherentes con 8 hilos lectores y 1 escritor (TC-20). |

## 7. Product backlog

Esfuerzo estimado en **minutos de la Sesión 2** (108 min en total, ver `05-implementation-plan.md` §1.3). A = Estudiante A, B = Estudiante B.

| ID backlog | Requisito | Tarea | Responsable | Esfuerzo estimado | Sprint | Estado |
|---|---|---|---|---|---|---|
| PB-01 | NFR-05 | Crear el repositorio, la estructura de carpetas y el entorno (T-00) | A y B | 8 min | Sprint 2 | Hecho |
| PB-02 | FR-02, FR-03 | Modelos del Controller (`Link`, `Topology`, `Route`) y excepciones (T-01) | A | 8 min | Sprint 2 | Hecho |
| PB-03 | FR-04 | `LinkCostCalculator` con las tres métricas (T-02) | A | 5 min | Sprint 2 | Hecho |
| PB-04 | FR-01 | `TopologyDAO` y `JsonTopologyDAO` (T-03) | A | 7 min | Sprint 2 | Hecho |
| PB-05 | FR-01, FR-02, FR-06 | `TopologyService`: carga, validación, fallos y restablecimientos (T-04) | A | 12 min | Sprint 2 | Hecho |
| PB-06 | FR-03 | `RoutingService` con Dijkstra (T-05) | A | 8 min | Sprint 2 | Hecho |
| PB-07 | FR-05, FR-06, FR-09 | API REST del Controller y `main.py` (T-06) | A | 12 min | Sprint 2 | Hecho |
| PB-08 | FR-08 | Modelos del Router (`Packet`, `RouteInfo`, `ForwardingResult`) (T-07) | B | 8 min | Sprint 2 | Hecho |
| PB-09 | FR-10 | `ForwardingLogDAO` y `JsonLinesForwardingLogDAO` (T-08) | B | 8 min | Sprint 2 | Hecho |
| PB-10 | FR-07 | `RouteProvider` y `HttpControllerClient` (T-09) | B | 10 min | Sprint 2 | Hecho |
| PB-11 | FR-08, FR-10 | `ForwardingService`: reenvío y registro (T-10) | B | 12 min | Sprint 2 | Hecho |
| PB-12 | FR-08, FR-09 | API REST del Router y `main.py` (T-11) | B | 12 min | Sprint 2 | Hecho |
| PB-13 | FR-01…FR-06 | Pruebas del Controller (T-12) | A | junto con cada tarea | Sprint 2 | Hecho |
| PB-14 | FR-07…FR-10 | Pruebas del Router (T-13) | B | junto con cada tarea | Sprint 2 | Hecho |
| PB-15 | NFR-01…NFR-03 | Pruebas de arquitectura (T-14) | A y B | 4 min | Sprint 3 | Hecho |
| PB-16 | FR-05…FR-08 | Integración con dos procesos reales y demo (T-15) | A y B | 10 min | Sprint 3 | Hecho |
| PB-17 | — | Reserva para corregir defectos | A y B | 12 min | Sprint 3 | Usado |
| PB-18 | NFR-01 | Revisión arquitectónica cruzada RA-01…RA-10 (T-18) | A y B | 4 min | Sprint 3 | Pendiente de firma |
| PB-19 | NFR-08 | README, `test-results.txt`, evidencias y `prompts-session2.md` (T-16, T-17) | A y B | 8 min | Sprint 3 | Pendiente: capturas y prompt propio |

## 8. Planificación de sprints

Se organizan tres sprints. El Sprint 1 corresponde a la Sesión 1; los Sprints 2 y 3 dividen los 108 minutos de la Sesión 2 según los hitos de `05-implementation-plan.md` §1.3.

**Sprint 1 — Especificación (Sesión 1, terminado)**

| Campo | Descripción |
|---|---|
| Número de sprint | 1 |
| Objetivo del sprint | Especificar y congelar requisitos, arquitectura, contrato de API, plan y pruebas, sin escribir código |
| Fecha de inicio | _completar_ (fecha de la Sesión 1) |
| Fecha de fin | 2026-10-26 (v1.1, tras las correcciones SPDR) |
| Integrantes | Estudiante A y Estudiante B |

| ID tarea | Requisito | Descripción | Responsable | Tiempo estimado | Estado |
|---|---|---|---|---|---|
| S1-01 | FR-01…FR-10, NFR-01…NFR-12 | `01-requirements.md` | A y B | 30 min | Hecho |
| S1-02 | NFR-01, NFR-02 | `02-static-architecture.md` y `03-dynamic-architecture.md` | A y B | 35 min | Hecho |
| S1-03 | FR-05 | `04-api-contract.md` | A y B | 10 min | Hecho |
| S1-04 | NFR-08 | `05-implementation-plan.md` y `06-test-spec.md` | A y B | 15 min | Hecho |

**Sprint 2 — Implementación (Sesión 2, minutos 0 a 70)**

| Campo | Descripción |
|---|---|
| Número de sprint | 2 |
| Objetivo del sprint | Tener ambas aplicaciones funcionando con MVC/DAO y las 11 pruebas obligatorias en verde (hito H2) |
| Fecha de inicio | _completar_ (fecha de la Sesión 2) |
| Fecha de fin | _completar_ |
| Integrantes | Estudiante A y Estudiante B |

| ID tarea | Requisito | Descripción | Responsable | Tiempo estimado | Estado |
|---|---|---|---|---|---|
| T-01…T-06 | FR-01…FR-06 | Controller completo (PB-02 a PB-07) | A | 52 min | Hecho |
| T-07…T-11 | FR-07…FR-10 | Router completo (PB-08 a PB-12) | B | 50 min | Hecho |
| T-12 | FR-01…FR-06 | Pruebas obligatorias del Controller: TC-01…TC-04, TC-08 | A | junto con el código | Hecho |
| T-13 | FR-07…FR-10 | Pruebas obligatorias del Router: TC-05…TC-07, TC-09, TC-24 | B | junto con el código | Hecho |

**Sprint 3 — Integración, verificación y entrega (Sesión 2, minutos 70 a 108)**

| Campo | Descripción |
|---|---|
| Número de sprint | 3 |
| Objetivo del sprint | Integrar los dos procesos, ejecutar la demo, corregir defectos y entregar con evidencias |
| Fecha de inicio | _completar_ |
| Fecha de fin | _completar_ |
| Integrantes | Estudiante A y Estudiante B |

| ID tarea | Requisito | Descripción | Responsable | Tiempo estimado | Estado |
|---|---|---|---|---|---|
| T-15 | FR-05…FR-08 | Integración y demo con dos procesos reales (TC-16) | A y B | 10 min | Hecho |
| T-14, T-18 | NFR-01…NFR-03 | Pruebas de arquitectura y revisión cruzada RA | A y B | 8 min | Pruebas hechas; revisión pendiente de firma |
| — | — | Corrección de defectos (reserva) | A y B | 12 min | Usado |
| T-16, T-17 | NFR-08 | README, resultados, evidencias y prompts | A y B | 8 min | Pendiente: capturas y prompt propio |

## 9. Definición de hecho (Definition of Done)

| Criterio | ¿Cumplido? |
|---|---|
| La funcionalidad está implementada en Python | Sí: `controller/` y `router/` |
| El código se probó con éxito | Sí: 76 de 76 pruebas aprobadas (`tests/test-results.txt`) |
| Se documentaron las entradas y salidas esperadas | Sí: `04-api-contract.md` y criterios de aceptación de `01-requirements.md` |
| Se cumplieron los criterios de aceptación | Sí: cada FR está vinculado a sus pruebas (sección 5) |
| El código se integró con el resto del sistema | Sí: TC-16 con dos procesos reales y `demo-evidence/demo-log.txt` |
| La funcionalidad se demostró al profesor | Pendiente: se hará en la defensa |
