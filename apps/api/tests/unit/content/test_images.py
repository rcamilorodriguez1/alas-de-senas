"""Tarea 2.6b — plan B de imágenes (§6.4.1, D25, B91 a B94).Imágenes generadas en la prueba."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.content.images import (
    BACKGROUND,
    CANVAS,
    FADE_SECONDS,
    FRAME_SECONDS,
    MIN_HEIGHT,
    SINGLE_SECONDS,
    build_frames,
    image_height,
    images_to_video,
    prepare_image,
)
from tests.unit.content.media_tools import assert_web_video, solid_image

RGB = tuple[int, int, int]
RED: RGB = (220, 30, 30)
GREEN: RGB = (30, 200, 30)
BLUE: RGB = (30, 30, 220)
YELLOW: RGB = (230, 220, 30)
BACKGROUND_RGB: RGB = (0xF5, 0xFA, 0xF7)
ORIENTATION_TAG = 0x0112


def _pixel(image: Image.Image, xy: tuple[int, int]) -> RGB:
    value = image.getpixel(xy)
    assert isinstance(value, tuple)
    r, g, b = value[0], value[1], value[2]
    assert isinstance(r, int)
    assert isinstance(g, int)
    assert isinstance(b, int)
    return (r, g, b)


def _close(actual: RGB, expected: RGB, tolerance: int = 40) -> bool:
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected, strict=True))


def _quadrants(size: tuple[int, int]) -> Image.Image:
    """Arriba-izq rojo, arriba-der verde, abajo-izq azul, abajo-der amarillo."""
    width, height = size
    image = Image.new("RGB", size, RED)
    image.paste(GREEN, (width // 2, 0, width, height // 2))
    image.paste(BLUE, (0, height // 2, width // 2, height))
    image.paste(YELLOW, (width // 2, height // 2, width, height))
    return image


def _save_with_orientation(image: Image.Image, path: Path, orientation: int) -> Path:
    exif = Image.Exif()
    exif[ORIENTATION_TAG] = orientation
    image.save(path, "JPEG", quality=95, exif=exif.tobytes())
    return path


# ---------- constantes ----------


def test_constantes_del_plan_b() -> None:
    assert CANVAS == (1280, 720)
    assert BACKGROUND.upper() == "#F5FAF7"
    assert SINGLE_SECONDS == 3.0
    assert FRAME_SECONDS == 1.2
    assert FADE_SECONDS == 0.4
    assert MIN_HEIGHT == 480


# ---------- prepare_image ----------


def test_foto_con_exif_de_rotacion_sale_derecha_b91(tmp_path: Path) -> None:
    # Guardada horizontal 1440x1080 con Orientation=6 (girar 90° a la derecha para mostrarla):
    # se ve vertical 1080x1440 y su esquina superior derecha es la superior izquierda guardada.
    path = _save_with_orientation(_quadrants((1440, 1080)), tmp_path / "celular.jpg", 6)

    prepared = prepare_image(path)

    assert prepared.size == (1280, 720)
    # Vertical reducida a 540x720 y centrada: ocupa x de 370 a 910.
    assert _close(_pixel(prepared, (775, 180)), RED)  # arriba a la derecha
    assert _close(_pixel(prepared, (505, 180)), BLUE)  # arriba a la izquierda
    assert _close(_pixel(prepared, (775, 540)), GREEN)  # abajo a la derecha
    assert _close(_pixel(prepared, (505, 540)), YELLOW)  # abajo a la izquierda
    assert _close(_pixel(prepared, (100, 360)), BACKGROUND_RGB, tolerance=3)  # franja lateral


def test_foto_sin_rotacion_conserva_la_orientacion(tmp_path: Path) -> None:
    path = tmp_path / "normal.jpg"
    _quadrants((1280, 720)).save(path, quality=95)

    prepared = prepare_image(path)

    assert _close(_pixel(prepared, (320, 180)), RED)
    assert _close(_pixel(prepared, (960, 180)), GREEN)
    assert _close(_pixel(prepared, (320, 540)), BLUE)
    assert _close(_pixel(prepared, (960, 540)), YELLOW)


def test_foto_de_12_mp_se_reduce_sin_error_b92(tmp_path: Path) -> None:
    path = solid_image(tmp_path / "grande.jpg", (4000, 3000), RED)

    prepared = prepare_image(path)

    assert prepared.size == (1280, 720)
    assert prepared.mode == "RGB"
    assert _close(_pixel(prepared, (640, 360)), RED)
    # 4:3 reducida a 960x720 y centrada: franjas laterales con el fondo.
    assert _close(_pixel(prepared, (50, 360)), BACKGROUND_RGB, tolerance=3)
    assert _close(_pixel(prepared, (1230, 360)), BACKGROUND_RGB, tolerance=3)


def test_medidas_impares_dan_lienzo_de_1280x720_b93(tmp_path: Path) -> None:
    path = solid_image(tmp_path / "impar.jpg", (1001, 777), GREEN)

    prepared = prepare_image(path)

    assert prepared.size == (1280, 720)
    assert prepared.mode == "RGB"


@pytest.mark.parametrize(
    ("mode", "color", "suffix"),
    [
        ("RGBA", (10, 20, 30, 128), ".png"),
        ("L", 128, ".png"),
        ("P", 3, ".png"),
        ("RGB", (1, 2, 3), ".webp"),
    ],
)
def test_prepare_image_siempre_devuelve_rgb_1280x720(
    tmp_path: Path, mode: str, color: int | tuple[int, ...], suffix: str
) -> None:
    path = tmp_path / f"imagen{suffix}"
    Image.new(mode, (640, 480), color).save(path)

    prepared = prepare_image(path)

    assert prepared.mode == "RGB"
    assert prepared.size == (1280, 720)


def test_imagen_pequena_queda_centrada_sobre_el_fondo(tmp_path: Path) -> None:
    path = solid_image(tmp_path / "pequena.png", (200, 100), BLUE)

    prepared = prepare_image(path)

    assert prepared.size == (1280, 720)
    assert _close(_pixel(prepared, (640, 360)), BLUE, tolerance=3)
    assert _close(_pixel(prepared, (5, 5)), BACKGROUND_RGB, tolerance=3)
    assert _close(_pixel(prepared, (1274, 714)), BACKGROUND_RGB, tolerance=3)


# ---------- image_height ----------


def test_image_height_sin_rotacion(tmp_path: Path) -> None:
    assert image_height(solid_image(tmp_path / "a.jpg", (640, 400))) == 400


def test_image_height_aplica_la_rotacion_exif(tmp_path: Path) -> None:
    path = _save_with_orientation(Image.new("RGB", (640, 360), RED), tmp_path / "r.jpg", 6)

    assert image_height(path) == 640


def test_image_height_detecta_fotos_bajas(tmp_path: Path) -> None:
    low = solid_image(tmp_path / "baja.jpg", (800, 479))

    assert image_height(low) < MIN_HEIGHT


# ---------- build_frames ----------


def _canvas(color: RGB) -> Image.Image:
    return Image.new("RGB", CANVAS, color)


def test_una_imagen_son_3_segundos_fijos() -> None:
    image = _canvas(RED)

    frames = build_frames([image], fps=30)

    assert len(frames) == 90
    assert all(frame.size == CANVAS for frame in frames)
    assert _pixel(frames[0], (640, 360)) == RED
    assert _pixel(frames[45], (640, 360)) == RED
    assert _pixel(frames[-1], (640, 360)) == RED


def test_tres_imagenes_son_3_por_36_cuadros() -> None:
    frames = build_frames([_canvas(RED), _canvas(GREEN), _canvas(BLUE)], fps=30)

    assert len(frames) == 3 * 36
    assert all(frame.size == CANVAS and frame.mode == "RGB" for frame in frames)


def test_dos_imagenes_son_2_por_36_cuadros() -> None:
    assert len(build_frames([_canvas(RED), _canvas(BLUE)], fps=30)) == 72


def test_cantidad_de_cuadros_redondea_hacia_arriba_en_otro_fps() -> None:
    # 1,2 · 24 = 28,8 → 29 por imagen; 3 · 24 = 72 para una sola.
    assert len(build_frames([_canvas(RED), _canvas(BLUE)], fps=24)) == 58
    assert len(build_frames([_canvas(RED)], fps=24)) == 72


def test_fundido_mezcla_los_colores_hacia_la_siguiente() -> None:
    frames = build_frames([_canvas(RED), _canvas(BLUE)], fps=30)

    assert _pixel(frames[0], (640, 360)) == RED
    assert _pixel(frames[10], (640, 360)) == RED  # 0,33 s: antes del fundido
    assert _pixel(frames[-1], (640, 360)) == BLUE  # la última imagen termina limpia
    first_segment = frames[:36]
    mixed = [
        _pixel(frame, (640, 360))
        for frame in first_segment
        if _pixel(frame, (640, 360)) not in (RED, BLUE)
    ]
    assert mixed, "debe haber cuadros intermedios con mezcla de ambos colores"
    assert any(r > BLUE[0] + 20 and b > RED[2] + 20 for r, _, b in mixed)


def test_el_fundido_dura_0_4_segundos_dentro_de_la_imagen() -> None:
    frames = build_frames([_canvas(RED), _canvas(BLUE)], fps=30)

    first_segment = frames[:36]
    blended = [f for f in first_segment if _pixel(f, (640, 360)) != RED]
    # 0,4 s a 30 fps = 12 cuadros de transición (con margen de uno por el redondeo).
    assert 11 <= len(blended) <= 13
    # Los primeros 0,8 s de la primera imagen no se tocan.
    assert all(_pixel(f, (640, 360)) == RED for f in first_segment[:23])


# ---------- images_to_video ----------


def test_images_to_video_una_imagen_numero_1(tmp_path: Path) -> None:
    source = solid_image(tmp_path / "numero-1.jpg", (800, 600), GREEN)
    video = tmp_path / "salida.mp4"
    poster = tmp_path / "poster.jpg"

    used = images_to_video([source], video, poster)

    assert used == 1
    info = assert_web_video(video, height=720)
    assert info.width == 1280
    assert info.duration == pytest.approx(3.0, abs=0.15)
    with Image.open(poster) as image:
        assert image.format == "JPEG"
        assert image.size == (1280, 720)
        assert _close(_pixel(image.convert("RGB"), (640, 360)), GREEN)


def test_images_to_video_secuencia_de_dos(tmp_path: Path) -> None:
    first = solid_image(tmp_path / "gracias__1.jpg", (640, 480), RED)
    second = solid_image(tmp_path / "gracias__2.jpg", (640, 480), BLUE)
    video = tmp_path / "salida.mp4"
    poster = tmp_path / "poster.jpg"

    used = images_to_video([first, second], video, poster)

    assert used == 2
    info = assert_web_video(video, height=720)
    assert info.duration == pytest.approx(2.4, abs=0.15)
    with Image.open(poster) as image:  # póster = primera imagen preparada
        assert _close(_pixel(image.convert("RGB"), (640, 360)), RED)


def test_images_to_video_con_foto_rotada_e_impar(tmp_path: Path) -> None:
    source = _save_with_orientation(_quadrants((1001, 777)), tmp_path / "letra-a.jpg", 6)
    video = tmp_path / "salida.mp4"
    poster = tmp_path / "poster.jpg"

    assert images_to_video([source], video, poster) == 1

    assert_web_video(video, height=720)
