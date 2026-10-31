"""Plan B: una o varias fotos → clip MP4 con el formato de los videos (D25, §6.4.1)."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageOps

from app.content.ffmpeg import frames_to_video
from app.domain.policies.scoring import round_half_up

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
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")  # B91: fotos de celular
    image.thumbnail(CANVAS, Image.Resampling.LANCZOS)  # B92: reducir antes de procesar
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    canvas.paste(image, ((CANVAS[0] - image.width) // 2, (CANVAS[1] - image.height) // 2))
    return canvas


def image_height(path: Path) -> int:
    """Alto real tras aplicar la rotación EXIF (para la advertencia de < MIN_HEIGHT px)."""
    with Image.open(path) as opened:
        return ImageOps.exif_transpose(opened).height


def build_frames(images: Sequence[Image.Image], fps: int = 30) -> list[Image.Image]:
    """Una imagen: SINGLE_SECONDS fijos. Varias: cada una FRAME_SECONDS, con fundido de
    FADE_SECONDS (Image.blend) hacia la siguiente dentro de esos segundos.

    Cantidad de cuadros: una imagen = round_half_up(3·fps); n imágenes = n·round_half_up(1,2·fps).
    """
    if not images:
        raise ValueError("Se necesita al menos una imagen.")
    if len(images) == 1:
        return [images[0]] * _frames_for(SINGLE_SECONDS, fps)
    per_image = _frames_for(FRAME_SECONDS, fps)
    fade = _frames_for(FADE_SECONDS, fps)
    frames: list[Image.Image] = []
    for index, image in enumerate(images):
        following = images[index + 1] if index + 1 < len(images) else None
        hold = per_image - fade if following is not None else per_image
        frames.extend([image] * hold)
        if following is not None:
            for step in range(1, fade + 1):
                frames.append(Image.blend(image, following, step / (fade + 1)))
    return frames


def images_to_video(paths: Sequence[Path], video: Path, poster: Path) -> int:
    """Convierte las imágenes en `video` (vía ffmpeg) y guarda `poster` = primera imagen
    preparada (JPG). Devuelve la cantidad de imágenes usadas."""
    prepared = [prepare_image(path) for path in paths]
    poster.parent.mkdir(parents=True, exist_ok=True)
    prepared[0].save(poster, "JPEG", quality=85)
    with tempfile.TemporaryDirectory(prefix="alas-frames-") as tmp:
        frames_dir = Path(tmp)
        for index, frame in enumerate(build_frames(prepared), start=1):
            frame.save(frames_dir / f"{index:05d}.png")
        frames_to_video(frames_dir, video)
    return len(prepared)


def _frames_for(seconds: float, fps: int) -> int:
    # Segundos con un decimal → décimas enteras para redondear sin flotantes (B10).
    tenths = int(f"{seconds:.1f}".replace(".", ""))
    return round_half_up(tenths * fps, 10)
