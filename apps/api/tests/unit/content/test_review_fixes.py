"""Revisión del Grupo 2: validaciones y protecciones agregadas."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.content.media import MANIFEST_NAME, ManifestEntry
from app.content.placeholders import generate_placeholders
from app.content.validation import check_content
from app.core.config import Settings, get_settings
from tests.unit.content.real_content import copy_content, entry_for, make_media

# ---------- Configuración del administrador (§11) ----------------------------------------------


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ("APP_ENV", "ADMIN_EMAIL", "ADMIN_PASSWORD", "JWT_SECRET", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize(
    ("email", "password"),
    [("admin@alasdesenas.co", None), (None, "Clave-Segura-1")],
)
def test_admin_requiere_correo_y_contrasena_juntos(email: str | None, password: str | None) -> None:
    with pytest.raises(ValidationError, match="ADMIN_EMAIL y ADMIN_PASSWORD"):
        Settings(_env_file=None, admin_email=email, admin_password=password)


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize("password", ["corta", "ñ" * 37])  # 5 bytes · 74 bytes UTF-8
def test_contrasena_del_admin_entre_8_y_72_bytes(password: str) -> None:
    with pytest.raises(ValidationError, match="ADMIN_PASSWORD"):
        Settings(_env_file=None, admin_email="admin@alasdesenas.co", admin_password=password)


@pytest.mark.usefixtures("clean_env")
def test_admin_valido_y_sin_admin_son_validos() -> None:
    assert Settings(_env_file=None).admin_email is None
    settings = Settings(_env_file=None, admin_email="admin@alasdesenas.co", admin_password="ñ" * 36)
    assert settings.admin_password == "ñ" * 36


# ---------- Manifiesto ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("video", "poster"),
    [
        ("/etc/passwd", "/media/p/0123456789abcdef.jpg"),
        ("/media/v/../../x.mp4", "/media/p/0123456789abcdef.jpg"),
        ("/media/v/0123456789abcdef.mp4", "C:/Windows/x.jpg"),
    ],
)
def test_rutas_del_manifiesto_solo_dentro_de_media(video: str, poster: str) -> None:
    with pytest.raises(ValidationError):
        ManifestEntry(
            video=video, poster=poster, placeholder=True, source="placeholder", duration=3
        )


def test_sin_manifiesto_no_borra_los_videos_existentes(tmp_path: Path) -> None:
    """Si `manifest.json` falta (borrado por error), los archivos de v/ y p/ no se borran."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "signs.csv").write_text(
        "slug,word,meaning,how_to,usage_example,category,node,order,motion\n"
        "hola,Hola,Saludo.,,«Hola».,saludos,M1-N1,1,\n",
        encoding="utf-8",
    )
    fonts = content_dir / "fonts"
    fonts.mkdir()
    repo_font = Path(__file__).resolve().parents[5] / "content" / "fonts" / "nunito-latin.woff2"
    (fonts / "nunito-latin.woff2").write_bytes(repo_font.read_bytes())
    media_dir = tmp_path / "media"
    (media_dir / "v").mkdir(parents=True)
    precious = media_dir / "v" / "aaaaaaaaaaaaaaaa.mp4"
    precious.write_bytes(b"video real sin commit")

    generate_placeholders(content_dir, media_dir)

    assert precious.is_file()
    assert (media_dir / MANIFEST_NAME).is_file()


# ---------- Validación (§6.3, §6.5) -----------------------------------------------------------


def test_conversaciones_de_un_nodo_inexistente_es_error(tmp_path: Path) -> None:
    content_dir = copy_content(tmp_path / "content")
    path = content_dir / "conversations.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("M2-N4:", "M2-N9:"), encoding="utf-8")
    media_dir = tmp_path / "media"
    make_media(media_dir, content_dir)
    report = check_content(content_dir, media_dir, skip_raw=True)
    assert any("M2-N9" in e and "no existe" in e for e in report.errors), report.errors


def test_intro_con_slug_inexistente_es_error(tmp_path: Path) -> None:
    content_dir = copy_content(tmp_path / "content")
    path = content_dir / "intro.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["cards"][0] = "holaa"
    data["quiz"][0]["sign"] = "gracia"
    path.write_text(json.dumps(data), encoding="utf-8")
    media_dir = tmp_path / "media"
    make_media(media_dir, content_dir)
    report = check_content(content_dir, media_dir, skip_raw=True)
    assert any("intro.json" in e and "holaa" in e for e in report.errors), report.errors
    assert any("intro.json" in e and "gracia" in e for e in report.errors), report.errors


# ---------- Plan B de imágenes (§6.4.1) y YAML (D-009.1) --------------------------------------


def test_foto_de_menos_de_480_px_es_advertencia(tmp_path: Path) -> None:
    from PIL import Image

    content_dir = copy_content(tmp_path / "content")
    raw = content_dir / "videos" / "raw"
    raw.mkdir(parents=True)
    Image.new("RGB", (640, 360), "#336699").save(raw / "hola.jpg")
    media_dir = tmp_path / "media"
    make_media(media_dir, content_dir)
    report = check_content(content_dir, media_dir, skip_raw=False)
    assert report.errors == []
    assert any("hola.jpg" in w and "480" in w for w in report.warnings), report.warnings


def test_imagenes_sin_how_to_dan_advertencia_destacada(tmp_path: Path) -> None:
    content_dir = copy_content(tmp_path / "content")
    media_dir = tmp_path / "media"
    images = entry_for("hola").model_copy(update={"source": "images", "frames": 2})
    make_media(media_dir, content_dir, overrides={"hola": images})
    report = check_content(content_dir, media_dir, skip_raw=True)
    highlighted = [w for w in report.warnings if w.startswith("IMPORTANTE") and "hola" in w]
    assert len(highlighted) == 1, report.warnings
    assert "⚠ IMPORTANTE" in report.render()
    assert "⚠ ⚠" not in report.render()


def test_la_sena_no_sin_comillas_se_lee_como_texto(tmp_path: Path) -> None:
    from app.content.loader import load_conversations

    path = tmp_path / "conversations.yaml"
    path.write_text(
        "M1-N2:\n  - turns:\n      - prompt: tu\n        answer: si\n"
        "        distractors: [no, yes, on, off]\n",
        encoding="utf-8",
    )
    turn = load_conversations(path)["M1-N2"].conversations[0].turns[0]
    assert turn.answer == "si"
    assert turn.distractors == ("no", "yes", "on", "off")
