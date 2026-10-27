"""Proveedores de dependencias para los controladores (FastAPI Depends).

Los servicios los crea main.py (raíz de composición) y los guarda en app.state.
En pruebas se reemplazan con app.dependency_overrides (TC-23).
"""
from __future__ import annotations

from fastapi import Request

from controller.services.routing_service import RoutingService
from controller.services.topology_service import TopologyService


def get_routing_service(request: Request) -> RoutingService:
    return request.app.state.routing_service


def get_topology_service(request: Request) -> TopologyService:
    return request.app.state.topology_service
