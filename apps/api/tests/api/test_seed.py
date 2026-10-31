"""Tarea 2.7 — `alas db seed` idempotente contra PostgreSQL real (R9.7, R9.8, R9.10, B7, D4).

Cada prueba siembra el contenido REAL de `content/` con un `media_dir` temporal cuyo manifiesto
tiene una entrada por seña. Al terminar se vacían las tablas de contenido y de usuarios.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import bcrypt
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.content.errors import ContentError
from app.content.seed import SeedCounts, seed_content
from app.domain.enums import ExerciseType
from app.domain.exercises.models import parse_payload
from app.infra.db import get_engine
from app.infra.models import (
    Achievement,
    ActivityKind,
    Base,
    Category,
    Exercise,
    Lesson,
    LessonSession,
    Module,
    Node,
    Role,
    SessionAnswer,
    Sign,
    User,
)
from tests.unit.content.real_content import CONTENT_DIR, entry_for, make_media

SEED_TABLES: tuple[str, ...] = (
    "favorites",
    "user_achievements",
    "sign_reviews",
    "streaks",
    "daily_activity",
    "review_answers",
    "review_sessions",
    "session_answers",
    "lesson_sessions",
    "refresh_tokens",
    "users",
    "achievements",
    "exercises",
    "signs",
    "lessons",
    "nodes",
    "categories",
    "modules",
)

ACTIVITY_BY_TYPE: dict[ExerciseType, ActivityKind] = {
    ExerciseType.OBSERVE: ActivityKind.OBSERVE,
    ExerciseType.VIDEO_TO_MEANING: ActivityKind.SELECT,
    ExerciseType.MEANING_TO_VIDEO: ActivityKind.SELECT,
    ExerciseType.MEMORY_MATCH: ActivityKind.SELECT,
    ExerciseType.PRODUCE: ActivityKind.PRODUCE,
    ExerciseType.CONVERSATION: ActivityKind.USE,
    ExerciseType.SPELLING: ActivityKind.USE,
}

ACHIEVEMENT_NECTAR = {
    "FIRST_FLAP": 10,
    "FIRST_LESSON": 10,
    "STREAK_3": 15,
    "STREAK_7": 30,
    "NODE_DONE": 15,
    "GOLDEN_NODE": 20,
    "MODULE_1": 40,
    "SIGNS_50": 40,
    "HUMMINGBIRD_EYE": 30,
}

MOMENT = datetime(2026, 11, 3, 14, 30, tzinfo=UTC)
ADMIN_EMAIL = "admin@alasdesenas.test"
ADMIN_PASSWORD = "Colibri-Admin-2026"


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


def _seed(media_dir: Path, **admin: str) -> SeedCounts:
    with Session(get_engine()) as session:
        counts = seed_content(session, CONTENT_DIR, media_dir, **admin)
        session.commit()
    return counts


def _count(session: Session, model: type[Base]) -> int:
    return session.execute(select(func.count()).select_from(model)).scalar_one()


def _db_counts() -> dict[str, int]:
    with Session(get_engine()) as session:
        return {
            "categories": _count(session, Category),
            "modules": _count(session, Module),
            "nodes": _count(session, Node),
            "lessons": _count(session, Lesson),
            "signs": _count(session, Sign),
            "exercises": _count(session, Exercise),
            "achievements": _count(session, Achievement),
        }


def _exercise_ids() -> list[str]:
    with Session(get_engine()) as session:
        return list(session.execute(select(Exercise.id).order_by(Exercise.id)).scalars())


def _sign(slug: str) -> Sign:
    with Session(get_engine()) as session:
        sign = session.get(Sign, slug)
        assert sign is not None, slug
        return sign


# ---------- Conteos e idempotencia -------------------------------------------------------------


def test_seed_carga_todo_el_contenido(media_dir: Path) -> None:
    counts = _seed(media_dir)
    db = _db_counts()
    assert db["categories"] == 13
    assert db["modules"] == 4
    assert db["nodes"] == 16
    assert db["lessons"] == 48
    assert db["signs"] == 109
    assert db["achievements"] == 9
    assert db["exercises"] > 0
    assert counts == SeedCounts(**db)


def test_solo_modulos_publicados_tienen_lecciones(media_dir: Path) -> None:
    _seed(media_dir)
    with Session(get_engine()) as session:
        rows = session.execute(
            select(Node.module_id, func.count(Lesson.id))
            .join(Lesson, Lesson.node_id == Node.id, isouter=True)
            .group_by(Node.module_id)
            .order_by(Node.module_id)
        ).all()
        m4 = session.get(Module, "M4")
        assert m4 is not None
        assert m4.published is False
        m4_nodes = session.execute(
            select(func.count()).select_from(Node).where(Node.module_id == "M4")
        ).scalar_one()
    assert [(module_id, n) for module_id, n in rows] == [
        ("M1", 16),
        ("M2", 16),
        ("M3", 16),
        ("M4", 0),
    ]
    assert m4_nodes == 4


def test_seed_dos_veces_da_los_mismos_conteos_e_ids(media_dir: Path) -> None:
    """R9.7, B7: cargar dos veces no duplica ni cambia los IDs."""
    first = _seed(media_dir)
    first_db = _db_counts()
    first_ids = _exercise_ids()
    second = _seed(media_dir)
    assert second == first
    assert _db_counts() == first_db
    assert _exercise_ids() == first_ids
    assert len(first_ids) == len(set(first_ids)) == first.exercises


def test_categorias_en_el_orden_de_6_2(media_dir: Path) -> None:
    _seed(media_dir)
    with Session(get_engine()) as session:
        rows = session.execute(select(Category.id, Category.name).order_by(Category.order)).all()
    assert [tuple(r) for r in rows][:4] == [
        ("saludos", "Saludos"),
        ("presentaciones", "Presentaciones"),
        ("cortesia", "Cortesía"),
        ("alfabeto", "Alfabeto"),
    ]
    assert [tuple(r) for r in rows][-1] == ("animales", "Animales")


def test_logros_de_7_9(media_dir: Path) -> None:
    _seed(media_dir)
    with Session(get_engine()) as session:
        rows = session.execute(
            select(Achievement.id, Achievement.nectar_reward).order_by(Achievement.order)
        ).all()
    assert {r[0]: r[1] for r in rows} == ACHIEVEMENT_NECTAR
    assert rows[0][0] == "FIRST_FLAP"


# ---------- Señas ------------------------------------------------------------------------------


def test_senas_toman_los_medios_del_manifiesto(media_dir: Path) -> None:
    _seed(media_dir)
    expected = entry_for("gracias")
    sign = _sign("gracias")
    assert sign.video_path == expected.video
    assert sign.poster_path == expected.poster
    assert sign.is_placeholder is False
    assert sign.media_source == "video"


def test_cambiar_el_manifiesto_y_resembrar_actualiza_la_sena(
    media_dir: Path, tmp_path: Path
) -> None:
    _seed(media_dir)
    changed = entry_for("gracias", placeholder=True, tag=":v2")
    images = entry_for("hola", tag=":v2").model_copy(update={"source": "images", "frames": 3})
    make_media(media_dir, CONTENT_DIR, overrides={"gracias": changed, "hola": images})
    _seed(media_dir)
    gracias = _sign("gracias")
    assert gracias.video_path == changed.video
    assert gracias.poster_path == changed.poster
    assert gracias.is_placeholder is True
    assert gracias.media_source == "placeholder"
    hola = _sign("hola")
    assert hola.video_path == images.video
    assert hola.media_source == "images"
    assert hola.is_placeholder is False
    assert _db_counts()["signs"] == 109


def test_sena_ausente_del_manifiesto_es_content_error(tmp_path: Path) -> None:
    media = tmp_path / "media-incompleto"
    make_media(media, CONTENT_DIR, omit=frozenset({"gracias"}))
    with Session(get_engine()) as session, pytest.raises(ContentError) as info:
        seed_content(session, CONTENT_DIR, media)
    assert "gracias" in str(info.value)


def test_campos_de_las_senas(media_dir: Path) -> None:
    _seed(media_dir)
    hola = _sign("hola")
    assert hola.word == "Hola"
    assert hola.category_id == "saludos"
    assert hola.node_id == "M1-N1"
    assert hola.order == 1
    assert hola.introduced_in_lesson_id == "M1-N1-L1"
    assert hola.motion is None
    como = _sign("como-estas")
    assert como.word == "¿Cómo estás?"
    assert como.normalized_word == "como estas"
    assert _sign("banarse").normalized_word == "bañarse"  # §7.8: la ñ se conserva (B11)
    assert _sign("letra-j").motion == "dynamic"
    assert _sign("letra-a").motion == "static"
    assert _sign("letra-n-tilde").word == "Ñ"
    perro = _sign("perro")
    assert perro.node_id is None
    assert perro.introduced_in_lesson_id is None
    assert perro.how_to is None


def test_introduced_in_lesson_sigue_el_reparto(media_dir: Path) -> None:
    _seed(media_dir)
    assert _sign("buenas-noches").introduced_in_lesson_id == "M1-N1-L2"
    assert _sign("de-nada").introduced_in_lesson_id == "M1-N1-L3"
    assert _sign("letra-f").introduced_in_lesson_id == "M1-N3-L2"
    assert _sign("numero-7").introduced_in_lesson_id == "M2-N3-L3"


# ---------- Ejercicios -------------------------------------------------------------------------


def test_actividad_guardada_segun_el_tipo(media_dir: Path) -> None:
    _seed(media_dir)
    with Session(get_engine()) as session:
        rows = session.execute(
            select(Exercise.id, Exercise.type, Exercise.activity).order_by(Exercise.id)
        ).all()
    assert rows
    for exercise_id, kind, activity in rows:
        assert activity is ACTIVITY_BY_TYPE[kind], exercise_id
    assert {r[2] for r in rows} == set(ActivityKind)
    with get_engine().connect() as conn:
        raw = set(conn.execute(text("SELECT DISTINCT activity::text FROM exercises")).scalars())
    assert raw == {"OBSERVE", "SELECT", "PRODUCE", "USE"}


def _keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [str(k) for k in value] + [k for v in value.values() for k in _keys(v)]
    if isinstance(value, list):
        return [k for item in value for k in _keys(item)]
    return []


def test_payload_jsonb_en_camel_case_valido(media_dir: Path) -> None:
    _seed(media_dir)
    with Session(get_engine()) as session:
        rows = session.execute(select(Exercise).order_by(Exercise.id)).scalars().all()
    assert rows
    for row in rows:
        payload = parse_payload(row.payload)
        assert payload.type == row.type, row.id
        assert all("_" not in key for key in _keys(row.payload)), row.id
        sign_id = getattr(payload, "sign_id", None)
        if sign_id is not None:
            assert row.sign_id == sign_id, row.id
    vtm = next(r for r in rows if r.type is ExerciseType.VIDEO_TO_MEANING)
    assert {"type", "signId", "optionIds", "correctId"} <= set(vtm.payload)


def test_ejercicios_solo_de_modulos_publicados(media_dir: Path) -> None:
    _seed(media_dir)
    ids = _exercise_ids()
    assert ids
    assert {i.split("-", 1)[0] for i in ids} == {"M1", "M2", "M3"}


# ---------- Progreso intacto -------------------------------------------------------------------


def test_resembrar_no_borra_el_progreso(media_dir: Path) -> None:
    _seed(media_dir)
    first_exercise = _exercise_ids()[0]
    with Session(get_engine()) as session:
        user = User(name="Ana", email="ana@alasdesenas.test", password_hash="x" * 60)
        session.add(user)
        session.flush()
        lesson_session = LessonSession(
            user_id=user.id, lesson_id=first_exercise.rsplit("-", 1)[0], started_at=MOMENT
        )
        session.add(lesson_session)
        session.flush()
        session.add(
            SessionAnswer(
                session_id=lesson_session.id,
                exercise_id=first_exercise,
                answer={"seen": True},
                correct=True,
                answered_at=MOMENT,
            )
        )
        session.commit()
        user_id, session_id = user.id, lesson_session.id

    _seed(media_dir)

    with Session(get_engine()) as session:
        assert session.get(User, user_id) is not None
        stored = session.get(LessonSession, session_id)
        assert stored is not None
        assert stored.started_at == MOMENT
        answer = session.get(SessionAnswer, (session_id, first_exercise))
        assert answer is not None
        assert answer.correct is True
        assert answer.answered_at == MOMENT


# ---------- Administrador opcional -------------------------------------------------------------


def test_sin_datos_de_administrador_no_crea_usuarios(media_dir: Path) -> None:
    _seed(media_dir)
    with Session(get_engine()) as session:
        assert _count(session, User) == 0


def test_administrador_opcional(media_dir: Path) -> None:
    _seed(media_dir, admin_email=ADMIN_EMAIL, admin_password=ADMIN_PASSWORD)
    with Session(get_engine()) as session:
        admins = session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalars().all()
    assert len(admins) == 1
    admin = admins[0]
    assert admin.role is Role.ADMIN
    assert admin.password_hash != ADMIN_PASSWORD
    assert bcrypt.checkpw(ADMIN_PASSWORD.encode("utf-8"), admin.password_hash.encode("utf-8"))
    assert admin.password_hash.startswith("$2b$12$")  # costo 12


def test_repetir_el_administrador_no_lo_duplica(media_dir: Path) -> None:
    _seed(media_dir, admin_email=ADMIN_EMAIL, admin_password=ADMIN_PASSWORD)
    _seed(media_dir, admin_email=ADMIN_EMAIL, admin_password=ADMIN_PASSWORD)
    with Session(get_engine()) as session:
        assert _count(session, User) == 1
        admin = session.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()
    assert admin.role is Role.ADMIN
