"""Foto de perfil (D-023): subir, ver y quitar; se valida y se re-codifica sin metadatos."""

from __future__ import annotations

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.rate_limit import reset_rate_limits
from tests.api.helpers import auth, register_user

URL = "/api/me/avatar"


@pytest.fixture(autouse=True)
def _limits() -> None:
    reset_rate_limits()


def encoded_image(fmt: str = "PNG", size: tuple[int, int] = (640, 480), gps: bool = False) -> str:
    image = Image.new("RGB", size, (16, 185, 129))
    out = io.BytesIO()
    if gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (4.0, 36.0, 0.0)}  # GPSInfo: ubicación en Bogotá
        exif[0x010F] = "MarcaDelCelular"  # Make
        image.save(out, format="JPEG", exif=exif)
    else:
        image.save(out, format=fmt)
    return base64.b64encode(out.getvalue()).decode()


def test_sin_foto_avatar_updated_at_es_null_y_get_da_404(client: TestClient) -> None:
    token, _ = register_user(client)
    me = client.get("/api/me", headers=auth(token)).json()
    assert me["avatarUpdatedAt"] is None
    response = client.get(URL, headers=auth(token))
    assert response.status_code == 404
    assert response.json()["code"] == "AVATAR_NOT_FOUND"


def test_subir_foto_la_guarda_como_webp_de_256(client: TestClient) -> None:
    token, _ = register_user(client)
    response = client.put(URL, json={"image": encoded_image()}, headers=auth(token))
    assert response.status_code == 200
    assert response.json()["avatarUpdatedAt"] is not None

    photo = client.get(URL, headers=auth(token))
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/webp"
    assert "no-store" in photo.headers["cache-control"]
    with Image.open(io.BytesIO(photo.content)) as stored:
        assert stored.format == "WEBP"
        assert stored.size == (256, 256)


def test_la_foto_se_guarda_sin_metadatos_ni_ubicacion(client: TestClient) -> None:
    token, _ = register_user(client)
    client.put(URL, json={"image": encoded_image(gps=True)}, headers=auth(token))
    stored = client.get(URL, headers=auth(token)).content
    assert b"MarcaDelCelular" not in stored
    with Image.open(io.BytesIO(stored)) as image:
        assert not image.getexif()


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_acepta_jpg_png_y_webp(client: TestClient, fmt: str) -> None:
    token, _ = register_user(client)
    response = client.put(URL, json={"image": encoded_image(fmt)}, headers=auth(token))
    assert response.status_code == 200


@pytest.mark.parametrize(
    "image",
    [
        "esto no es base64!!",
        base64.b64encode(b"<svg onload=alert(1)></svg>").decode(),
        base64.b64encode(b"GIF89a" + b"\x00" * 50).decode(),
    ],
)
def test_rechaza_lo_que_no_es_una_imagen_permitida(client: TestClient, image: str) -> None:
    token, _ = register_user(client)
    response = client.put(URL, json={"image": image}, headers=auth(token))
    assert response.status_code == 422
    assert response.json()["code"] in {"INVALID_IMAGE", "VALIDATION_ERROR"}
    assert client.get("/api/me", headers=auth(token)).json()["avatarUpdatedAt"] is None


def test_rechaza_imagenes_demasiado_pesadas(client: TestClient) -> None:
    token, _ = register_user(client)
    noisy = Image.effect_noise((900, 900), 100).convert("RGB")
    out = io.BytesIO()
    noisy.save(out, format="PNG")
    response = client.put(
        URL, json={"image": base64.b64encode(out.getvalue()).decode()}, headers=auth(token)
    )
    assert response.status_code == 422


def test_quitar_foto(client: TestClient) -> None:
    token, _ = register_user(client)
    client.put(URL, json={"image": encoded_image()}, headers=auth(token))
    response = client.delete(URL, headers=auth(token))
    assert response.status_code == 200
    assert response.json()["avatarUpdatedAt"] is None
    assert client.get(URL, headers=auth(token)).status_code == 404


def test_cada_usuario_ve_solo_su_foto(client: TestClient) -> None:
    ana, _ = register_user(client, "ana@ejemplo.com")
    beto, _ = register_user(client, "beto@ejemplo.com")
    client.put(URL, json={"image": encoded_image()}, headers=auth(ana))
    assert client.get(URL, headers=auth(beto)).status_code == 404


def test_requiere_sesion(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={"image": encoded_image()}).status_code == 401
    assert client.delete(URL).status_code == 401


def test_la_exportacion_indica_si_hay_foto(client: TestClient) -> None:
    token, _ = register_user(client)
    assert client.get("/api/me/export", headers=auth(token)).json()["profile"]["hasAvatar"] is False
    client.put(URL, json={"image": encoded_image()}, headers=auth(token))
    assert client.get("/api/me/export", headers=auth(token)).json()["profile"]["hasAvatar"] is True
