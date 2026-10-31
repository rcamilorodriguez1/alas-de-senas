"""`alas content videos`: originales de raw/ → medios normalizados y manifiesto (§6.4, D19, D25)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CACHE_NAME = ".cache.json"  # en content/videos/ (ignorado en git)


@dataclass(slots=True)
class VideosResult:
    processed: list[str] = field(default_factory=list)  # slugs procesados en esta ejecución
    unchanged: list[str] = field(default_factory=list)  # slugs saltados por la caché
    removed: list[Path] = field(default_factory=list)  # archivos huérfanos borrados
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def source_hash(paths: list[Path]) -> str:
    """SHA-256 (hex completo) del contenido de los originales de una seña, en orden."""
    raise NotImplementedError


def process_videos(content_dir: Path, media_dir: Path) -> VideosResult:
    """Para cada RawAsset de `scan_raw(content_dir/videos/raw, slugs)`:

    - Si el manifiesto tiene la seña con `source_hash` igual y sus archivos existen → saltar
      (caché; además se guarda en `content/videos/.cache.json`).
    - Video: `normalize_video` + `extract_poster`; imágenes: `images_to_video`. Luego
      `store_media` y entrada del manifiesto `placeholder: false`, `source: "video"|"images"`,
      `duration`, `frames` (imágenes) y `source_hash`.
    - Duración > 8 s → advertencia. Errores del escaneo → `errors` (no procesa esos archivos).
    Guarda el manifiesto y borra huérfanos. No genera rellenos (eso es `placeholders`).
    """
    raise NotImplementedError
