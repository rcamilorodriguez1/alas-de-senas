"""Archivos de MediaPipe servidos localmente (§10.1): WASM del paquete y modelo `.task`."""

from __future__ import annotations

import shutil
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

HAND_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
HAND_LANDMARKER = "hand_landmarker.task"
# Cámara holística (Grupo 10B, anexo A.2.1): manos + pose + cara, variante float16.
HOLISTIC_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/holistic_landmarker/"
    "holistic_landmarker/float16/latest/holistic_landmarker.task"
)
HOLISTIC_LANDMARKER = "holistic_landmarker.task"
MODELS = ((HAND_LANDMARKER, HAND_LANDMARKER_URL), (HOLISTIC_LANDMARKER, HOLISTIC_LANDMARKER_URL))
DOWNLOAD_TIMEOUT_S = 60

Download = Callable[[str, Path], None]


class CameraAssetsError(RuntimeError):
    """Falta el paquete de MediaPipe en node_modules (hay que ejecutar `npm ci`)."""


@dataclass(frozen=True, slots=True)
class CameraAssetsReport:
    wasm_files: tuple[str, ...]
    model: Path
    downloaded: bool  # False si el modelo ya estaba
    error: str | None = None  # descarga fallida: mensaje con la URL oficial


def _download(url: str, target: Path) -> None:
    # Solo la URL oficial fija (https): no hay entrada del usuario en la petición.
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_S) as response:  # noqa: S310
        data = response.read()
    partial = target.with_suffix(".part")
    partial.write_bytes(data)
    partial.replace(target)  # atómico: nunca queda un modelo a medias


def prepare_camera_assets(
    web_dir: Path, *, download: Download = _download, force: bool = False
) -> CameraAssetsReport:
    """Copia `@mediapipe/tasks-vision/wasm/*` y descarga los modelos `.task` que falten."""
    source = web_dir / "node_modules" / "@mediapipe" / "tasks-vision" / "wasm"
    if not source.is_dir():
        raise CameraAssetsError(
            f"No encontramos {source.as_posix()}. Ejecuta antes `npm ci --prefix apps/web`."
        )
    target_dir = web_dir / "public" / "mediapipe"
    wasm_dir = target_dir / "wasm"
    wasm_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for item in sorted(source.iterdir()):
        if item.is_file():
            shutil.copy2(item, wasm_dir / item.name)
            copied.append(item.name)

    downloaded = False
    errors: list[str] = []
    for name, url in MODELS:
        target = target_dir / name
        if target.is_file() and not force:
            continue
        try:
            download(url, target)
            downloaded = True
        except OSError as exc:
            errors.append(
                f"No se pudo descargar {name} ({exc}). Descárgalo a mano desde {url} y "
                f"guárdalo en {target.as_posix()}."
            )
    model = target_dir / HAND_LANDMARKER
    error = " ".join(errors) or None
    return CameraAssetsReport(tuple(copied), model, downloaded=downloaded, error=error)
