"""Tarea 2.5 — videos de relleno (D6, D19, §6.4, R9.2). Nunca reemplazan un video real."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.content.media import MANIFEST_NAME, Manifest, ManifestEntry, load_manifest, save_manifest
from app.content.placeholders import (
    BACKGROUND,
    FONT_FILE,
    FOREGROUND,
    LABEL,
    SECONDS,
    SIZE,
    generate_placeholders,
    render_frame,
)
from tests.unit.content.media_tools import (
    assert_web_video,
    media_files,
    url_to_path,
    write_signs_csv,
)

REPO_CONTENT = Path(__file__).resolve().parents[5] / "content"
FONT = REPO_CONTENT / FONT_FILE
BACKGROUND_RGB = (0x0E, 0x2A, 0x2F)
SIGNS = [("hola", "Hola"), ("gracias", "Gracias"), ("banarse", "Bañarse")]


def _pixels(image: Image.Image, box: tuple[int, int, int, int]) -> list[tuple[int, int, int]]:
    region = image.crop(box).convert("RGB")
    width, height = region.size
    result: list[tuple[int, int, int]] = []
    for y in range(height):
        for x in range(width):
            value = region.getpixel((x, y))
            assert isinstance(value, tuple)
            r, g, b = value[0], value[1], value[2]
            assert isinstance(r, int)
            assert isinstance(g, int)
            assert isinstance(b, int)
            result.append((r, g, b))
    return result


def _is_white(pixel: tuple[int, int, int]) -> bool:
    return all(channel >= 235 for channel in pixel)


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    """Copia mínima de content/: signs.csv con 3 señas y la fuente incluida."""
    directory = tmp_path / "content"
    (directory / "fonts").mkdir(parents=True)
    shutil.copyfile(FONT, directory / FONT_FILE)
    write_signs_csv(directory, SIGNS)
    return directory


@pytest.fixture
def media_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "media"
    directory.mkdir()
    return directory


# ---------- constantes ----------


def test_constantes_del_relleno() -> None:
    assert BACKGROUND.upper() == "#0E2A2F"
    assert FOREGROUND.upper() == "#FFFFFF"
    assert LABEL == "Video en preparación"
    assert SECONDS == 3.0
    assert SIZE == (1280, 720)
    assert FONT.is_file()


# ---------- render_frame ----------


def test_render_frame_tiene_1280x720_y_fondo_oscuro() -> None:
    frame = render_frame("Hola", FONT)

    assert frame.size == (1280, 720)
    assert frame.convert("RGB").getpixel((5, 5)) == BACKGROUND_RGB
    assert frame.convert("RGB").getpixel((1274, 714)) == BACKGROUND_RGB


def test_render_frame_dibuja_la_palabra_en_blanco_en_el_centro() -> None:
    frame = render_frame("Hola", FONT)

    center = _pixels(frame, (440, 200, 840, 420))
    assert any(_is_white(p) for p in center)


def test_render_frame_dibuja_la_etiqueta_debajo_de_la_palabra() -> None:
    with_label = render_frame("Hola", FONT)

    lower = _pixels(with_label, (0, 430, 1280, 720))
    assert any(p != BACKGROUND_RGB for p in lower), "falta «Video en preparación» debajo"


def test_render_frame_palabras_distintas_dan_imagenes_distintas() -> None:
    assert render_frame("Hola", FONT).tobytes() != render_frame("Gracias", FONT).tobytes()


def test_render_frame_palabra_larga_cabe_en_el_ancho() -> None:
    frame = render_frame("Otorrinolaringólogo electroencefalografista", FONT)

    assert frame.size == (1280, 720)
    left_edge = _pixels(frame, (0, 0, 8, 720))
    right_edge = _pixels(frame, (1272, 0, 1280, 720))
    assert all(p == BACKGROUND_RGB for p in left_edge)
    assert all(p == BACKGROUND_RGB for p in right_edge)
    assert any(_is_white(p) for p in _pixels(frame, (0, 200, 1280, 420)))


@pytest.mark.parametrize("word", ["Bañarse", "¿Cómo estás?", "Pájaro", "Ñ", "Médico"])
def test_render_frame_admite_n_tilde_y_tildes(word: str) -> None:
    frame = render_frame(word, FONT)

    assert frame.size == (1280, 720)
    assert any(_is_white(p) for p in _pixels(frame, (0, 200, 1280, 420)))


def test_render_frame_la_tilde_se_dibuja() -> None:
    # Si la fuente no tuviera la «ñ», saldría igual (o un cuadro vacío) que la «n».
    assert render_frame("Bañarse", FONT).tobytes() != render_frame("Banarse", FONT).tobytes()


# ---------- generate_placeholders ----------


def test_genera_un_relleno_por_sena_r9_2(content_dir: Path, media_dir: Path) -> None:
    result = generate_placeholders(content_dir, media_dir)

    assert sorted(result.created) == ["banarse", "gracias", "hola"]
    assert result.kept == []
    manifest = load_manifest(media_dir)
    assert set(manifest.signs) == {"hola", "gracias", "banarse"}
    for entry in manifest.signs.values():
        assert entry.placeholder is True
        assert entry.source == "placeholder"
        assert entry.frames is None
        assert entry.source_hash is None
        assert entry.duration == pytest.approx(3.0, abs=0.2)
        assert entry.video.startswith("/media/v/")
        assert entry.video.endswith(".mp4")
        assert entry.poster.startswith("/media/p/")
        assert entry.poster.endswith(".jpg")
        assert url_to_path(media_dir, entry.video).is_file()
        assert url_to_path(media_dir, entry.poster).is_file()


def test_el_relleno_tiene_el_formato_de_los_videos(content_dir: Path, media_dir: Path) -> None:
    generate_placeholders(content_dir, media_dir)

    entry = load_manifest(media_dir).signs["hola"]
    info = assert_web_video(url_to_path(media_dir, entry.video), height=720)
    assert info.width == 1280
    assert info.duration == pytest.approx(3.0, abs=0.15)
    with Image.open(url_to_path(media_dir, entry.poster)) as poster:
        assert poster.format == "JPEG"
        assert poster.size == (1280, 720)


def test_cada_palabra_tiene_su_propia_ruta(content_dir: Path, media_dir: Path) -> None:
    generate_placeholders(content_dir, media_dir)

    manifest = load_manifest(media_dir)
    videos = {entry.video for entry in manifest.signs.values()}
    assert len(videos) == 3
    assert all("hola" not in v and "gracias" not in v for v in videos)


def test_no_toca_una_sena_con_video_real(content_dir: Path, media_dir: Path) -> None:
    real_video = media_dir / "v" / "aaaaaaaaaaaaaaaa.mp4"
    real_poster = media_dir / "p" / "aaaaaaaaaaaaaaaa.jpg"
    real_video.parent.mkdir()
    real_poster.parent.mkdir()
    real_video.write_bytes(b"video real de hola")
    real_poster.write_bytes(b"poster real de hola")
    real_entry = ManifestEntry(
        video="/media/v/aaaaaaaaaaaaaaaa.mp4",
        poster="/media/p/aaaaaaaaaaaaaaaa.jpg",
        placeholder=False,
        source="video",
        duration=2.5,
        source_hash="c" * 64,
    )
    save_manifest(media_dir, Manifest(signs={"hola": real_entry}))

    result = generate_placeholders(content_dir, media_dir)

    assert "hola" not in result.created
    assert "hola" in result.kept
    assert sorted(result.created) == ["banarse", "gracias"]
    assert load_manifest(media_dir).signs["hola"] == real_entry
    assert real_video.read_bytes() == b"video real de hola"
    assert real_poster.read_bytes() == b"poster real de hola"


def test_respeta_raw_slugs(content_dir: Path, media_dir: Path) -> None:
    result = generate_placeholders(content_dir, media_dir, raw_slugs={"gracias"})

    assert "gracias" not in result.created
    assert sorted(result.created) == ["banarse", "hola"]
    assert "gracias" not in load_manifest(media_dir).signs


def test_repetir_no_cambia_el_manifiesto_ni_crea_archivos(
    content_dir: Path, media_dir: Path
) -> None:
    generate_placeholders(content_dir, media_dir)
    manifest_bytes = (media_dir / MANIFEST_NAME).read_bytes()
    files = media_files(media_dir)
    mtimes = {path: path.stat().st_mtime_ns for path in files}

    second = generate_placeholders(content_dir, media_dir)

    assert second.created == []
    assert sorted(second.kept) == ["banarse", "gracias", "hola"]
    assert (media_dir / MANIFEST_NAME).read_bytes() == manifest_bytes
    assert media_files(media_dir) == files
    assert {path: path.stat().st_mtime_ns for path in files} == mtimes


def test_cambiar_la_palabra_cambia_la_ruta_y_borra_el_viejo(
    content_dir: Path, media_dir: Path
) -> None:
    generate_placeholders(content_dir, media_dir)
    old = load_manifest(media_dir).signs["hola"]
    untouched = load_manifest(media_dir).signs["gracias"]

    write_signs_csv(
        content_dir, [("hola", "¡Hola!"), ("gracias", "Gracias"), ("banarse", "Bañarse")]
    )
    result = generate_placeholders(content_dir, media_dir)

    new = load_manifest(media_dir).signs["hola"]
    assert result.created == ["hola"]
    assert new.video != old.video
    assert new.poster != old.poster
    assert url_to_path(media_dir, new.video).is_file()
    assert not url_to_path(media_dir, old.video).exists()
    assert not url_to_path(media_dir, old.poster).exists()
    assert load_manifest(media_dir).signs["gracias"] == untouched
