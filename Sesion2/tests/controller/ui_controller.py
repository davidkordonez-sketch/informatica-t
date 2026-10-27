"""UiController: la raíz del Controller (GET /) lleva a la consola visual.

La consola (controller/ui/) es parte de la capa VISTA: HTML/CSS/JS que solo consume la
API REST. Los archivos los sirve StaticFiles, montado en main.py (raíz de composición),
así que este controlador no toca el sistema de archivos (regla R1, TC-12).
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(include_in_schema=False)


class UiController:
    def index(self) -> RedirectResponse:
        return RedirectResponse(url="/ui/")


@router.get("/")
def index() -> RedirectResponse:
    return UiController().index()
