"""Lector de `content/signs.csv` (§6.2, §6.6, B12)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from app.content.errors import ContentError

COLUMNS = (
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
MOJIBAKE_MARKERS = ("Ã", "Â", "�")
ENCODING_MESSAGE = (
    'signs.csv parece guardado con codificación incorrecta (se ve "{sample}"). '
    'Guárdalo como "CSV UTF-8" o expórtalo desde Google Sheets.'
)


@dataclass(frozen=True, slots=True)
class SignRow:
    slug: str
    word: str
    meaning: str
    how_to: str | None  # vacío → None
    usage_example: str
    category: str
    node: str | None  # vacío → None (solo diccionario)
    order: int  # vacío → 0
    motion: str | None  # vacío → None; el valor se valida en `alas content check`
    line: int  # número de fila en el archivo (la cabecera es la 1)


def read_signs_csv(path: Path) -> list[SignRow]:
    """Lee con `utf-8-sig` (quita el BOM) y `csv.DictReader`; recorta espacios de cada celda.

    Lanza ContentError: con ENCODING_MESSAGE si el archivo no es UTF-8 válido o si alguna celda
    contiene un marcador de MOJIBAKE_MARKERS (`sample` = el fragmento sospechoso, p. ej. «Ã¡»);
    si falta alguna columna de COLUMNS (`signs.csv no tiene la columna "motion".`); si `order` no
    es un entero (`signs.csv fila 12: "order" debe ser un número entero.`).
    """
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ContentError(ENCODING_MESSAGE.format(sample=_undecodable_sample(raw))) from exc
    sample = _mojibake_sample(text)
    if sample is not None:
        raise ContentError(ENCODING_MESSAGE.format(sample=sample))

    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = [name.strip() for name in reader.fieldnames or []]
    for column in COLUMNS:
        if column not in header:
            raise ContentError(f'signs.csv no tiene la columna "{column}".')

    rows: list[SignRow] = []
    for line, raw_row in enumerate(reader, start=2):
        cells = {
            (key or "").strip(): (value or "").strip()
            for key, value in raw_row.items()
            if isinstance(value, str) or value is None
        }
        order_text = cells.get("order", "")
        try:
            order = int(order_text) if order_text else 0
        except ValueError as exc:
            raise ContentError(
                f'signs.csv fila {line}: "order" debe ser un número entero.'
            ) from exc
        rows.append(
            SignRow(
                slug=cells.get("slug", ""),
                word=cells.get("word", ""),
                meaning=cells.get("meaning", ""),
                how_to=cells.get("how_to") or None,
                usage_example=cells.get("usage_example", ""),
                category=cells.get("category", ""),
                node=cells.get("node") or None,
                order=order,
                motion=cells.get("motion") or None,
                line=line,
            )
        )
    return rows


def _mojibake_sample(text: str) -> str | None:
    """Fragmento con el primer marcador de mojibake (el marcador y el carácter siguiente)."""
    positions = [text.find(m) for m in MOJIBAKE_MARKERS if m in text]
    if not positions:
        return None
    start = min(positions)
    return text[start : start + 2]


def _undecodable_sample(raw: bytes) -> str:
    # Lo que vería alguien que abre el archivo como UTF-8: los bytes inválidos como «�».
    text = raw.decode("utf-8", errors="replace")
    return _mojibake_sample(text) or "�"
