"""Tareas 2.5/2.6 — manifiesto de medios y nombres por contenido (D19, B55, B56)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.content.media import (
    HASH_LENGTH,
    MANIFEST_NAME,
    Manifest,
    ManifestEntry,
    file_hash,
    load_manifest,
    remove_orphans,
    save_manifest,
    store_media,
)


def _entry(name: str, *, placeholder: bool = False) -> ManifestEntry:
    return ManifestEntry(
        video=f"/media/v/{name}.mp4",
        poster=f"/media/p/{name}.jpg",
        placeholder=placeholder,
        source="placeholder" if placeholder else "video",
        duration=2.5,
        source_hash=None if placeholder else "a" * 64,
    )


def _sample_manifest() -> Manifest:
    # Claves en desorden a propósito.
    return Manifest(
        signs={
            "zeta": _entry("1111111111111111"),
            "abuelo": _entry("2222222222222222", placeholder=True),
            "mama": ManifestEntry(
                video="/media/v/3333333333333333.mp4",
                poster="/media/p/3333333333333333.jpg",
                placeholder=False,
                source="images",
                duration=2.4,
                frames=2,
                source_hash="b" * 64,
            ),
        }
    )


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# ---------- file_hash ----------


def test_file_hash_son_los_primeros_16_hex_del_sha256(tmp_path: Path) -> None:
    path = _write(tmp_path / "video.mp4", b"contenido del video")

    digest = file_hash(path)

    assert HASH_LENGTH == 16
    assert digest == hashlib.sha256(b"contenido del video").hexdigest()[:16]
    assert len(digest) == 16
    assert all(ch in "0123456789abcdef" for ch in digest)


def test_file_hash_cambia_si_cambia_el_contenido(tmp_path: Path) -> None:
    a = _write(tmp_path / "a.mp4", b"relleno")
    b = _write(tmp_path / "b.mp4", b"video real")

    assert file_hash(a) != file_hash(b)


def test_file_hash_no_depende_del_nombre(tmp_path: Path) -> None:
    a = _write(tmp_path / "hola.mp4", b"mismo")
    b = _write(tmp_path / "otro" / "gracias.mp4", b"mismo")

    assert file_hash(a) == file_hash(b)


# ---------- load_manifest / save_manifest ----------


def test_load_manifest_sin_archivo_devuelve_manifiesto_vacio(tmp_path: Path) -> None:
    manifest = load_manifest(tmp_path)

    assert manifest.version == 1
    assert manifest.signs == {}


def test_save_manifest_escribe_manifest_json_en_media_dir(tmp_path: Path) -> None:
    save_manifest(tmp_path, _sample_manifest())

    assert MANIFEST_NAME == "manifest.json"
    assert (tmp_path / "manifest.json").is_file()


def test_save_manifest_ordena_las_claves_de_signs(tmp_path: Path) -> None:
    save_manifest(tmp_path, _sample_manifest())

    data = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert list(data["signs"]) == ["abuelo", "mama", "zeta"]


def test_save_manifest_usa_lf_e_indentacion_de_2_espacios(tmp_path: Path) -> None:
    save_manifest(tmp_path, _sample_manifest())

    raw = (tmp_path / MANIFEST_NAME).read_bytes()
    assert b"\r\n" not in raw
    text = raw.decode("utf-8")
    assert '\n  "signs": {' in text
    assert '\n    "abuelo": {' in text
    assert '\n      "video": "/media/v/2222222222222222.mp4"' in text


def test_save_manifest_es_estable_dos_guardados_mismos_bytes(tmp_path: Path) -> None:
    save_manifest(tmp_path, _sample_manifest())
    first = (tmp_path / MANIFEST_NAME).read_bytes()

    save_manifest(tmp_path, _sample_manifest())
    second = (tmp_path / MANIFEST_NAME).read_bytes()

    assert first == second


def test_save_manifest_no_depende_del_orden_de_insercion(tmp_path: Path) -> None:
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    original = _sample_manifest()
    reversed_manifest = Manifest(signs=dict(reversed(list(original.signs.items()))))

    save_manifest(a_dir, original)
    save_manifest(b_dir, reversed_manifest)

    assert (a_dir / MANIFEST_NAME).read_bytes() == (b_dir / MANIFEST_NAME).read_bytes()


def test_manifiesto_ida_y_vuelta(tmp_path: Path) -> None:
    original = _sample_manifest()

    save_manifest(tmp_path, original)
    loaded = load_manifest(tmp_path)

    assert loaded == original
    assert loaded.signs["mama"].frames == 2
    assert loaded.signs["mama"].source == "images"
    assert loaded.signs["abuelo"].placeholder is True
    assert loaded.signs["abuelo"].source_hash is None


def test_guardar_lo_cargado_produce_los_mismos_bytes(tmp_path: Path) -> None:
    save_manifest(tmp_path, _sample_manifest())
    first = (tmp_path / MANIFEST_NAME).read_bytes()

    save_manifest(tmp_path, load_manifest(tmp_path))

    assert (tmp_path / MANIFEST_NAME).read_bytes() == first


# ---------- store_media ----------


def test_store_media_mueve_a_rutas_por_contenido(tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    work = tmp_path / "trabajo"
    video = _write(work / "salida.mp4", b"video procesado")
    poster = _write(work / "salida.jpg", b"poster procesado")
    expected = hashlib.sha256(b"video procesado").hexdigest()[:16]

    video_url, poster_url = store_media(media_dir, video, poster)

    assert video_url == f"/media/v/{expected}.mp4"
    assert poster_url == f"/media/p/{expected}.jpg"
    assert (media_dir / "v" / f"{expected}.mp4").read_bytes() == b"video procesado"
    assert (media_dir / "p" / f"{expected}.jpg").read_bytes() == b"poster procesado"
    assert not video.exists()
    assert not poster.exists()


def test_store_media_la_url_no_revela_la_palabra(tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    video = _write(tmp_path / "gracias.mp4", b"gracias")
    poster = _write(tmp_path / "gracias.jpg", b"gracias-poster")

    video_url, poster_url = store_media(media_dir, video, poster)

    assert "gracias" not in video_url
    assert "gracias" not in poster_url


def test_store_media_contenido_distinto_da_ruta_distinta_b55(tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    placeholder_url, _ = store_media(
        media_dir, _write(tmp_path / "a.mp4", b"relleno"), _write(tmp_path / "a.jpg", b"pa")
    )
    real_url, _ = store_media(
        media_dir, _write(tmp_path / "b.mp4", b"video real"), _write(tmp_path / "b.jpg", b"pb")
    )

    assert placeholder_url != real_url


def test_store_media_mismo_contenido_misma_ruta_sin_error(tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    first, first_poster = store_media(
        media_dir, _write(tmp_path / "1.mp4", b"igual"), _write(tmp_path / "1.jpg", b"p")
    )
    second, second_poster = store_media(
        media_dir, _write(tmp_path / "2.mp4", b"igual"), _write(tmp_path / "2.jpg", b"p")
    )

    assert first == second
    assert first_poster == second_poster
    assert len(list((media_dir / "v").iterdir())) == 1


# ---------- remove_orphans ----------


def test_remove_orphans_borra_solo_lo_no_referenciado(tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    kept_video = _write(media_dir / "v" / "1111111111111111.mp4", b"v1")
    kept_poster = _write(media_dir / "p" / "1111111111111111.jpg", b"p1")
    orphan_video = _write(media_dir / "v" / "9999999999999999.mp4", b"v9")
    orphan_poster = _write(media_dir / "p" / "9999999999999999.jpg", b"p9")
    manifest = Manifest(signs={"zeta": _entry("1111111111111111")})
    save_manifest(media_dir, manifest)

    removed = remove_orphans(media_dir, manifest)

    assert {p.resolve() for p in removed} == {orphan_video.resolve(), orphan_poster.resolve()}
    assert not orphan_video.exists()
    assert not orphan_poster.exists()
    assert kept_video.exists()
    assert kept_poster.exists()
    assert (media_dir / MANIFEST_NAME).exists()


def test_remove_orphans_sin_huerfanos_no_borra_nada(tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    _write(media_dir / "v" / "1111111111111111.mp4", b"v1")
    _write(media_dir / "p" / "1111111111111111.jpg", b"p1")
    manifest = Manifest(signs={"zeta": _entry("1111111111111111")})

    assert remove_orphans(media_dir, manifest) == []


def test_remove_orphans_con_manifiesto_vacio_borra_todo_en_v_y_p(tmp_path: Path) -> None:
    media_dir = tmp_path / "media"
    video = _write(media_dir / "v" / "1111111111111111.mp4", b"v1")
    poster = _write(media_dir / "p" / "1111111111111111.jpg", b"p1")

    removed = remove_orphans(media_dir, Manifest())

    assert {p.resolve() for p in removed} == {video.resolve(), poster.resolve()}
