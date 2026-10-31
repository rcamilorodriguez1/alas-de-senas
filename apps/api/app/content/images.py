"""Plan B: una o varias fotos → clip MP4 con el formato de los videos (D25, §6.4.1)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PIL import Image

CANVAS = (1280, 720)
BACKGROUND = "#F5FAF7"
SINGLE_SECONDS = 3.0
FRAME_SECONDS = 1.2
FADE_SECONDS = 0.4
MIN_HEIGHT = 480


def prepare_image(path: Path) -> Image.Image:
    """`exif_transpose` → RGB → `thumbnail(CANVAS)` → centrada en un lienzo CANVAS con BACKGROUND.

    Siempre devuelve una imagen RGB de exactamente 1280 x 720 (medidas pares para yuv420p, B93).
    """
    raise NotImplementedError


def image_height(path: Path) -> int:
    """Alto real tras aplicar la rotación EXIF (para la advertencia de < MIN_HEIGHT px)."""
    raise NotImplementedError


def build_frames(images: Sequence[Image.Image], fps: int = 30) -> list[Image.Image]:
    """Una imagen: SINGLE_SECONDS fijos. Varias: cada una FRAME_SECONDS, con fundido de
    FADE_SECONDS (Image.blend) hacia la siguiente dentro de esos segundos.

    Cantidad de cuadros: una imagen = round_half_up(3·fps); n imágenes = n·round_half_up(1,2·fps).
    """
    raise NotImplementedError


def images_to_video(paths: Sequence[Path], video: Path, poster: Path) -> int:
    """Convierte las imágenes en `video` (vía ffmpeg) y guarda `poster` = primera imagen
    preparada (JPG). Devuelve la cantidad de imágenes usadas."""
    raise NotImplementedError
