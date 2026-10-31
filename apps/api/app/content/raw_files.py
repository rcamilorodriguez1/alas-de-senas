"""Emparejamiento de archivos de `content/videos/raw/` con los slugs (§6.4, §6.4.1, B90, B95)."""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.domain.text import levenshtein, normalize_text

VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".m4v")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
HEIC_EXTENSIONS = (".heic", ".heif")
MAX_FRAMES = 4
MAX_SUGGESTION_DISTANCE = 3
IGNORED_NAMES = {".gitkeep", "Thumbs.db", "desktop.ini"}
_FRAME = re.compile(r"^(?P<slug>.+)__(?P<n>\d+)$")
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
    candidate = re.sub(r"[\s_]+", "-", normalize_text(name)).strip("-")
    best: tuple[int, str] | None = None
    for slug in sorted(slugs):
        distance = levenshtein(candidate, slug)
        if best is None or distance < best[0]:
            best = (distance, slug)
    if best is None or best[0] > MAX_SUGGESTION_DISTANCE:
        return None
    return best[1]


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
    scan = RawScan()
    known = set(slugs)
    videos: dict[str, list[Path]] = {}
    singles: dict[str, list[Path]] = {}
    frames: dict[str, dict[int, Path]] = {}
    files = sorted(
        (f for f in raw_dir.iterdir() if f.is_file()) if raw_dir.is_dir() else [],
        key=lambda f: f.name,
    )
    for path in files:
        if path.name.startswith(".") or path.name in IGNORED_NAMES:
            continue
        shown = f"raw/{path.name}"
        ext = path.suffix.lower()
        if ext in HEIC_EXTENSIONS:
            scan.errors.append(HEIC_MESSAGE.format(name=shown))
            continue
        if ext not in VIDEO_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
            scan.warnings.append(f"{shown}: formato no reconocido; se ignora.")
            continue
        stem = path.stem.lower()
        frame = _FRAME.match(stem) if ext in IMAGE_EXTENSIONS else None
        slug = frame.group("slug") if frame else stem
        if slug not in known:
            suggestion = suggest_slug(slug, known)
            message = f"{shown} no corresponde a ninguna seña."
            if suggestion is not None:
                message += f' ¿Quisiste decir "{suggestion}"?'
            scan.errors.append(message)
            continue
        if ext in VIDEO_EXTENSIONS:
            videos.setdefault(slug, []).append(path)
        elif frame:
            frames.setdefault(slug, {})[int(frame.group("n"))] = path
        else:
            singles.setdefault(slug, []).append(path)

    for slug in sorted(set(videos) | set(singles) | set(frames)):
        found_videos = videos.get(slug, [])
        has_images = slug in singles or slug in frames
        if len(found_videos) > 1:
            names = ", ".join(f"raw/{v.name}" for v in found_videos)
            scan.errors.append(f"«{slug}» tiene varios videos ({names}): deja solo uno.")
            continue
        if found_videos:
            if has_images:
                scan.warnings.append(
                    f"«{slug}» tiene video e imágenes: se usa el video (borra las imágenes)."
                )
            scan.assets[slug] = RawAsset(slug, "video", (found_videos[0],))
            continue
        asset = _images_asset(slug, singles.get(slug, []), frames.get(slug, {}), scan.errors)
        if asset is not None:
            scan.assets[slug] = asset
    return scan


def _images_asset(
    slug: str, singles: list[Path], frames: dict[int, Path], errors: list[str]
) -> RawAsset | None:
    if singles and frames:
        errors.append(
            f"«{slug}» tiene una imagen sola y una secuencia (__1, __2…) a la vez: usa solo una."
        )
        return None
    if len(singles) > 1:
        errors.append(f"«{slug}» tiene varias imágenes sueltas: usa {slug}.jpg o una secuencia.")
        return None
    if singles:
        return RawAsset(slug, "images", (singles[0],))
    numbers = sorted(frames)
    if len(numbers) > MAX_FRAMES:
        errors.append(
            f"La secuencia de «{slug}» tiene {len(numbers)} imágenes; máximo {MAX_FRAMES}."
        )
        return None
    expected = list(range(1, numbers[-1] + 1))
    if numbers != expected:
        present = " y ".join(f"__{n}" for n in numbers)
        missing = ", ".join(f"__{n}" for n in expected if n not in frames)
        errors.append(
            f"Faltan imágenes en la secuencia de «{slug}»: hay {present}, falta {missing}."
        )
        return None
    return RawAsset(slug, "images", tuple(frames[n] for n in numbers))
