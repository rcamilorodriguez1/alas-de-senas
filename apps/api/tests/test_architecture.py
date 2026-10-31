"""Tarea 0.5 — el dominio es Python puro: no importa frameworks ni infraestructura (§4, §15)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DOMAIN_DIR = Path(__file__).resolve().parents[1] / "app" / "domain"
FORBIDDEN = ("fastapi", "sqlalchemy", "starlette", "pydantic_settings")


def _is_forbidden(module: str) -> bool:
    root = module.split(".", 1)[0]
    return root in FORBIDDEN


def forbidden_imports(source: str, filename: str = "<memoria>") -> list[str]:
    """Devuelve los módulos prohibidos importados en `source` (import y from-import)."""
    tree = ast.parse(source, filename=filename)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names if _is_forbidden(alias.name))
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module is not None
            and _is_forbidden(node.module)
        ):
            found.append(node.module)
    return found


def _domain_files() -> list[Path]:
    return sorted(DOMAIN_DIR.rglob("*.py"))


# --- El detector funciona ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from sqlalchemy.orm import Session\n", ["sqlalchemy.orm"]),
        ("import fastapi\n", ["fastapi"]),
        ("import starlette.requests as req\n", ["starlette.requests"]),
        ("from pydantic_settings import BaseSettings\n", ["pydantic_settings"]),
        ("import os, sqlalchemy\n", ["sqlalchemy"]),
        ("def f() -> None:\n    from fastapi import Depends\n", ["fastapi"]),
        (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import sqlalchemy\n",
            ["sqlalchemy"],
        ),
    ],
)
def test_detector_marca_imports_prohibidos(source: str, expected: list[str]) -> None:
    assert forbidden_imports(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "import dataclasses\n",
        "from datetime import date, datetime\n",
        "from pydantic import BaseModel\n",
        "import fastapi_like_but_not\n",
        "from . import dates\n",
        "from .policies import scoring\n",
        "text = 'import fastapi'\n",
    ],
)
def test_detector_no_marca_imports_permitidos(source: str) -> None:
    assert forbidden_imports(source) == []


# --- El dominio real cumple la regla ----------------------------------------------------------


def test_el_paquete_de_dominio_existe() -> None:
    assert DOMAIN_DIR.is_dir()
    assert (DOMAIN_DIR / "__init__.py").is_file()


def test_el_dominio_no_importa_frameworks_ni_infraestructura() -> None:
    files = _domain_files()
    assert files, "No se encontraron archivos en app/domain"

    violations = {
        str(path.relative_to(DOMAIN_DIR)): found
        for path in files
        if (found := forbidden_imports(path.read_text(encoding="utf-8"), str(path)))
    }

    assert violations == {}
