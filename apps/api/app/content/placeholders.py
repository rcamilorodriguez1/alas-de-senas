"""Videos de relleno: la palabra escrita y «Video en preparación» (D6, §6.4, R9.2)."""

from __future__ import annotations

import contextlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.content.csv_reader import read_signs_csv
from app.content.ffmpeg import image_to_video, probe_duration
from app.content.media import (
    ManifestEntry,
    load_manifest,
    manifest_exists,
    remove_orphans,
    save_manifest,
    store_media,
)

BACKGROUND = "#0E2A2F"
FOREGROUND = "#FFFFFF"
LABEL = "Video en preparación"
SECONDS = 3.0
SIZE = (1280, 720)
FONT_FILE = "fonts/nunito-latin.woff2"  # relativo a content/
FPS = 30
WORD_MAX_SIZE = 150
WORD_MIN_SIZE = 48
LABEL_SIZE = 44
MARGIN = 80
WORD_WEIGHT = 800  # Nunito variable: ExtraBold
LABEL_WEIGHT = 600


@dataclass(slots=True)
class PlaceholderResult:
    created: list[str] = field(default_factory=list)  # slugs con relleno nuevo o actualizado
    kept: list[str] = field(default_factory=list)  # slugs que ya tenían video real o relleno al día


def render_frame(word: str, font_path: Path) -> Image.Image:
    """Imagen SIZE con fondo BACKGROUND, `word` grande centrada y LABEL debajo (Pillow, nunca
    `drawtext` de ffmpeg). Palabras largas reducen el tamaño de letra para caber."""
    image = Image.new("RGB", SIZE, BACKGROUND)
    draw = ImageDraw.Draw(image)
    max_width = SIZE[0] - 2 * MARGIN
    size = WORD_MAX_SIZE
    font = _font(font_path, size, WORD_WEIGHT)
    while size > WORD_MIN_SIZE and draw.textlength(word, font=font) > max_width:
        size -= 6
        font = _font(font_path, size, WORD_WEIGHT)
    center_x = SIZE[0] // 2
    draw.text((center_x, SIZE[1] // 2 - 30), word, font=font, fill=FOREGROUND, anchor="mm")
    label_font = _font(font_path, LABEL_SIZE, LABEL_WEIGHT)
    draw.text((center_x, SIZE[1] - 110), LABEL, font=label_font, fill="#9FD3C7", anchor="mm")
    return image


def _font(font_path: Path, size: int, weight: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(font_path), size)
    with contextlib.suppress(OSError):  # fuente no variable: se usa el peso que traiga
        font.set_variation_by_axes([weight])
    return font


def generate_placeholders(
    content_dir: Path, media_dir: Path, raw_slugs: set[str] | None = None
) -> PlaceholderResult:
    """Para cada seña del CSV: si el manifiesto ya tiene un video real (`placeholder: false`) o
    la seña está en `raw_slugs` (tiene original en raw/), no la toca (nunca reemplaza un video
    real). Si ya tiene un relleno generado para la misma palabra, lo conserva. Si no, genera
    video (SECONDS, 30 fps) + póster con nombre por contenido y lo registra con
    `placeholder: true, source: "placeholder"`. Guarda el manifiesto y borra huérfanos.
    """
    rows = read_signs_csv(content_dir / "signs.csv")
    font_path = content_dir / FONT_FILE
    had_manifest = manifest_exists(media_dir)
    manifest = load_manifest(media_dir)
    skip = raw_slugs or set()
    result = PlaceholderResult()
    for row in rows:
        entry = manifest.signs.get(row.slug)
        if row.slug in skip or (entry is not None and not entry.placeholder):
            result.kept.append(row.slug)
            continue
        if entry is not None and entry.label == row.word and _files_exist(media_dir, entry):
            result.kept.append(row.slug)
            continue
        manifest.signs[row.slug] = _make(row.word, font_path, media_dir)
        result.created.append(row.slug)
    save_manifest(media_dir, manifest)
    if had_manifest:  # sin manifiesto previo no se sabe qué archivos son huérfanos
        remove_orphans(media_dir, manifest)
    return result


def _files_exist(media_dir: Path, entry: ManifestEntry) -> bool:
    return all(
        (media_dir / url.removeprefix("/media/")).is_file() for url in (entry.video, entry.poster)
    )


def _make(word: str, font_path: Path, media_dir: Path) -> ManifestEntry:
    frame = render_frame(word, font_path)
    with tempfile.TemporaryDirectory(prefix="alas-placeholder-") as tmp:
        work = Path(tmp)
        still = work / "frame.png"
        frame.save(still)
        video = work / "video.mp4"
        poster = work / "poster.jpg"
        image_to_video(still, video, SECONDS, FPS)
        frame.save(poster, "JPEG", quality=85)
        duration = probe_duration(video)
        video_url, poster_url = store_media(media_dir, video, poster)
    return ManifestEntry(
        video=video_url,
        poster=poster_url,
        placeholder=True,
        source="placeholder",
        duration=duration,
        label=word,
    )
