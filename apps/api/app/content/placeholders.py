"""Videos de relleno: la palabra escrita y «Video en preparación» (D6, §6.4, R9.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

BACKGROUND = "#0E2A2F"
FOREGROUND = "#FFFFFF"
LABEL = "Video en preparación"
SECONDS = 3.0
SIZE = (1280, 720)
FONT_FILE = "fonts/nunito-latin.woff2"  # relativo a content/


@dataclass(slots=True)
class PlaceholderResult:
    created: list[str] = field(default_factory=list)  # slugs con relleno nuevo o actualizado
    kept: list[str] = field(default_factory=list)  # slugs que ya tenían video real o relleno al día


def render_frame(word: str, font_path: Path) -> Image.Image:
    """Imagen SIZE con fondo BACKGROUND, `word` grande centrada y LABEL debajo (Pillow, nunca
    `drawtext` de ffmpeg). Palabras largas reducen el tamaño de letra para caber."""
    raise NotImplementedError


def generate_placeholders(
    content_dir: Path, media_dir: Path, raw_slugs: set[str] | None = None
) -> PlaceholderResult:
    """Para cada seña del CSV: si el manifiesto ya tiene un video real (`placeholder: false`) o
    la seña está en `raw_slugs` (tiene original en raw/), no la toca (nunca reemplaza un video
    real). Si ya tiene un relleno generado para la misma palabra, lo conserva. Si no, genera
    video (SECONDS, 30 fps) + póster con nombre por contenido y lo registra con
    `placeholder: true, source: "placeholder"`. Guarda el manifiesto y borra huérfanos.
    """
    raise NotImplementedError
