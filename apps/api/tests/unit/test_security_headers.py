"""Tarea 0.3 — cabeceras de seguridad y CSP (§11)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from app.core.security_headers import SecurityHeadersMiddleware

EXPECTED_CSP = (
    "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; "
    "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
    "style-src 'self' 'unsafe-inline'; font-src 'self'"
)

BASE_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(self)",
}


def _build_app() -> FastAPI:
    # docs_url/redoc_url desactivados: se simulan con rutas propias para probar solo el middleware.
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/")
    def index() -> PlainTextResponse:
        return PlainTextResponse("<html>SPA</html>", media_type="text/html")

    @app.get("/api/docs")
    def docs() -> PlainTextResponse:
        return PlainTextResponse("docs")

    @app.get("/api/docs/oauth2-redirect")
    def docs_redirect() -> PlainTextResponse:
        return PlainTextResponse("redirect")

    @app.get("/api/redoc")
    def redoc() -> PlainTextResponse:
        return PlainTextResponse("redoc")

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app())


def _assert_base_headers(headers: dict[str, str]) -> None:
    for name, value in BASE_HEADERS.items():
        assert headers.get(name) == value


@pytest.mark.parametrize("path", ["/api/ping", "/"])
def test_respuestas_normales_llevan_todas_las_cabeceras(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    _assert_base_headers(dict(response.headers))
    assert response.headers["content-security-policy"] == EXPECTED_CSP


def test_la_csp_es_exactamente_la_de_la_especificacion(client: TestClient) -> None:
    csp = client.get("/api/ping").headers["content-security-policy"]
    assert "'wasm-unsafe-eval'" in csp  # MediaPipe y TensorFlow.js (WASM)
    assert "worker-src 'self' blob:" in csp
    assert "'unsafe-eval'" not in csp.replace("'wasm-unsafe-eval'", "")
    assert csp == EXPECTED_CSP


@pytest.mark.parametrize("path", ["/api/docs", "/api/docs/oauth2-redirect", "/api/redoc"])
def test_documentacion_no_lleva_csp_pero_si_las_demas_cabeceras(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    _assert_base_headers(dict(response.headers))


def test_respuestas_de_error_404_tambien_llevan_cabeceras(client: TestClient) -> None:
    response = client.get("/api/no-existe")

    assert response.status_code == 404
    _assert_base_headers(dict(response.headers))
    assert response.headers["content-security-policy"] == EXPECTED_CSP


def test_el_middleware_no_altera_el_cuerpo(client: TestClient) -> None:
    response = client.get("/api/ping")
    assert response.json() == {"ok": True}


def test_las_cabeceras_no_se_duplican(client: TestClient) -> None:
    response = client.get("/api/ping")
    assert len(response.headers.get_list("content-security-policy")) == 1
    assert len(response.headers.get_list("x-content-type-options")) == 1
