"""Tarea 2.6 — llamadas a ffmpeg (§6.4, D7): normalización, póster, duración y cuadros → MP4."""

from __future__ import annotations

from pathlib import Path

import imageio_ffmpeg
import pytest
from PIL import Image

from app.content.ffmpeg import (
    FPS,
    HEIGHT,
    extract_poster,
    ffmpeg_exe,
    frames_to_video,
    normalize_video,
    probe_duration,
)
from tests.unit.content.media_tools import assert_web_video, make_clip, probe


@pytest.fixture(scope="module")
def source_clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Clip de 2 s, 320x240, con audio y yuv444p (lo contrario de lo que se sirve)."""
    path = tmp_path_factory.mktemp("fuente") / "fuente.mp4"
    make_clip(path, seconds=2.0, size="320x240", audio=True)
    info = probe(path)
    assert info.has_audio  # la fuente sí trae audio: la normalización debe quitarlo
    assert info.pix_fmt == "yuv444p"
    return path


@pytest.fixture(scope="module")
def normalized_clip(source_clip: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("normalizado") / "salida.mp4"
    normalize_video(source_clip, target)
    return target


def test_ffmpeg_exe_es_el_de_imageio_ffmpeg() -> None:
    exe = ffmpeg_exe()

    assert exe == imageio_ffmpeg.get_ffmpeg_exe()
    assert Path(exe).is_file()


def test_constantes_del_formato() -> None:
    assert FPS == 30
    assert HEIGHT == 720


def test_normalize_video_produce_h264_yuv420p_720p_sin_audio(normalized_clip: Path) -> None:
    info = assert_web_video(normalized_clip, height=720)

    assert info.width == 960  # 320x240 escalado a 720 de alto conserva la proporción 4:3


def test_normalize_video_queda_a_30_fps(normalized_clip: Path) -> None:
    assert "30 fps" in probe(normalized_clip).raw


def test_normalize_video_usa_perfil_high(normalized_clip: Path) -> None:
    assert "(High)" in probe(normalized_clip).raw


def test_normalize_video_conserva_la_duracion(normalized_clip: Path) -> None:
    assert probe(normalized_clip).duration == pytest.approx(2.0, abs=0.15)


def test_normalize_video_con_medidas_impares_da_ancho_par(tmp_path: Path) -> None:
    source = make_clip(tmp_path / "impar.mp4", seconds=1.0, size="321x241", audio=False)
    target = tmp_path / "salida.mp4"

    normalize_video(source, target)

    info = assert_web_video(target, height=720)
    assert info.width % 2 == 0


def test_normalize_video_con_nombre_con_espacios_y_tildes(tmp_path: Path) -> None:
    folder = tmp_path / "carpeta con espacios"
    folder.mkdir()
    source = make_clip(folder / "buenos días.mp4", seconds=1.0, audio=False)
    target = folder / "salida ñ.mp4"

    normalize_video(source, target)

    assert_web_video(target)


def test_extract_poster_produce_un_jpg(normalized_clip: Path, tmp_path: Path) -> None:
    poster = tmp_path / "poster.jpg"

    extract_poster(normalized_clip, poster)

    assert poster.is_file()
    with Image.open(poster) as image:
        assert image.format == "JPEG"
        assert image.height == 720


def test_extract_poster_de_video_mas_corto_que_el_segundo_pedido(tmp_path: Path) -> None:
    short = make_clip(tmp_path / "corto.mp4", seconds=0.5, audio=False)
    poster = tmp_path / "poster.jpg"

    extract_poster(short, poster, at_second=1.0)

    assert poster.is_file()
    with Image.open(poster) as image:
        assert image.format == "JPEG"
        assert image.size == (320, 240)


def test_probe_duration_aproxima_la_duracion(source_clip: Path, tmp_path: Path) -> None:
    one_second = make_clip(tmp_path / "uno.mp4", seconds=1.0, audio=False)

    assert probe_duration(source_clip) == pytest.approx(2.0, abs=0.15)
    assert probe_duration(one_second) == pytest.approx(1.0, abs=0.15)


def test_frames_to_video_convierte_pngs_numerados(tmp_path: Path) -> None:
    frames_dir = tmp_path / "cuadros"
    frames_dir.mkdir()
    for index in range(30):
        shade = index * 8
        Image.new("RGB", (320, 240), (shade, 100, 255 - shade)).save(
            frames_dir / f"{index + 1:05d}.png"
        )
    target = tmp_path / "salida.mp4"

    frames_to_video(frames_dir, target)

    info = assert_web_video(target, height=240)
    assert info.width == 320
    assert info.duration == pytest.approx(1.0, abs=0.1)
    assert "30 fps" in info.raw
