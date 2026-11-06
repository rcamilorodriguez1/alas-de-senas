"""La versión de la política que se guarda al registrarse es la que muestra /privacidad (D-037)."""

from __future__ import annotations

from datetime import date

from app.core.config import REPO_ROOT
from app.core.privacy import DATA_POLICY_VERSION

MONTHS = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
PRIVACY_PAGE = REPO_ROOT / "apps" / "web" / "src" / "pages" / "PrivacyPage.tsx"


def test_la_version_es_una_fecha_iso() -> None:
    assert date.fromisoformat(DATA_POLICY_VERSION).isoformat() == DATA_POLICY_VERSION


def test_la_pagina_de_privacidad_muestra_la_misma_version() -> None:
    day = date.fromisoformat(DATA_POLICY_VERSION)
    expected = f"Versión del {day.day} de {MONTHS[day.month - 1]} de {day.year}."

    assert expected in PRIVACY_PAGE.read_text(encoding="utf-8")
