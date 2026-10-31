"""Lector de `content/signs.csv` (§6.2, §6.6, B12)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    raise NotImplementedError
