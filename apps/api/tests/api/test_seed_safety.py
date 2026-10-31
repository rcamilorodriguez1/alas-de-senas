"""Revisión del Grupo 2: el seed no escala privilegios y tolera reordenar el currículo."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import bcrypt
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.content.errors import ContentError
from app.content.seed import seed_content
from app.infra.db import get_engine
from app.infra.models import Node, Role, User
from tests.api.test_seed import SEED_TABLES
from tests.unit.content.real_content import CONTENT_DIR, copy_content, make_media

ADMIN_EMAIL = "admin@alasdesenas.test"


def _truncate() -> None:
    preparer = get_engine().dialect.identifier_preparer
    names = ", ".join(preparer.quote(name) for name in SEED_TABLES)
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE TABLE " + names + " RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    _truncate()
    yield
    _truncate()


@pytest.fixture
def media_dir(tmp_path: Path) -> Path:
    path = tmp_path / "media"
    make_media(path, CONTENT_DIR)
    return path


def _seed(content_dir: Path, media_dir: Path, **admin: str) -> None:
    with Session(get_engine()) as session:
        seed_content(session, content_dir, media_dir, **admin)
        session.commit()


def test_no_convierte_en_admin_una_cuenta_de_estudiante(media_dir: Path) -> None:
    with Session(get_engine()) as session:
        session.add(
            User(
                name="Intruso",
                email=ADMIN_EMAIL,
                password_hash=bcrypt.hashpw(b"del-intruso", bcrypt.gensalt(4)).decode(),
            )
        )
        session.commit()
    with pytest.raises(ContentError, match="no es administrador"):
        _seed(CONTENT_DIR, media_dir, admin_email=ADMIN_EMAIL, admin_password="Clave-Segura-1")
    with Session(get_engine()) as session:
        user = session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()
        assert user.role is Role.LEARNER


def test_admin_existente_toma_la_contrasena_del_env(media_dir: Path) -> None:
    _seed(CONTENT_DIR, media_dir, admin_email=ADMIN_EMAIL, admin_password="Primera-Clave-1")
    _seed(CONTENT_DIR, media_dir, admin_email=ADMIN_EMAIL, admin_password="Segunda-Clave-2")
    with Session(get_engine()) as session:
        admin = session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()
    assert admin.role is Role.ADMIN
    assert bcrypt.checkpw(b"Segunda-Clave-2", admin.password_hash.encode())
    assert not bcrypt.checkpw(b"Primera-Clave-1", admin.password_hash.encode())


def test_correo_del_admin_se_normaliza(media_dir: Path) -> None:
    _seed(
        CONTENT_DIR, media_dir, admin_email="  Admin@AlasDeSenas.TEST ", admin_password="Clave-1234"
    )
    with Session(get_engine()) as session:
        assert session.execute(select(User.email)).scalar_one() == ADMIN_EMAIL


def test_reordenar_nodos_y_resembrar_funciona(tmp_path: Path, media_dir: Path) -> None:
    content_dir = copy_content(tmp_path / "content")
    _seed(content_dir, media_dir)

    path = content_dir / "curriculum.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data["modules"][2]["nodes"]  # M3: intercambia Transporte (N3) y Necesidades (N4)
    nodes[2]["order"], nodes[3]["order"] = nodes[3]["order"], nodes[2]["order"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    _seed(content_dir, media_dir)
    with Session(get_engine()) as session:
        assert session.get(Node, "M3-N3") is not None
        orders = dict(session.execute(select(Node.id, Node.order)).tuples().all())
    assert orders["M3-N3"] == 4
    assert orders["M3-N4"] == 3
