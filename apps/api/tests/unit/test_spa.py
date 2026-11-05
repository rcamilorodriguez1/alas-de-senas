"""Tarea 11.1 — FastAPI sirve la SPA compilada con fallback a `index.html` (§11, B26, B54, B55).

Sin base de datos: solo se piden rutas estáticas, de la SPA o inexistentes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.routing import Mount

from app.core.config import Settings, get_settings
from app.core.security_headers import CONTENT_SECURITY_POLICY
from app.main import create_app

IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"
INDEX_HTML = '<!doctype html><html><body><div id="root">Alas de Señas</div></body></html>'
ASSET_JS = "console.log('tomi');"
MODEL_JSON = '{"format": "layers-model"}'
WASM_BYTES = b"\x00asm\x01\x00\x00\x00"
FAVICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
VIDEO_BYTES = b"video-de-prueba"
SECRET_TEXT = "secreto-fuera-de-dist"


@pytest.fixture(autouse=True)
def dev_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="development",
        web_dist_dir=tmp_path / "dist",
        media_dir=tmp_path / "media",
    )


DIST_MANIFEST = '{"signs": {"gracias": "MANIFIESTO-SECRETO"}}'


def _build_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "models" / "lsc-gestos").mkdir(parents=True)
    (dist / "mediapipe" / "wasm").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text(ASSET_JS, encoding="utf-8")
    (dist / "models" / "lsc-gestos" / "model.json").write_text(MODEL_JSON, encoding="utf-8")
    (dist / "mediapipe" / "wasm" / "x.wasm").write_bytes(WASM_BYTES)
    (dist / "favicon.svg").write_text(FAVICON_SVG, encoding="utf-8")
    # Vite copia public/media dentro de dist: en Docker MEDIA_DIR = dist/media (B54).
    (dist / "media" / "v").mkdir(parents=True)
    (dist / "media" / "manifest.json").write_text(DIST_MANIFEST, encoding="utf-8")
    return dist


def _build_media(tmp_path: Path) -> Path:
    media = tmp_path / "media"
    (media / "v").mkdir(parents=True)
    (media / "v" / "gracias-0123abcd.mp4").write_bytes(VIDEO_BYTES)
    (media / "manifest.json").write_text('{"gracias": "v/gracias-0123abcd.mp4"}', encoding="utf-8")
    return media


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    _build_dist(tmp_path)
    _build_media(tmp_path)
    (tmp_path / "secreto.txt").write_text(SECRET_TEXT, encoding="utf-8")
    return TestClient(create_app(_settings(tmp_path)))


def _assert_is_index(response_text: str) -> None:
    assert "Alas de Señas" in response_text
    assert '<div id="root">' in response_text


def _assert_json_not_found(status: int, body: dict[str, object]) -> None:
    assert status == 404
    assert body["code"] == "NOT_FOUND"
    assert body["statusCode"] == 404


# --- Montaje ---------------------------------------------------------------------------------


def test_create_app_monta_spafiles_en_la_raiz_con_web_dist_dir(tmp_path: Path) -> None:
    from app.core.spa import SpaFiles

    app: FastAPI = create_app(_settings(tmp_path))
    mounts = [route for route in app.routes if isinstance(route, Mount)]
    spa_mounts = [m for m in mounts if isinstance(m.app, SpaFiles)]
    assert len(spa_mounts) == 1
    assert spa_mounts[0].path == ""
    # Es el último montaje: no tapa los routers ni `/media`.
    assert app.routes[-1] is spa_mounts[0]
    spa_app = spa_mounts[0].app
    assert isinstance(spa_app, SpaFiles)
    assert Path(str(spa_app.directory)) == tmp_path / "dist"


def test_spafiles_es_un_staticfiles() -> None:
    from starlette.staticfiles import StaticFiles

    from app.core.spa import SpaFiles

    assert issubclass(SpaFiles, StaticFiles)


# --- index.html y rutas de la SPA ------------------------------------------------------------


def test_la_raiz_devuelve_index_html_sin_cache_y_con_csp(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    _assert_is_index(response.text)
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == NO_CACHE
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


@pytest.mark.parametrize(
    "path",
    [
        "/aprender",
        "/diccionario/gracias",
        "/diccionario/niño",
        "/perfil/ajustes/",
        "/leccion/M1-N1-L1",
    ],
)
def test_las_rutas_de_la_spa_devuelven_index_html(client: TestClient, path: str) -> None:
    # B26: recargar una ruta de la SPA no debe dar 404.
    response = client.get(path)

    assert response.status_code == 200
    _assert_is_index(response.text)
    assert response.headers["cache-control"] == NO_CACHE
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


def test_index_html_pedido_directamente_va_sin_cache(client: TestClient) -> None:
    response = client.get("/index.html")

    assert response.status_code == 200
    _assert_is_index(response.text)
    assert response.headers["cache-control"] == NO_CACHE


def test_las_cabeceras_base_de_seguridad_van_en_la_spa(client: TestClient) -> None:
    response = client.get("/aprender")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(self)"


@pytest.mark.parametrize("path", ["/apiario", "/assetsx", "/modelos", "/mediateca"])
def test_rutas_que_solo_comparten_prefijo_de_texto_son_de_la_spa(
    client: TestClient, path: str
) -> None:
    # La exclusión es por segmento: `/apiario` no es `/api`.
    response = client.get(path)

    assert response.status_code == 200
    _assert_is_index(response.text)


# --- Archivos reales de dist -----------------------------------------------------------------


def test_los_assets_con_hash_son_inmutables(client: TestClient) -> None:
    response = client.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.text == ASSET_JS
    assert response.headers["cache-control"] == IMMUTABLE
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("/models/lsc-gestos/model.json", MODEL_JSON.encode()),
        ("/mediapipe/wasm/x.wasm", WASM_BYTES),
        ("/favicon.svg", FAVICON_SVG.encode()),
    ],
)
def test_otros_archivos_de_dist_van_sin_cache(
    client: TestClient, path: str, content: bytes
) -> None:
    # Se pueden republicar con el mismo nombre: no pueden ser inmutables.
    response = client.get(path)

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["cache-control"] == NO_CACHE


@pytest.mark.parametrize(
    "path",
    [
        "/assets/index-no-existe.js",
        "/assets/",
        "/assets",
        "/models/lsc-gestos/no-existe.json",
        "/models/otro/model.json",
        "/models",
        "/mediapipe/wasm/no-existe.wasm",
        "/mediapipe",
    ],
)
def test_archivos_inexistentes_de_carpetas_estaticas_dan_404_json_y_nunca_index(
    client: TestClient, path: str
) -> None:
    # Un <script> o el cargador del modelo recibirían HTML en lugar de un 404.
    response = client.get(path)

    _assert_json_not_found(response.status_code, response.json())
    assert "Alas de Señas" not in response.text
    assert response.headers.get("cache-control") != IMMUTABLE


# --- /api ------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/ruta-que-no-existe", "/api", "/api/", "/api/lecciones/x/y"])
def test_api_inexistente_sigue_dando_404_json_con_dist_presente(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    _assert_json_not_found(response.status_code, response.json())
    assert "Alas de Señas" not in response.text


def test_api_docs_en_desarrollo_sigue_sin_csp(client: TestClient) -> None:
    response = client.get("/api/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    assert "swagger" in response.text.lower()


def test_openapi_json_sigue_disponible_en_desarrollo(client: TestClient) -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert "/api/health" in response.json()["paths"]


# --- /media ----------------------------------------------------------------------------------


def test_media_manifest_sigue_sin_publicarse(client: TestClient) -> None:
    # B54: el manifiesto relaciona cada seña con su video.
    response = client.get("/media/manifest.json")

    _assert_json_not_found(response.status_code, response.json())
    assert "gracias" not in response.text


def test_media_videos_siguen_inmutables(client: TestClient) -> None:
    response = client.get("/media/v/gracias-0123abcd.mp4")

    assert response.status_code == 200
    assert response.content == VIDEO_BYTES
    assert response.headers["cache-control"] == IMMUTABLE


@pytest.mark.parametrize("path", ["/media/v/no-existe.mp4", "/media", "/media/", "/media/otra"])
def test_media_inexistente_da_404_y_nunca_index(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert "Alas de Señas" not in response.text


# --- Sin build de la SPA ---------------------------------------------------------------------


def test_sin_carpeta_dist_la_app_arranca_y_las_rutas_de_la_spa_dan_404(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    response = client.get("/aprender")
    _assert_json_not_found(response.status_code, response.json())
    root = client.get("/")
    assert root.status_code == 404


def test_con_dist_vacia_las_rutas_de_la_spa_dan_404(tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir()
    client = TestClient(create_app(_settings(tmp_path)))

    response = client.get("/aprender")
    _assert_json_not_found(response.status_code, response.json())


def test_con_dist_sin_index_los_assets_existentes_se_sirven(tmp_path: Path) -> None:
    dist = _build_dist(tmp_path)
    (dist / "index.html").unlink()
    client = TestClient(create_app(_settings(tmp_path)))

    assert client.get("/aprender").status_code == 404
    asset = client.get("/assets/index-abc123.js")
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == IMMUTABLE


def test_sin_dist_la_api_inexistente_sigue_en_404_json(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    response = client.get("/api/ruta-que-no-existe")
    _assert_json_not_found(response.status_code, response.json())


# --- Métodos y seguridad ---------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/aprender", "/", "/assets/index-abc123.js"])
def test_post_a_la_spa_da_405(client: TestClient, path: str) -> None:
    response = client.post(path)

    assert response.status_code == 405
    assert "Alas de Señas" not in response.text


def test_head_a_una_ruta_de_la_spa_responde_200(client: TestClient) -> None:
    response = client.head("/aprender")

    assert response.status_code == 200
    assert response.headers["cache-control"] == NO_CACHE


@pytest.mark.parametrize(
    "path",
    [
        "/..%2Fsecreto.txt",
        "/%2E%2E/secreto.txt",
        "/%2E%2E%2Fsecreto.txt",
        "/assets/..%2F..%2Fsecreto.txt",
        "/models/..%2F..%2Fsecreto.txt",
        "/aprender/..%2F..%2F..%2Fsecreto.txt",
    ],
)
def test_path_traversal_no_sirve_archivos_fuera_de_dist(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code in (200, 404)
    assert SECRET_TEXT not in response.text
    if response.status_code == 200:
        _assert_is_index(response.text)


@pytest.mark.parametrize(
    "path",
    [
        "/x/..%2Fmedia%2Fmanifest.json",
        "/x/..%2Fmedia/manifest.json",
        "/%2Fmedia/manifest.json",
        "/MEDIA/manifest.json",
        "/Media/manifest.json",
        "/aprender/..%2F..%2Fmedia%2Fmanifest.json",
    ],
)
def test_el_manifiesto_dentro_de_dist_nunca_se_publica_por_la_spa(
    client: TestClient, path: str
) -> None:
    """B54: rutas normalizadas o con mayúsculas no deben saltarse el bloqueo de /media."""
    response = client.get(path)

    assert "MANIFIESTO-SECRETO" not in response.text
    _assert_json_not_found(response.status_code, response.json())


@pytest.mark.parametrize("path", ["/API/x", "/Api", "/ASSETS/nope.js", "/Models/x.json"])
def test_las_carpetas_reservadas_no_distinguen_mayusculas(client: TestClient, path: str) -> None:
    """En Windows el disco no distingue mayúsculas: /ASSETS es la misma carpeta que /assets."""
    response = client.get(path)

    _assert_json_not_found(response.status_code, response.json())
