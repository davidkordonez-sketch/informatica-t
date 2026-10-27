"""Errores de dominio del Router y su traducción a HTTP (R6, 01 §7, 02 §3.1)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("router")


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
    """ForwardingService la convierte en UNREACHABLE; no debería llegar al ErrorHandler."""

    code = "ROUTE_NOT_FOUND"


class ControllerUnavailableError(DomainError):
    code = "CONTROLLER_UNAVAILABLE"


class ControllerTimeoutError(DomainError):
    code = "CONTROLLER_TIMEOUT"


class ControllerBadResponseError(DomainError):
    code = "CONTROLLER_BAD_RESPONSE"


class PersistenceError(DomainError):
    """Código interno: ForwardingService la convierte en log_persisted = false + aviso."""

    code = "PERSISTENCE_ERROR"


def error_body(code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


class ErrorHandler:
    STATUS_BY_ERROR = {
        InvalidParameterError: 400,
        NodeNotFoundError: 404,
        RouteNotFoundError: 404,
        ControllerBadResponseError: 502,
        ControllerUnavailableError: 503,
        ControllerTimeoutError: 503,
    }

    def register(self, app: FastAPI) -> None:
        app.add_exception_handler(DomainError, self._on_domain_error)
        app.add_exception_handler(RequestValidationError, self._on_validation_error)
        app.add_exception_handler(Exception, self._on_unexpected)

    def handle_domain_error(self, error: DomainError) -> JSONResponse:
        status = self.STATUS_BY_ERROR.get(type(error))
        if status is None:  # p. ej. PersistenceError, que nunca debería escapar
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
