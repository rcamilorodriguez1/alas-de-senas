"""Tarea 0.3 — formato único de errores `{ statusCode, code, message }` (§8.2)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import AppError, register_error_handlers

ENGLISH_PYDANTIC_FRAGMENTS = (
    "Field required",
    "Extra inputs are not permitted",
    "Input should be",
    "value is not",
    "String should",
)


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    display_name: str = Field(alias="displayName")
    age: int


def _build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/locked")
    def locked() -> dict[str, str]:
        raise AppError(403, "LESSON_LOCKED", "Esta lección todavía no está disponible.")

    @app.get("/no-hearts")
    def no_hearts() -> dict[str, str]:
        raise AppError(
            403,
            "NO_HEARTS",
            "Te quedaste sin vidas.",
            extra={"nextHeartAt": "2026-11-04T10:00:00Z"},
        )

    @app.get("/conflict")
    def conflict() -> dict[str, str]:
        raise AppError(409, "SESSION_COMPLETED", "La sesión ya terminó.")

    @app.post("/items")
    def create_item(item: ItemIn) -> dict[str, str]:
        return {"name": item.display_name}

    @app.get("/search")
    def search(q: str) -> dict[str, str]:
        return {"q": q}

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("detalle interno secreto que no debe salir")

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app(), raise_server_exceptions=False)


def _assert_no_english(text: str) -> None:
    for fragment in ENGLISH_PYDANTIC_FRAGMENTS:
        assert fragment not in text


# --- AppError ---------------------------------------------------------------------------------


def test_app_error_es_una_excepcion() -> None:
    error = AppError(403, "LESSON_LOCKED", "Bloqueada")
    assert issubclass(AppError, Exception)
    assert error.status_code == 403
    assert error.code == "LESSON_LOCKED"
    assert error.message == "Bloqueada"


def test_app_error_responde_con_el_formato_unico(client: TestClient) -> None:
    response = client.get("/locked")

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "statusCode": 403,
        "code": "LESSON_LOCKED",
        "message": "Esta lección todavía no está disponible.",
    }


def test_app_error_conserva_tildes_y_enie(client: TestClient) -> None:
    response = client.get("/locked")
    assert "lección" in response.json()["message"]
    assert "está" in response.json()["message"]


def test_app_error_incluye_campos_extra_en_el_cuerpo(client: TestClient) -> None:
    response = client.get("/no-hearts")

    assert response.status_code == 403
    assert response.json() == {
        "statusCode": 403,
        "code": "NO_HEARTS",
        "message": "Te quedaste sin vidas.",
        "nextHeartAt": "2026-11-04T10:00:00Z",
    }


def test_app_error_usa_el_status_indicado(client: TestClient) -> None:
    response = client.get("/conflict")
    assert response.status_code == 409
    assert response.json()["statusCode"] == 409
    assert response.json()["code"] == "SESSION_COMPLETED"


# --- Validación de Pydantic → VALIDATION_ERROR en español -------------------------------------


def test_campos_ausentes_son_obligatorios_en_espanol(client: TestClient) -> None:
    response = client.post("/items", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["statusCode"] == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Revisa los datos enviados."
    assert body["fields"] == {
        "displayName": "Este campo es obligatorio.",
        "age": "Este campo es obligatorio.",
    }
    _assert_no_english(response.text)


def test_el_campo_usa_el_alias_camel_case(client: TestClient) -> None:
    response = client.post("/items", json={"age": 20})

    fields = response.json()["fields"]
    assert "displayName" in fields
    assert "display_name" not in fields


def test_campo_extra_no_permitido(client: TestClient) -> None:
    response = client.post("/items", json={"displayName": "Ana", "age": 20, "isAdmin": True})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["fields"] == {"isAdmin": "Este campo no está permitido."}
    _assert_no_english(response.text)


def test_tipo_invalido_da_mensaje_en_espanol_no_vacio(client: TestClient) -> None:
    response = client.post("/items", json={"displayName": "Ana", "age": "veinte"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert set(body["fields"]) == {"age"}
    message = body["fields"]["age"]
    assert isinstance(message, str)
    assert message.strip() != ""
    _assert_no_english(response.text)


def test_parametro_de_consulta_ausente(client: TestClient) -> None:
    response = client.get("/search")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["fields"] == {"q": "Este campo es obligatorio."}


def test_validacion_no_expone_detail_de_fastapi(client: TestClient) -> None:
    response = client.post("/items", json={})
    assert "detail" not in response.json()


def test_cuerpo_con_valores_no_ascii_es_valido(client: TestClient) -> None:
    response = client.post("/items", json={"displayName": "Muñoz", "age": 30})
    assert response.status_code == 200
    assert response.json() == {"name": "Muñoz"}


# --- HTTPException de Starlette (rutas inexistentes, método no permitido) ---------------------


def test_ruta_inexistente_da_404_con_formato_unico(client: TestClient) -> None:
    response = client.get("/no-existe")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"statusCode", "code", "message"}
    assert body["statusCode"] == 404
    assert body["code"] == "NOT_FOUND"
    assert isinstance(body["message"], str)
    assert body["message"].strip() != ""
    assert body["message"] != "Not Found"


def test_metodo_no_permitido_da_405_con_formato_unico(client: TestClient) -> None:
    response = client.get("/items")

    assert response.status_code == 405
    body = response.json()
    assert body["statusCode"] == 405
    assert body["code"] == "METHOD_NOT_ALLOWED"
    assert isinstance(body["message"], str)
    assert body["message"].strip() != ""
    assert body["message"] != "Method Not Allowed"


# --- Excepciones no controladas ---------------------------------------------------------------


def test_excepcion_no_controlada_da_500_sin_traza(client: TestClient) -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert set(body) == {"statusCode", "code", "message"}
    assert body["statusCode"] == 500
    assert body["code"] == "INTERNAL_ERROR"
    assert isinstance(body["message"], str)
    assert body["message"].strip() != ""
    assert "secreto" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
    assert body["message"] != "Internal Server Error"


def test_extra_no_sobrescribe_los_campos_del_formato() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/tricky")
    def tricky() -> dict[str, str]:
        raise AppError(
            400, "REAL_CODE", "Mensaje real.", extra={"code": "FALSO", "statusCode": 200}
        )

    response = TestClient(app).get("/tricky")
    assert response.status_code == 400
    assert response.json() == {"statusCode": 400, "code": "REAL_CODE", "message": "Mensaje real."}
