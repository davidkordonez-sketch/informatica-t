"""Raíz de composición del Controller (02 §6, R5).

Es el ÚNICO lugar que conoce las clases concretas. Ejecutar desde la raíz del repo:

    python -m controller.main                      # usa CONTROLLER_PORT / TOPOLOGY_FILE
    uvicorn controller.main:app --port 8000        # equivalente (1 worker)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from controller.config import UI_DIR, ControllerSettings, load_settings
from controller.controllers import (
    health_controller,
    link_controller,
    route_controller,
    topology_controller,
    ui_controller,
)
from controller.dao.json_topology_dao import JsonTopologyDAO
from controller.dao.topology_dao import TopologyDAO
from controller.exceptions import ErrorHandler, TopologyUnavailableError
from controller.services.link_cost_calculator import LinkCostCalculator
from controller.services.routing_service import RoutingService
from controller.services.topology_service import TopologyService

logger = logging.getLogger("controller")


def create_app(settings: Optional[ControllerSettings] = None, topology_dao: Optional[TopologyDAO] = None) -> FastAPI:
    settings = settings or load_settings()
    dao = topology_dao or JsonTopologyDAO(settings.topology_file)
    topology_service = TopologyService(dao, LinkCostCalculator())
    routing_service = RoutingService(topology_service)

    app = FastAPI(title="SDN Controller", version="1.1")
    app.state.settings = settings
    app.state.topology_service = topology_service
    app.state.routing_service = routing_service
    ErrorHandler().register(app)
    for module in (route_controller, link_controller, topology_controller, health_controller, ui_controller):
        app.include_router(module.router)
    # Consola visual (capa Vista): http://localhost:8000/ -> /ui/
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")

    try:  # A-13: intento de carga al arrancar; si falla, el proceso sigue vivo (degraded)
        topology_service.ensure_loaded()
    except TopologyUnavailableError as error:
        logger.warning("Controller started in DEGRADED mode: %s %s", error.message, error.details)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=app.state.settings.port, workers=1)
