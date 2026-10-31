"""Tareas 2.6/2.6b — `alas content videos` (§6.4, §6.4.1, D19, D25, R9.3, R9.4, R9.12, B55, B95)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from app.content.media import MANIFEST_NAME, Manifest, ManifestEntry, load_manifest, save_manifest
from app.content.videos import CACHE_NAME, process_videos, source_hash
from tests.unit.content.media_tools import (
    assert_web_video,
    make_clip,
    media_files,
    solid_image,
    url_to_path,
    write_signs_csv,
)

SIGNS = [("hola", "Hola"), ("gracias", "Gracias"), ("buenos-dias", "Buenos días")]


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "content"
    (directory / "videos" / "raw").mkdir(parents=True)
    write_signs_csv(directory, SIGNS)
    return directory


@pytest.fixture
def raw_dir(content_dir: Path) -> Path:
    return content_dir / "videos" / "raw"


@pytest.fixture
def media_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "media"
    directory.mkdir()
    return directory


@pytest.fixture
def full_raw(raw_dir: Path) -> Path:
    """hola.mp4 (video con audio) + gracias__1.jpg y gracias__2.jpg (plan B)."""
    make_clip(raw_dir / "hola.mp4", seconds=1.0, audio=True)
    solid_image(raw_dir / "gracias__1.jpg", (640, 480), (220, 30, 30))
    solid_image(raw_dir / "gracias__2.jpg", (640, 480), (30, 30, 220))
    return raw_dir


# ---------- source_hash ----------


def test_source_hash_de_un_archivo_es_su_sha256_completo(tmp_path: Path) -> None:
    path = tmp_path / "hola.mp4"
    path.write_bytes(b"original")

    assert source_hash([path]) == hashlib.sha256(b"original").hexdigest()


def test_source_hash_depende_del_contenido_y_del_orden(tmp_path: Path) -> None:
    a = tmp_path / "gracias__1.jpg"
    b = tmp_path / "gracias__2.jpg"
    a.write_bytes(b"inicio")
    b.write_bytes(b"final")

    digest = source_hash([a, b])

    assert len(digest) == 64
    assert digest != source_hash([b, a])
    b.write_bytes(b"final cambiado")
    assert source_hash([a, b]) != digest


# ---------- process_videos ----------


def test_procesa_video_e_imagenes_r9_3_r9_12(
    content_dir: Path, media_dir: Path, full_raw: Path
) -> None:
    result = process_videos(content_dir, media_dir)

    assert result.errors == []
    assert sorted(result.processed) == ["gracias", "hola"]
    assert result.unchanged == []
    manifest = load_manifest(media_dir)
    assert set(manifest.signs) == {"hola", "gracias"}  # no genera rellenos

    hola = manifest.signs["hola"]
    assert hola.placeholder is False
    assert hola.source == "video"
    assert hola.frames is None
    assert hola.duration == pytest.approx(1.0, abs=0.15)
    assert hola.source_hash == source_hash([full_raw / "hola.mp4"])

    gracias = manifest.signs["gracias"]
    assert gracias.placeholder is False
    assert gracias.source == "images"
    assert gracias.frames == 2
    assert gracias.duration == pytest.approx(2.4, abs=0.15)
    assert gracias.source_hash == source_hash(
        [full_raw / "gracias__1.jpg", full_raw / "gracias__2.jpg"]
    )

    for entry in (hola, gracias):
        assert url_to_path(media_dir, entry.video).is_file()
        assert url_to_path(media_dir, entry.poster).is_file()


def test_los_videos_procesados_tienen_el_formato_web(
    content_dir: Path, media_dir: Path, full_raw: Path
) -> None:
    process_videos(content_dir, media_dir)
    manifest = load_manifest(media_dir)

    for slug in ("hola", "gracias"):
        entry = manifest.signs[slug]
        assert_web_video(url_to_path(media_dir, entry.video), height=720)
        with Image.open(url_to_path(media_dir, entry.poster)) as poster:
            assert poster.format == "JPEG"


def test_la_ruta_es_el_hash_del_video_procesado_d19(
    content_dir: Path, media_dir: Path, full_raw: Path
) -> None:
    process_videos(content_dir, media_dir)

    entry = load_manifest(media_dir).signs["hola"]
    video = url_to_path(media_dir, entry.video)
    expected = hashlib.sha256(video.read_bytes()).hexdigest()[:16]
    assert entry.video == f"/media/v/{expected}.mp4"
    assert entry.poster == f"/media/p/{expected}.jpg"


def test_no_modifica_los_originales(content_dir: Path, media_dir: Path, full_raw: Path) -> None:
    before = {p.name: p.read_bytes() for p in full_raw.iterdir()}

    process_videos(content_dir, media_dir)

    assert {p.name: p.read_bytes() for p in full_raw.iterdir()} == before


def test_segunda_ejecucion_usa_la_cache(content_dir: Path, media_dir: Path, full_raw: Path) -> None:
    process_videos(content_dir, media_dir)
    manifest_bytes = (media_dir / MANIFEST_NAME).read_bytes()
    files = media_files(media_dir)
    mtimes = {path: path.stat().st_mtime_ns for path in files}

    second = process_videos(content_dir, media_dir)

    assert second.processed == []
    assert sorted(second.unchanged) == ["gracias", "hola"]
    assert second.removed == []
    assert (media_dir / MANIFEST_NAME).read_bytes() == manifest_bytes
    assert media_files(media_dir) == files
    assert {path: path.stat().st_mtime_ns for path in files} == mtimes


def test_guarda_la_cache_local_en_content_videos(
    content_dir: Path, media_dir: Path, full_raw: Path
) -> None:
    process_videos(content_dir, media_dir)

    assert CACHE_NAME == ".cache.json"
    assert (content_dir / "videos" / CACHE_NAME).is_file()


def test_si_falta_el_archivo_procesado_vuelve_a_procesar(
    content_dir: Path, media_dir: Path, full_raw: Path
) -> None:
    process_videos(content_dir, media_dir)
    url_to_path(media_dir, load_manifest(media_dir).signs["hola"].video).unlink()

    second = process_videos(content_dir, media_dir)

    assert second.processed == ["hola"]
    assert second.unchanged == ["gracias"]
    assert url_to_path(media_dir, load_manifest(media_dir).signs["hola"].video).is_file()


def test_reemplazar_el_original_cambia_la_ruta_y_borra_el_viejo_b55(
    content_dir: Path, media_dir: Path, full_raw: Path
) -> None:
    process_videos(content_dir, media_dir)
    old = load_manifest(media_dir).signs["hola"]
    old_video = url_to_path(media_dir, old.video).resolve()
    old_poster = url_to_path(media_dir, old.poster).resolve()

    make_clip(full_raw / "hola.mp4", seconds=1.0, audio=False, pattern="testsrc2")
    result = process_videos(content_dir, media_dir)

    new = load_manifest(media_dir).signs["hola"]
    assert result.processed == ["hola"]
    assert result.unchanged == ["gracias"]
    assert new.video != old.video
    assert new.poster != old.poster
    assert new.source_hash != old.source_hash
    assert not old_video.exists()
    assert not old_poster.exists()
    assert {p.resolve() for p in result.removed} == {old_video, old_poster}


def test_el_video_real_reemplaza_al_relleno_r9_3(
    content_dir: Path, media_dir: Path, raw_dir: Path
) -> None:
    placeholder_video = media_dir / "v" / "0000000000000000.mp4"
    placeholder_poster = media_dir / "p" / "0000000000000000.jpg"
    placeholder_video.parent.mkdir()
    placeholder_poster.parent.mkdir()
    placeholder_video.write_bytes(b"relleno")
    placeholder_poster.write_bytes(b"relleno")
    save_manifest(
        media_dir,
        Manifest(
            signs={
                "hola": ManifestEntry(
                    video="/media/v/0000000000000000.mp4",
                    poster="/media/p/0000000000000000.jpg",
                    placeholder=True,
                    source="placeholder",
                    duration=3.0,
                )
            }
        ),
    )
    make_clip(raw_dir / "hola.mp4", seconds=1.0, audio=False)

    result = process_videos(content_dir, media_dir)

    entry = load_manifest(media_dir).signs["hola"]
    assert result.processed == ["hola"]
    assert entry.placeholder is False
    assert entry.source == "video"
    assert entry.video != "/media/v/0000000000000000.mp4"
    assert not placeholder_video.exists()
    assert not placeholder_poster.exists()


def test_conserva_rellenos_de_senas_sin_original(
    content_dir: Path, media_dir: Path, raw_dir: Path
) -> None:
    placeholder = ManifestEntry(
        video="/media/v/0000000000000000.mp4",
        poster="/media/p/0000000000000000.jpg",
        placeholder=True,
        source="placeholder",
        duration=3.0,
    )
    (media_dir / "v").mkdir()
    (media_dir / "p").mkdir()
    (media_dir / "v" / "0000000000000000.mp4").write_bytes(b"relleno")
    (media_dir / "p" / "0000000000000000.jpg").write_bytes(b"relleno")
    save_manifest(media_dir, Manifest(signs={"buenos-dias": placeholder}))
    make_clip(raw_dir / "hola.mp4", seconds=1.0, audio=False)

    process_videos(content_dir, media_dir)

    manifest = load_manifest(media_dir)
    assert manifest.signs["buenos-dias"] == placeholder
    assert (media_dir / "v" / "0000000000000000.mp4").is_file()


def test_nombre_sin_slug_da_error_con_sugerencia_y_no_se_procesa_r9_4(
    content_dir: Path, media_dir: Path, raw_dir: Path
) -> None:
    make_clip(raw_dir / "Hol.mp4", seconds=1.0, audio=False)

    result = process_videos(content_dir, media_dir)

    assert result.errors == ['raw/Hol.mp4 no corresponde a ninguna seña. ¿Quisiste decir "hola"?']
    assert result.processed == []
    assert load_manifest(media_dir).signs == {}
    assert media_files(media_dir) == set()


def test_un_error_no_impide_procesar_las_demas(
    content_dir: Path, media_dir: Path, raw_dir: Path
) -> None:
    make_clip(raw_dir / "hola.mp4", seconds=1.0, audio=False)
    (raw_dir / "gracias.heic").write_bytes(b"")

    result = process_videos(content_dir, media_dir)

    assert result.processed == ["hola"]
    assert len(result.errors) == 1
    assert "HEIC" in result.errors[0]
    assert set(load_manifest(media_dir).signs) == {"hola"}


def test_video_de_mas_de_8_segundos_advierte(
    content_dir: Path, media_dir: Path, raw_dir: Path
) -> None:
    make_clip(raw_dir / "hola.mp4", seconds=9.0, size="160x120", audio=False)

    result = process_videos(content_dir, media_dir)

    assert result.processed == ["hola"]
    assert result.errors == []
    assert any("hola" in w for w in result.warnings)
    assert load_manifest(media_dir).signs["hola"].duration == pytest.approx(9.0, abs=0.2)


def test_video_corto_no_advierte(content_dir: Path, media_dir: Path, raw_dir: Path) -> None:
    make_clip(raw_dir / "hola.mp4", seconds=1.0, audio=False)

    result = process_videos(content_dir, media_dir)

    assert result.warnings == []


def test_video_e_imagenes_de_la_misma_sena_usa_el_video_b95(
    content_dir: Path, media_dir: Path, raw_dir: Path
) -> None:
    make_clip(raw_dir / "hola.mp4", seconds=1.0, audio=False)
    solid_image(raw_dir / "hola.jpg", (640, 480))

    result = process_videos(content_dir, media_dir)

    entry = load_manifest(media_dir).signs["hola"]
    assert entry.source == "video"
    assert entry.frames is None
    assert entry.source_hash == source_hash([raw_dir / "hola.mp4"])
    assert any("hola" in w for w in result.warnings)


def test_pasar_de_imagenes_a_video(content_dir: Path, media_dir: Path, raw_dir: Path) -> None:
    solid_image(raw_dir / "hola.jpg", (640, 480))
    process_videos(content_dir, media_dir)
    images_entry = load_manifest(media_dir).signs["hola"]
    assert images_entry.source == "images"
    assert images_entry.frames == 1

    (raw_dir / "hola.jpg").unlink()
    make_clip(raw_dir / "hola.mp4", seconds=1.0, audio=False)
    process_videos(content_dir, media_dir)

    video_entry = load_manifest(media_dir).signs["hola"]
    assert video_entry.source == "video"
    assert video_entry.video != images_entry.video
    assert not url_to_path(media_dir, images_entry.video).exists()


def test_sin_carpeta_raw_no_falla(tmp_path: Path, media_dir: Path) -> None:
    content = tmp_path / "solo-csv"
    content.mkdir()
    write_signs_csv(content, SIGNS)

    result = process_videos(content, media_dir)

    assert result.processed == []
    assert result.errors == []
