"""Raíz de composición del Router (02 §6, R5).

    python -m router.main                       # usa ROUTER_PORT, CONTROLLER_URL, ...
    uvicorn router.main:app --port 8001         # equivalente (1 worker)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from router.clients.http_controller_client import HttpControllerClient
from router.clients.route_provider import RouteProvider
from router.config import RouterSettings, load_settings
from router.controllers import health_controller, packet_controller
from router.dao.forwarding_log_dao import ForwardingLogDAO
from router.dao.jsonlines_forwarding_log_dao import JsonLinesForwardingLogDAO
from router.exceptions import ErrorHandler
from router.services.forwarding_service import ForwardingService


def create_app(
    settings: Optional[RouterSettings] = None,
    route_provider: Optional[RouteProvider] = None,
    log_dao: Optional[ForwardingLogDAO] = None,
) -> FastAPI:
    settings = settings or load_settings()
    provider = route_provider or HttpControllerClient(settings.controller_url, settings.controller_timeout_s)
    dao = log_dao or JsonLinesForwardingLogDAO(settings.forwarding_log_file)
    forwarding_service = ForwardingService(provider, dao)

    app = FastAPI(title="SDN Router", version="1.1")
    app.state.settings = settings
    app.state.forwarding_service = forwarding_service
    ErrorHandler().register(app)
    # Permite que la consola visual del Controller (otro puerto) envíe paquetes desde el navegador.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )
    app.include_router(packet_controller.router)
    app.include_router(health_controller.router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=app.state.settings.port, workers=1)
