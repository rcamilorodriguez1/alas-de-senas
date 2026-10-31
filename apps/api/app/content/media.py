"""Manifiesto de medios y nombres por contenido (D19)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MANIFEST_NAME = "manifest.json"
HASH_LENGTH = 16

MediaSource = Literal["video", "images", "placeholder"]


class ManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video: str = Field(pattern=r"^/media/v/[0-9a-f]{16}\.mp4$")
    poster: str = Field(pattern=r"^/media/p/[0-9a-f]{16}\.jpg$")
    placeholder: bool
    source: MediaSource
    duration: float  # segundos
    frames: int | None = None  # solo `source == "images"`
    source_hash: str | None = None  # SHA-256 de los originales (caché); None en relleno
    label: str | None = None  # solo relleno: palabra dibujada (para no regenerarlo)


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    signs: dict[str, ManifestEntry] = {}


def file_hash(path: Path) -> str:
    """Primeros HASH_LENGTH caracteres hexadecimales del SHA-256 del archivo."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:HASH_LENGTH]


def load_manifest(media_dir: Path) -> Manifest:
    """`media_dir/manifest.json`; si no existe, Manifest vacío."""
    path = media_dir / MANIFEST_NAME
    if not path.exists():
        return Manifest()
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


def save_manifest(media_dir: Path, manifest: Manifest) -> None:
    """JSON UTF-8 con LF, claves de `signs` ordenadas e indentación 2 (diffs estables en git)."""
    media_dir.mkdir(parents=True, exist_ok=True)
    data = manifest.model_dump(mode="json", exclude_none=True)
    data["signs"] = dict(sorted(data["signs"].items()))
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    (media_dir / MANIFEST_NAME).write_text(text, encoding="utf-8", newline="\n")


def store_media(media_dir: Path, video: Path, poster: Path) -> tuple[str, str]:
    """Mueve un video y su póster ya procesados a `v/<hash>.mp4` y `p/<hash>.jpg`.

    `hash` = file_hash(video) (el póster usa el mismo hash). Devuelve las URL públicas
    («/media/v/…», «/media/p/…»). Si el destino ya existe, no lo reescribe.
    """
    digest = file_hash(video)
    targets = (
        (video, media_dir / "v" / f"{digest}.mp4"),
        (poster, media_dir / "p" / f"{digest}.jpg"),
    )
    for source, target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            source.unlink(missing_ok=True)
        else:
            shutil.move(str(source), target)
    return f"/media/v/{digest}.mp4", f"/media/p/{digest}.jpg"


def manifest_exists(media_dir: Path) -> bool:
    return (media_dir / MANIFEST_NAME).is_file()


def remove_orphans(media_dir: Path, manifest: Manifest) -> list[Path]:
    """Borra de `v/` y `p/` los archivos que el manifiesto no referencia; devuelve los borrados."""
    referenced = {
        url.removeprefix("/media/")
        for entry in manifest.signs.values()
        for url in (entry.video, entry.poster)
    }
    removed: list[Path] = []
    for folder in ("v", "p"):
        directory = media_dir / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.is_file() and f"{folder}/{path.name}" not in referenced:
                path.unlink()
                removed.append(path)
    return removed
