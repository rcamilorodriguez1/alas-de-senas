"""Manifiesto de medios y nombres por contenido (D19)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

MANIFEST_NAME = "manifest.json"
HASH_LENGTH = 16

MediaSource = Literal["video", "images", "placeholder"]


class ManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video: str  # "/media/v/<hash>.mp4"
    poster: str  # "/media/p/<hash>.jpg"
    placeholder: bool
    source: MediaSource
    duration: float  # segundos
    frames: int | None = None  # solo `source == "images"`
    source_hash: str | None = None  # SHA-256 de los originales (caché); None en relleno


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    signs: dict[str, ManifestEntry] = {}


def file_hash(path: Path) -> str:
    """Primeros HASH_LENGTH caracteres hexadecimales del SHA-256 del archivo."""
    raise NotImplementedError


def load_manifest(media_dir: Path) -> Manifest:
    """`media_dir/manifest.json`; si no existe, Manifest vacío."""
    raise NotImplementedError


def save_manifest(media_dir: Path, manifest: Manifest) -> None:
    """JSON UTF-8 con LF, claves de `signs` ordenadas e indentación 2 (diffs estables en git)."""
    raise NotImplementedError


def store_media(media_dir: Path, video: Path, poster: Path) -> tuple[str, str]:
    """Mueve un video y su póster ya procesados a `v/<hash>.mp4` y `p/<hash>.jpg`.

    `hash` = file_hash(video) (el póster usa el mismo hash). Devuelve las URL públicas
    («/media/v/…», «/media/p/…»). Si el destino ya existe, no lo reescribe.
    """
    raise NotImplementedError


def remove_orphans(media_dir: Path, manifest: Manifest) -> list[Path]:
    """Borra de `v/` y `p/` los archivos que el manifiesto no referencia; devuelve los borrados."""
    raise NotImplementedError
