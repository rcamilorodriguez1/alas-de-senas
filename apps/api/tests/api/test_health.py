"""Tarea 0.3/0.4 — `GET /api/health` contra la BD de prueba real."""

from __future__ import annotations

from fastapi.testclient import TestClient

EXPECTED_CSP = (
    "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; "
    "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
    "style-src 'self' 'unsafe-inline'; font-src 'self'"
)


def test_health_con_bd_real_responde_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "db": True}


def test_health_trae_la_csp_y_las_cabeceras(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.headers["content-security-policy"] == EXPECTED_CSP
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(self)"


def test_health_repetido_no_agota_el_pool(client: TestClient) -> None:
    # pool_size=5: si get_db no cerrara la sesión, las peticiones siguientes se bloquearían.
    for _ in range(12):
        assert client.get("/api/health").status_code == 200
