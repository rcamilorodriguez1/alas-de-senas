"""Formato único de errores `{ statusCode, code, message }` (§8.2)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import JsonValue
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

VALIDATION_MESSAGE = "Revisa los datos enviados."
DEFAULT_FIELD_MESSAGE = "El valor no es válido."

FIELD_MESSAGES: dict[str, str] = {
    "missing": "Este campo es obligatorio.",
    "extra_forbidden": "Este campo no está permitido.",
    "string_too_short": "El texto es demasiado corto.",
    "string_too_long": "El texto es demasiado largo.",
    "string_type": "Debe ser un texto.",
    "int_type": "Debe ser un número entero.",
    "int_parsing": "Debe ser un número entero.",
    "float_type": "Debe ser un número.",
    "float_parsing": "Debe ser un número.",
    "bool_type": "Debe ser verdadero o falso.",
    "bool_parsing": "Debe ser verdadero o falso.",
    "literal_error": "El valor no es una de las opciones permitidas.",
    "enum": "El valor no es una de las opciones permitidas.",
    "greater_than_equal": "El valor es demasiado pequeño.",
    "less_than_equal": "El valor es demasiado grande.",
    "value_error": DEFAULT_FIELD_MESSAGE,
    "json_invalid": "El cuerpo de la petición no es un JSON válido.",
    "model_attributes_type": "El cuerpo de la petición no tiene el formato esperado.",
    "dict_type": "El cuerpo de la petición no tiene el formato esperado.",
}

HTTP_ERRORS: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "La petición no es válida."),
    401: ("UNAUTHORIZED", "Debes iniciar sesión."),
    403: ("FORBIDDEN", "No tienes permiso para hacer esto."),
    404: ("NOT_FOUND", "No encontramos lo que buscas."),
    405: ("METHOD_NOT_ALLOWED", "Esta operación no está permitida."),
    429: ("TOO_MANY_REQUESTS", "Hiciste demasiadas peticiones. Espera un momento."),
}


class AppError(Exception):
    """Error de negocio con código estable y mensaje en español para el usuario."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        extra: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}


def unauthorized() -> AppError:
    """401 de sesión terminada (token ausente, inválido o vencido)."""
    return AppError(401, "UNAUTHORIZED", "Tu sesión terminó. Vuelve a ingresar.")


def error_response(
    status_code: int, code: str, message: str, extra: Mapping[str, JsonValue] | None = None
) -> JSONResponse:
    # `extra` nunca sobrescribe los campos del formato único (§8.2).
    body: dict[str, JsonValue] = {
        **(extra or {}),
        "statusCode": status_code,
        "code": code,
        "message": message,
    }
    return JSONResponse(status_code=status_code, content=body)


def _field_name(loc: Sequence[int | str]) -> str:
    # loc = ("body", "displayName") · ("query", "q"); el cuerpo completo ausente es ("body",).
    return str(loc[-1]) if loc else "body"


def validation_fields(errors: Sequence[Mapping[str, object]]) -> dict[str, JsonValue]:
    fields: dict[str, JsonValue] = {}
    for error in errors:
        raw_loc = error.get("loc", ())
        loc = (
            [part for part in raw_loc if isinstance(part, int | str)]
            if isinstance(raw_loc, tuple | list)
            else []
        )
        name = _field_name(loc)
        error_type = str(error.get("type", ""))
        fields.setdefault(name, _field_message(error_type, error.get("ctx")))
    return fields


def _field_message(error_type: str, ctx: object) -> str:
    # Los validadores propios lanzan ValueError con el mensaje en español: se usa tal cual.
    if error_type == "value_error" and isinstance(ctx, Mapping):
        custom = ctx.get("error")
        if isinstance(custom, ValueError) and str(custom):
            return str(custom)
    return FIELD_MESSAGES.get(error_type, DEFAULT_FIELD_MESSAGE)


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return error_response(exc.status_code, exc.code, exc.message, exc.extra)


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    return error_response(
        422,
        "VALIDATION_ERROR",
        VALIDATION_MESSAGE,
        {"fields": validation_fields(exc.errors())},
    )


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    code, message = HTTP_ERRORS.get(
        exc.status_code, ("HTTP_ERROR", "No se pudo completar la petición.")
    )
    response = error_response(exc.status_code, code, message)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


INTERNAL_MESSAGE = "Ocurrió un error inesperado. Intenta de nuevo."


class UnhandledErrorMiddleware:
    """Convierte las excepciones no controladas en el 500 del formato único.

    Un manejador de `Exception` corre en `ServerErrorMiddleware`, por fuera de todos los
    middlewares: sus respuestas saldrían sin cabeceras de seguridad. Este middleware se monta por
    dentro de `SecurityHeadersMiddleware`.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            logger.exception("Error no controlado en %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise
            response = error_response(500, "INTERNAL_ERROR", INTERNAL_MESSAGE)
            await response(scope, receive, send)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_middleware(UnhandledErrorMiddleware)
