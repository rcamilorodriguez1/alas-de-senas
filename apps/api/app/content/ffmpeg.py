"""Llamadas a ffmpeg (incluido con imageio-ffmpeg, D7). Siempre lista de argumentos, sin shell."""

from __future__ import annotations

from pathlib import Path

FPS = 30
HEIGHT = 720


def ffmpeg_exe() -> str:
    raise NotImplementedError


def normalize_video(source: Path, target: Path) -> None:
    """Comando de §6.4: sin audio, 720p, 30 fps, H.264 high yuv420p, crf 23, +faststart."""
    raise NotImplementedError


def extract_poster(video: Path, poster: Path, at_second: float = 1.0) -> None:
    """Un cuadro JPG del segundo `at_second` (si el video es más corto, del primer cuadro)."""
    raise NotImplementedError


def frames_to_video(frames_dir: Path, target: Path, fps: int = FPS) -> None:
    """`%05d.png` de `frames_dir` → MP4 (yuv420p, H.264, +faststart, sin audio)."""
    raise NotImplementedError


def probe_duration(video: Path) -> float:
    """Duración en segundos (leída de la salida de ffmpeg `-i`)."""
    raise NotImplementedError
