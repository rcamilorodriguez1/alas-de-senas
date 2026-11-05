"""Configuración de las pruebas E2E (Playwright para Python, §15). Las ejecuta `alas e2e`."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass

import pytest

from app.core.config import REPO_ROOT

VIEWPORT = {"width": 1366, "height": 768}  # §15: ventana de portátil


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, object]) -> dict[str, object]:
    return {**browser_context_args, "viewport": VIEWPORT, "locale": "es-CO"}


@dataclass(frozen=True)
class SignMaps:
    """Lo que la prueba sabe del repositorio (nunca de la API, B89): video → seña → palabra."""

    slugs_by_video: dict[str, set[str]]
    word_by_slug: dict[str, str]
    slugs_by_word: dict[str, set[str]]

    def words_for_video(self, src: str) -> set[str]:
        return {self.word_by_slug[slug] for slug in self.slugs_by_video.get(src, set())}


@pytest.fixture(scope="session")
def sign_maps() -> SignMaps:
    manifest = json.loads(
        (REPO_ROOT / "apps" / "web" / "public" / "media" / "manifest.json").read_text("utf-8")
    )
    slugs_by_video: dict[str, set[str]] = defaultdict(set)
    for slug, entry in manifest["signs"].items():
        slugs_by_video[str(entry["video"])].add(slug)
    with (REPO_ROOT / "content" / "signs.csv").open(encoding="utf-8", newline="") as handle:
        word_by_slug = {row["slug"]: row["word"] for row in csv.DictReader(handle)}
    slugs_by_word: dict[str, set[str]] = defaultdict(set)
    for slug, word in word_by_slug.items():
        slugs_by_word[word].add(slug)
    return SignMaps(dict(slugs_by_video), word_by_slug, dict(slugs_by_word))
