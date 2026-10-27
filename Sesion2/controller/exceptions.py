"""Errores de dominio del Controller y su traducción a HTTP (R6, 01 §7, 02 §3.1).

Las excepciones NO conocen HTTP. El único que asigna códigos de estado es ErrorHandler.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("controller")


class DomainError(Exception):
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidParameterError(DomainError):
    code = "INVALID_PARAMETER"


class NodeNotFoundError(DomainError):
    code = "NODE_NOT_FOUND"


class RouteNotFoundError(DomainError):
    code = "ROUTE_NOT_FOUND"


class LinkNotFoundError(DomainError):
    code = "LINK_NOT_FOUND"


class LinkAlreadyFailedError(DomainError):
    code = "LINK_ALREADY_FAILED"


class LinkAlreadyActiveError(DomainError):
    code = "LINK_ALREADY_ACTIVE"


class TopologyUnavailableError(DomainError):
    code = "TOPOLOGY_UNAVAILABLE"


class InvalidTopologyError(DomainError):
    """Código interno: nunca sale de TopologyService como respuesta HTTP."""

    code = "INVALID_TOPOLOGY"


class InvalidLinkMetricsError(DomainError):
    """Código interno: se detecta al validar la topología."""

    code = "INVALID_LINK_METRICS"


def error_body(code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Formato único de error (01 §7)."""
    return {"error": {"code": code, "message": message, "details": details or {}}}


class ErrorHandler:
    """Traduce errores de dominio a HTTP. Sin lógica de negocio."""

    STATUS_BY_ERROR = {
        InvalidParameterError: 400,
        NodeNotFoundError: 404,
        RouteNotFoundError: 404,
        LinkNotFoundError: 404,
        LinkAlreadyFailedError: 409,
        LinkAlreadyActiveError: 409,
        TopologyUnavailableError: 503,
    }

    def register(self, app: FastAPI) -> None:
        app.add_exception_handler(DomainError, self._on_domain_error)
        app.add_exception_handler(RequestValidationError, self._on_validation_error)
        app.add_exception_handler(Exception, self._on_unexpected)

    def handle_domain_error(self, error: DomainError) -> JSONResponse:
        status = self.STATUS_BY_ERROR.get(type(error))
        if status is None:
            # Errores internos (INVALID_TOPOLOGY, INVALID_LINK_METRICS) no deberían llegar aquí.
            return self.handle_unexpected(error)
        return JSONResponse(status_code=status, content=error_body(error.code, error.message, error.details))

    def handle_validation_error(self, error: RequestValidationError) -> JSONResponse:
        problems = [
            {"field": ".".join(str(part) for part in item.get("loc", ())[1:]) or "body", "msg": item.get("msg", "")}
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=400,
            content=error_body("INVALID_PARAMETER", "Invalid or missing parameters", {"errors": problems}),
        )

    def handle_unexpected(self, error: Exception) -> JSONResponse:
        logger.exception("Unexpected error", exc_info=error)
        return JSONResponse(status_code=500, content=error_body("INTERNAL_ERROR", "Unexpected internal error"))

    async def _on_domain_error(self, request: Request, error: DomainError) -> JSONResponse:
        return self.handle_domain_error(error)

    async def _on_validation_error(self, request: Request, error: RequestValidationError) -> JSONResponse:
        return self.handle_validation_error(error)

    async def _on_unexpected(self, request: Request, error: Exception) -> JSONResponse:
        return self.handle_unexpected(error)
