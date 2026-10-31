"""Normalización de texto para búsquedas y distancia de Levenshtein (§7.8)."""

from __future__ import annotations

import re
import unicodedata

_PUNCT = re.compile(r"[¿?¡!.,;:]")
_SPACES = re.compile(r"\s+")


def normalize_text(s: str) -> str:
    """Minúsculas, sin tildes ni signos de puntuación, espacios simples; conserva la ñ."""
    s = unicodedata.normalize("NFD", s.strip().lower())
    s = s.replace("n\u0303", "\u00f1")  # protege la ñ (escapes explícitos a propósito)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = _PUNCT.sub("", s)
    return _SPACES.sub(" ", s).strip()


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]
