"""Tarea 5.3 (servidor): `/media` con `Range` (B35) y caché inmutable (§11, D19).

Los archivos se llaman por el hash de su contenido (D19), así que se pueden guardar en caché para
siempre. `manifest.json` relaciona slug y video (D-009): nunca se publica, porque permitiría
deducir la respuesta de un ejercicio a partir de la ruta de su video (B54).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

VIDEO = "v/0123456789abcdef.mp4"
POSTER = "p/0123456789abcdef.jpg"
VIDEO_BYTES = bytes(range(256)) * 7 + bytes(208)  # 2000 bytes
POSTER_BYTES = b"\xff\xd8\xff\xe0" + bytes(300)
IMMUTABLE = "public, max-age=31536000, immutable"


@pytest.fixture
def media_dir(tmp_path: Path) -> Path:
    root = tmp_path / "media"
    (root / "v").mkdir(parents=True)
    (root / "p").mkdir()
    (root / VIDEO).write_bytes(VIDEO_BYTES)
    (root / POSTER).write_bytes(POSTER_BYTES)
    (root / "manifest.json").write_text('{"hola": {"video": "/media/' + VIDEO + '"}}', "utf-8")
    return root


@pytest.fixture
def media_client(media_dir: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(media_dir=media_dir))) as test_client:
        yield test_client


def test_video_completo_200_con_cache_inmutable(media_client: TestClient) -> None:
    assert len(VIDEO_BYTES) == 2000
    response = media_client.get(f"/media/{VIDEO}")
    assert response.status_code == 200
    assert response.content == VIDEO_BYTES
    assert response.headers["cache-control"] == IMMUTABLE
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-type"].startswith("video/mp4")


def test_video_con_range_responde_206_parcial(media_client: TestClient) -> None:
    """B35: sin `Range` no se puede adelantar ni repetir bien el video."""
    response = media_client.get(f"/media/{VIDEO}", headers={"Range": "bytes=0-99"})
    assert response.status_code == 206
    assert len(response.content) == 100
    assert response.content == VIDEO_BYTES[:100]
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == "bytes 0-99/2000"


def test_range_intermedio_devuelve_los_bytes_pedidos(media_client: TestClient) -> None:
    response = media_client.get(f"/media/{VIDEO}", headers={"Range": "bytes=1000-1499"})
    assert response.status_code == 206
    assert response.content == VIDEO_BYTES[1000:1500]
    assert response.headers["content-range"] == "bytes 1000-1499/2000"


def test_poster_con_cache_inmutable(media_client: TestClient) -> None:
    response = media_client.get(f"/media/{POSTER}")
    assert response.status_code == 200
    assert response.content == POSTER_BYTES
    assert response.headers["cache-control"] == IMMUTABLE
    assert response.headers["content-type"].startswith("image/jpeg")


def test_manifest_no_se_publica(media_client: TestClient) -> None:
    """B54, D-009: el manifiesto relaciona slug y video; existe en disco pero no se sirve."""
    response = media_client.get("/media/manifest.json")
    assert response.status_code == 404
    assert b"hola" not in response.content


@pytest.mark.parametrize(
    "path",
    [
        "/media/v/ffffffffffffffff.mp4",
        "/media/p/ffffffffffffffff.jpg",
        "/media/v/no-existe.mp4",
        "/media/v/../manifest.json",
    ],
)
def test_ruta_inexistente_o_fuera_de_media_404(media_client: TestClient, path: str) -> None:
    response = media_client.get(path)
    assert response.status_code == 404
