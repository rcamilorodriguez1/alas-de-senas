"""Ayudas para las pruebas del pipeline de contenido con el contenido REAL de `content/`.

Lee el CSV con el módulo `csv` de la biblioteca estándar (no con el código de producción) para
que las pruebas no dependan de lo que prueban. Construye un `media_dir` temporal con un
manifiesto completo (una entrada por seña) y archivos vacíos para cada ruta referenciada.
"""

from __future__ import annotations

import csv
import hashlib
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from app.content.media import MANIFEST_NAME, Manifest, ManifestEntry

REPO_ROOT = Path(__file__).resolve().parents[5]
CONTENT_DIR = REPO_ROOT / "content"
CONTENT_FILES = ("curriculum.json", "signs.csv", "conversations.yaml", "intro.json")
CSV_COLUMNS = (
    "slug",
    "word",
    "meaning",
    "how_to",
    "usage_example",
    "category",
    "node",
    "order",
    "motion",
)

Row = dict[str, str]


def copy_content(dst: Path) -> Path:
    """Copia los cuatro archivos de contenido real a `dst` (sin fuentes ni videos)."""
    dst.mkdir(parents=True, exist_ok=True)
    for name in CONTENT_FILES:
        shutil.copyfile(CONTENT_DIR / name, dst / name)
    return dst


def read_rows(content_dir: Path) -> list[Row]:
    with (content_dir / "signs.csv").open(encoding="utf-8-sig", newline="") as fh:
        return [{k: (v or "") for k, v in row.items()} for row in csv.DictReader(fh)]


def write_rows(content_dir: Path, rows: list[Row]) -> None:
    with (content_dir / "signs.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def edit_rows(content_dir: Path, edit: Callable[[list[Row]], list[Row] | None]) -> None:
    rows = read_rows(content_dir)
    result = edit(rows)
    write_rows(content_dir, rows if result is None else result)


def row_of(rows: list[Row], slug: str) -> Row:
    for row in rows:
        if row["slug"] == slug:
            return row
    raise KeyError(slug)


def make_row(slug: str, word: str, category: str, node: str = "", order: str = "0") -> Row:
    return {
        "slug": slug,
        "word": word,
        "meaning": f"Significado de {word}.",
        "how_to": "",
        "usage_example": f"Ejemplo con «{word}».",
        "category": category,
        "node": node,
        "order": order,
        "motion": "",
    }


def real_slugs(content_dir: Path = CONTENT_DIR) -> list[str]:
    return [row["slug"] for row in read_rows(content_dir)]


def digest_for(slug: str) -> str:
    return hashlib.sha256(slug.encode("utf-8")).hexdigest()[:16]


def entry_for(
    slug: str,
    *,
    placeholder: bool = False,
    duration: float = 3.0,
    tag: str = "",
) -> ManifestEntry:
    digest = digest_for(slug + tag)
    return ManifestEntry(
        video=f"/media/v/{digest}.mp4",
        poster=f"/media/p/{digest}.jpg",
        placeholder=placeholder,
        source="placeholder" if placeholder else "video",
        duration=duration,
        source_hash=None if placeholder else digest_for("raw:" + slug + tag),
    )


def media_file(media_dir: Path, url: str) -> Path:
    """«/media/v/x.mp4» → media_dir/v/x.mp4."""
    prefix = "/media/"
    assert url.startswith(prefix)
    return media_dir / url[len(prefix) :]


def write_manifest(media_dir: Path, entries: Mapping[str, ManifestEntry]) -> Manifest:
    manifest = Manifest(signs=dict(entries))
    media_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries.values():
        for url in (entry.video, entry.poster):
            path = media_file(media_dir, url)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
    (media_dir / MANIFEST_NAME).write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def make_media(
    media_dir: Path,
    content_dir: Path = CONTENT_DIR,
    *,
    overrides: Mapping[str, ManifestEntry] | None = None,
    omit: frozenset[str] = frozenset(),
) -> Manifest:
    """Manifiesto con una entrada (video real de 3 s) por cada seña del CSV de `content_dir`."""
    entries = {slug: entry_for(slug) for slug in real_slugs(content_dir) if slug not in omit}
    if overrides:
        entries.update(overrides)
    return write_manifest(media_dir, entries)
