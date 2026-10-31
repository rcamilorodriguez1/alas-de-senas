"""Esquema publicado en OpenAPI del formato único de errores (§8.2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ErrorOut(BaseModel):
    # extra="allow": algunos errores agregan datos (p. ej. `nextHeartAt` en NO_HEARTS).
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="allow")

    status_code: int
    code: str
    message: str
    fields: dict[str, str] | None = Field(
        default=None, description="Mensaje en español por campo (solo VALIDATION_ERROR)."
    )


ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    "4XX": {"model": ErrorOut, "description": "Error de la petición"},
    "5XX": {"model": ErrorOut, "description": "Error del servidor"},
}
