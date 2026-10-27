"""Proveedores de dependencias del Router (los servicios los crea main.py)."""
from __future__ import annotations

from fastapi import Request

from router.services.forwarding_service import ForwardingService


def get_forwarding_service(request: Request) -> ForwardingService:
    return request.app.state.forwarding_service
