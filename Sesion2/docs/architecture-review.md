# Revisión arquitectónica RA-01…RA-10 (tarea T-18)

Lista definida en `specs/06-test-specification.md` §5. Procedimiento: **A revisa el Router y B revisa el Controller**, comparando el código con `02-static-architecture.md`.

> **Estado:** filas preparadas a partir del código del commit indicado abajo. Cada estudiante abre los archivos citados, confirma o corrige la fila y firma con sus iniciales en la columna *Revisor*.

| ID | Punto de revisión | Evidencia (archivo:línea) | Resultado | Observación | Revisor |
|---|---|---|---|---|---|
| RA-01 | Cada módulo está en la capa correcta | Árbol `controller/{models,schemas,controllers,services,dao}`, `router/{models,schemas,controllers,services,clients,dao}` | OK | Coincide con `02` §5 y §8. | A: ___ / B: ___ |
| RA-02 | Los manejadores HTTP solo convierten la entrada, llaman a **un** método de servicio y serializan | `controller/controllers/route_controller.py:18-29`, `link_controller.py`, `topology_controller.py`, `health_controller.py`, `router/controllers/packet_controller.py:16-24` | OK | Sin bucles sobre nodos/enlaces ni construcción de `trace`. Confirmado por TC-12 (AST) y TC-23 (espías). | A: ___ / B: ___ |
| RA-03 | Toda E/S de archivos está en `dao/` concretos | `controller/dao/json_topology_dao.py:26-41`, `router/dao/jsonlines_forwarding_log_dao.py:34-83` | OK | `services/` y `controllers/` no usan `open`, `Path` ni `json.` (TC-12, TC-13). | A: ___ / B: ___ |
| RA-04 | Los servicios reciben dependencias por constructor tipadas con **interfaces** | `controller/services/topology_service.py:34` (`TopologyDAO`), `routing_service.py:14`, `router/services/forwarding_service.py:30-34` (`RouteProvider`, `ForwardingLogDAO`) | OK | — | A: ___ / B: ___ |
| RA-05 | Solo `main.py` instancia DAO y clientes concretos; controladores usan `Depends` | `controller/main.py:29`, `router/main.py:29-30`; `controllers/dependencies.py` en ambas apps | OK | `create_app` acepta dobles de prueba como parámetros (inyección). | A: ___ / B: ___ |
| RA-06 | Excepciones sin HTTP; solo `ErrorHandler` asigna códigos | `controller/exceptions.py:74-82`, `router/exceptions.py:60-67` | OK | No hay `HTTPException` ni `status_code` en `services/`. | A: ___ / B: ___ |
| RA-07 | Modelos inmutables; `_current` solo se reasigna bajo `_write_lock`; una instantánea por consulta; sin lock durante Dijkstra | `controller/models/*.py` (`frozen=True`), `topology_service.py:45-61, 108-122`, `routing_service.py:18` | OK | TC-20 lo verifica con 8 hilos lectores y 1 escritor. | A: ___ / B: ___ |
| RA-08 | `save()` en `DELIVERED` y `UNREACHABLE`, nunca en errores; captura cualquier fallo; DAO serializa, usa lock, una escritura y `fsync` | `router/services/forwarding_service.py:37-79`, `jsonlines_forwarding_log_dao.py:34-51` | OK | TC-09, TC-15, TC-24, TC-26. | A: ___ / B: ___ |
| RA-09 | `HttpControllerClient` implementa todas las filas de `04` §3 regla 4 | `router/clients/http_controller_client.py:40-138` | OK | TC-25 cubre 16 casos (tabla + fallos de red). | A: ___ / B: ___ |
| RA-10 | El Router no importa `networkx` ni calcula costos o caminos | Todo `router/` | OK | TC-14 (AST). `parse_route_response` solo valida formato (A-15). | A: ___ / B: ___ |

Commit revisado: `________` · Fecha: `________`
