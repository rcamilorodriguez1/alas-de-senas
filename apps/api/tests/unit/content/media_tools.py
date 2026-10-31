"""Utilidades de prueba para medios: clips con ffmpeg real (imageio-ffmpeg), sondeo e imágenes.

Las pruebas no usan el código de producción para crear o inspeccionar archivos: así un error en
`app.content.ffmpeg` no puede ocultarse a sí mismo. Siempre lista de argumentos, sin shell.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

CSV_HEADER = "slug,word,meaning,how_to,usage_example,category,node,order,motion"


def ffmpeg() -> str:
    return str(imageio_ffmpeg.get_ffmpeg_exe())


def make_clip(
    path: Path,
    *,
    seconds: float = 1.0,
    size: str = "320x240",
    audio: bool = True,
    pattern: str = "testsrc",
) -> Path:
    """Clip MP4 de prueba (lavfi). `yuv444p` a propósito: la normalización debe pasar a yuv420p."""
    args = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"]
    args += ["-f", "lavfi", "-i", f"{pattern}=size={size}:rate=30"]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
    args += ["-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv444p"]
    if audio:
        args += ["-c:a", "aac"]
    args.append(str(path))
    subprocess.run(args, check=True, capture_output=True)  # noqa: S603 — lista fija de argumentos
    return path


@dataclass(frozen=True, slots=True)
class MediaInfo:
    raw: str
    duration: float
    width: int
    height: int
    has_audio: bool
    codec: str
    pix_fmt: str


_DURATION = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO = re.compile(r"Video: (\w+).*?, (\w+)(?:\([^)]*\))?, (\d{2,5})x(\d{2,5})")


def probe(path: Path) -> MediaInfo:
    """Lee la salida de `ffmpeg -i` (sale con código 1 porque no hay salida; es lo esperado)."""
    proc = subprocess.run(  # noqa: S603 — lista fija de argumentos
        [ffmpeg(), "-hide_banner", "-i", str(path)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw = proc.stderr
    duration_match = _DURATION.search(raw)
    video_match = _VIDEO.search(raw)
    assert duration_match is not None, raw
    assert video_match is not None, raw
    hours, minutes, secs = duration_match.groups()
    return MediaInfo(
        raw=raw,
        duration=int(hours) * 3600 + int(minutes) * 60 + float(secs),
        width=int(video_match.group(3)),
        height=int(video_match.group(4)),
        has_audio="Audio:" in raw,
        codec=video_match.group(1),
        pix_fmt=video_match.group(2),
    )


def assert_web_video(path: Path, *, height: int = 720) -> MediaInfo:
    """Formato común de todos los videos servidos (§6.4): H.264, yuv420p, sin audio, 720 de alto."""
    assert path.is_file(), path
    info = probe(path)
    assert info.codec == "h264", info.raw
    assert info.pix_fmt == "yuv420p", info.raw
    assert not info.has_audio, info.raw
    assert info.height == height, info.raw
    assert info.width % 2 == 0, info.raw
    return info


def solid_image(
    path: Path, size: tuple[int, int], color: tuple[int, int, int] = (200, 40, 40)
) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def url_to_path(media_dir: Path, url: str) -> Path:
    """«/media/v/<hash>.mp4» → media_dir/v/<hash>.mp4."""
    prefix = "/media/"
    assert url.startswith(prefix), url
    return media_dir / url.removeprefix(prefix)


def media_files(media_dir: Path) -> set[Path]:
    return {
        p for sub in ("v", "p") if (media_dir / sub).is_dir() for p in (media_dir / sub).iterdir()
    }


def write_signs_csv(content_dir: Path, rows: list[tuple[str, str]]) -> Path:
    """signs.csv mínimo con (slug, palabra); el resto de columnas con valores válidos."""
    lines = [CSV_HEADER]
    for order, (slug, word) in enumerate(rows, start=1):
        lines.append(
            f"{slug},{word},Significado de {word}.,,Ejemplo con {word}.,saludos,M1-N1,{order},"
        )
    path = content_dir / "signs.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path
