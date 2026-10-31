"""Tarea 0.3 — fábrica de la aplicación: documentación solo fuera de producción (§11)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app as module_app
from app.main import create_app

PROD_SECRET = "secreto-de-produccion-con-mas-de-32-caracteres-xyz"
PROD_DB_URL = "postgresql+psycopg://alas:clave@db.example.com:5432/alas"


@pytest.fixture(autouse=True)
def dev_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _production_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="production",
        database_url=PROD_DB_URL,
        jwt_secret=PROD_SECRET,
    )


def test_modulo_expone_una_app_fastapi() -> None:
    assert isinstance(module_app, FastAPI)


def test_create_app_devuelve_una_app_nueva_cada_vez() -> None:
    assert create_app() is not create_app()


def test_en_desarrollo_la_documentacion_existe() -> None:
    client = TestClient(create_app())

    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/redoc").status_code == 200
    openapi = client.get("/api/openapi.json")
    assert openapi.status_code == 200
    assert "/api/health" in openapi.json()["paths"]


def test_en_desarrollo_la_documentacion_no_lleva_csp() -> None:
    client = TestClient(create_app())
    response = client.get("/api/docs")
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_en_produccion_la_documentacion_no_existe() -> None:
    client = TestClient(create_app(_production_settings()))

    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/redoc").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404


def test_la_app_registra_los_manejadores_de_error() -> None:
    client = TestClient(create_app())
    response = client.get("/api/ruta-que-no-existe")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["statusCode"] == 404


def test_la_app_aplica_las_cabeceras_de_seguridad() -> None:
    client = TestClient(create_app())
    response = client.get("/api/ruta-que-no-existe")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(self)"
    assert "content-security-policy" in response.headers


def test_la_app_incluye_la_ruta_de_salud() -> None:
    # FastAPI ≥ 0.16x agrupa las rutas incluidas en un objeto interno: se usa la API pública.
    assert create_app().url_path_for("health") == "/api/health"


def test_los_errores_500_tambien_llevan_cabeceras_de_seguridad() -> None:
    app = create_app()

    @app.get("/api/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("fallo interno")

    response = TestClient(app, raise_server_exceptions=False).get("/api/boom")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers


def test_openapi_publica_el_formato_de_error_y_el_503_de_salud() -> None:
    schema = create_app().openapi()
    responses = schema["paths"]["/api/health"]["get"]["responses"]
    assert {"200", "503", "4XX", "5XX"} <= set(responses)
    error_props = schema["components"]["schemas"]["ErrorOut"]["properties"]
    assert {"statusCode", "code", "message", "fields"} <= set(error_props)
