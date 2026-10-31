"""Emparejamiento de archivos de `content/videos/raw/` con los slugs (§6.4, §6.4.1, B90, B95)."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".m4v")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
HEIC_EXTENSIONS = (".heic", ".heif")
MAX_FRAMES = 4
HEIC_MESSAGE = (
    "{name}: el formato HEIC no es compatible. Exporta la foto como JPG (en el iPhone: "
    "Ajustes → Cámara → Formatos → Más compatible)."
)


@dataclass(frozen=True, slots=True)
class RawAsset:
    slug: str
    kind: Literal["video", "images"]
    paths: tuple[Path, ...]  # un video, o de 1 a 4 imágenes en orden (__1, __2…)


@dataclass(slots=True)
class RawScan:
    assets: dict[str, RawAsset] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def suggest_slug(name: str, slugs: Collection[str]) -> str | None:
    """Slug más parecido (Levenshtein sobre el nombre normalizado: minúsculas, sin tildes,
    espacios y «_» → «-»). None si ninguno está a distancia ≤ 3."""
    raise NotImplementedError


def scan_raw(raw_dir: Path, slugs: Collection[str]) -> RawScan:
    """Recorre `raw_dir` (sin subcarpetas; ignora archivos ocultos y `.gitkeep`).

    - Extensiones sin importar mayúsculas. `slug.ext` (video o una imagen) y `slug__N.ext`
      (cuadro N de una secuencia de imágenes, dos guiones bajos). `numero-1.jpg` es una imagen
      de la seña «numero-1», nunca el cuadro 1 de «numero».
    - Nombre que no corresponde a un slug → error
      `raw/Gracia.mp4 no corresponde a ninguna seña. ¿Quisiste decir "gracias"?`
      (sin sugerencia: `raw/xyz.mp4 no corresponde a ninguna seña.`).
    - `.heic`/`.heif` → error HEIC_MESSAGE. Otra extensión → advertencia (se ignora).
    - Secuencia con huecos → error `Faltan imágenes en la secuencia de «gracias»: hay __1 y
      __3, falta __2.`; más de MAX_FRAMES → error; `slug.jpg` y `slug__1.jpg` a la vez → error.
    - Video e imágenes de la misma seña → se usa el video y se advierte (B95). Dos videos de la
      misma seña → error.
    """
    raise NotImplementedError
