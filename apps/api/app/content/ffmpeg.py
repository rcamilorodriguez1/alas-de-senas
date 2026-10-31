"""Llamadas a ffmpeg (incluido con imageio-ffmpeg, D7). Siempre lista de argumentos, sin shell."""

from __future__ import annotations

import re
import subprocess
from functools import cache
from pathlib import Path

import imageio_ffmpeg

FPS = 30
HEIGHT = 720
_ENCODE = [
    "-c:v",
    "libx264",
    "-profile:v",
    "high",
    "-preset",
    "veryfast",
    "-crf",
    "23",
    "-movflags",
    "+faststart",
    "-an",
]
_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


@cache
def ffmpeg_exe() -> str:
    exe: str = imageio_ffmpeg.get_ffmpeg_exe()
    return exe


def _run(args: list[str]) -> str:
    """Ejecuta ffmpeg y devuelve stderr (donde ffmpeg informa); falla con un mensaje claro."""
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        raise RuntimeError(f"ffmpeg falló ({result.returncode}): {tail}")
    return result.stderr


def normalize_video(source: Path, target: Path) -> None:
    """Comando de §6.4: sin audio, 720p, 30 fps, H.264 high yuv420p, crf 23, +faststart."""
    target.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "-y",
            "-i",
            str(source),
            "-vf",
            f"scale=-2:{HEIGHT}:flags=lanczos,fps={FPS},format=yuv420p",
            *_ENCODE,
            str(target),
        ]
    )


def extract_poster(video: Path, poster: Path, at_second: float = 1.0) -> None:
    """Un cuadro JPG del segundo `at_second` (si el video es más corto, del primer cuadro)."""
    poster.parent.mkdir(parents=True, exist_ok=True)
    start = at_second if probe_duration(video) > at_second else 0.0
    _run(
        ["-y", "-ss", f"{start:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "4", str(poster)]
    )


def frames_to_video(frames_dir: Path, target: Path, fps: int = FPS) -> None:
    """`%05d.png` de `frames_dir` → MP4 (yuv420p, H.264, +faststart, sin audio)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "%05d.png"),
            "-vf",
            "format=yuv420p",
            *_ENCODE,
            str(target),
        ]
    )


def probe_duration(video: Path) -> float:
    """Duración en segundos (leída de la salida de ffmpeg `-i`)."""
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(video)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )  # sin salida, ffmpeg termina con código 1: solo interesa la información de stderr
    match = _DURATION.search(result.stderr)
    if match is None:
        raise RuntimeError(f"No se pudo leer la duración de {video.name}.")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def image_to_video(image: Path, target: Path, seconds: float, fps: int = FPS) -> None:
    """Una imagen fija en bucle durante `seconds` → MP4 (mismo formato que los demás)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-i",
            str(image),
            "-t",
            f"{seconds:.2f}",
            "-vf",
            "format=yuv420p",
            *_ENCODE,
            str(target),
        ]
    )
