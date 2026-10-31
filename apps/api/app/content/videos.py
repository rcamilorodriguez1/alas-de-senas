"""`alas content videos`: originales de raw/ → medios normalizados y manifiesto (§6.4, D19, D25)."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.content.csv_reader import read_signs_csv
from app.content.ffmpeg import extract_poster, normalize_video, probe_duration
from app.content.images import images_to_video
from app.content.media import (
    Manifest,
    ManifestEntry,
    load_manifest,
    manifest_exists,
    remove_orphans,
    save_manifest,
    store_media,
)
from app.content.raw_files import RawAsset, scan_raw

CACHE_NAME = ".cache.json"  # en content/videos/ (ignorado en git)
MAX_SECONDS = 8


@dataclass(slots=True)
class VideosResult:
    processed: list[str] = field(default_factory=list)  # slugs procesados en esta ejecución
    unchanged: list[str] = field(default_factory=list)  # slugs saltados por la caché
    removed: list[Path] = field(default_factory=list)  # archivos huérfanos borrados
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def source_hash(paths: list[Path]) -> str:
    """SHA-256 (hex completo) del contenido de los originales de una seña, en orden."""
    if len(paths) == 1:
        return hashlib.sha256(paths[0].read_bytes()).hexdigest()
    digest = hashlib.sha256()
    for path in paths:  # el orden de los cuadros cambia el resultado
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
    return digest.hexdigest()


def process_videos(content_dir: Path, media_dir: Path) -> VideosResult:
    """Para cada RawAsset de `scan_raw(content_dir/videos/raw, slugs)`:

    - Si el manifiesto tiene la seña con `source_hash` igual y sus archivos existen → saltar
      (caché; además se guarda en `content/videos/.cache.json`).
    - Video: `normalize_video` + `extract_poster`; imágenes: `images_to_video`. Luego
      `store_media` y entrada del manifiesto `placeholder: false`, `source: "video"|"images"`,
      `duration`, `frames` (imágenes) y `source_hash`.
    - Duración > 8 s → advertencia. Errores del escaneo → `errors` (no procesa esos archivos).
    Guarda el manifiesto y borra huérfanos. No genera rellenos (eso es `placeholders`).
    Las señas sin original en raw/ conservan su entrada (en otro equipo raw/ no existe).
    """
    result = VideosResult()
    slugs = [row.slug for row in read_signs_csv(content_dir / "signs.csv")]
    scan = scan_raw(content_dir / "videos" / "raw", slugs)
    result.errors.extend(scan.errors)
    result.warnings.extend(scan.warnings)
    had_manifest = manifest_exists(media_dir)
    manifest = load_manifest(media_dir)
    for slug in sorted(scan.assets):
        asset = scan.assets[slug]
        digest = source_hash(list(asset.paths))
        current = manifest.signs.get(slug)
        if (
            current is not None
            and current.source_hash == digest
            and _files_exist(media_dir, current)
        ):
            result.unchanged.append(slug)
            continue
        try:
            entry = _process(asset, digest, media_dir)
        except (RuntimeError, OSError) as exc:
            result.errors.append(f"No se pudo procesar «{slug}»: {exc}")
            continue
        manifest.signs[slug] = entry
        result.processed.append(slug)
        if entry.duration > MAX_SECONDS:
            result.warnings.append(
                f"«{slug}» dura {entry.duration:.1f} s; los clips deben durar como máximo "
                f"{MAX_SECONDS} s."
            )
    save_manifest(media_dir, manifest)
    if had_manifest:  # sin manifiesto previo no se sabe qué archivos son huérfanos
        result.removed = remove_orphans(media_dir, manifest)
    _save_cache(content_dir, manifest)
    return result


def _files_exist(media_dir: Path, entry: ManifestEntry) -> bool:
    return all(
        (media_dir / url.removeprefix("/media/")).is_file() for url in (entry.video, entry.poster)
    )


def _process(asset: RawAsset, digest: str, media_dir: Path) -> ManifestEntry:
    with tempfile.TemporaryDirectory(prefix="alas-video-") as tmp:
        work = Path(tmp)
        video = work / "video.mp4"
        poster = work / "poster.jpg"
        frames: int | None = None
        if asset.kind == "video":
            normalize_video(asset.paths[0], video)
            extract_poster(video, poster)
        else:
            frames = images_to_video(asset.paths, video, poster)
        duration = probe_duration(video)
        video_url, poster_url = store_media(media_dir, video, poster)
    return ManifestEntry(
        video=video_url,
        poster=poster_url,
        placeholder=False,
        source=asset.kind,
        duration=duration,
        frames=frames,
        source_hash=digest,
    )


def _save_cache(content_dir: Path, manifest: Manifest) -> None:
    """Caché local (ignorada en git): seña → hash de los originales ya procesados."""
    cache = {
        slug: entry.source_hash
        for slug, entry in sorted(manifest.signs.items())
        if entry.source_hash is not None
    }
    path = content_dir / "videos" / CACHE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8", newline="\n")
