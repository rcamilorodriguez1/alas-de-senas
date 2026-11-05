"""Tarea 11.5 — usuario de demostración `alas db seed-demo` (§17.4, R10.9, B83, B84).

`app.content.demo.seed_demo(settings, clock, *, reset=False, allow_production=False)` crea, con
los servicios reales y fechas relativas al «hoy» del `clock` (10:00 de Bogotá de cada día):

- hace 5 días: M1-N1 L1-L4 con 100 % en el reto (nodo dorado);
- hace 4 días: M1-N2 L1-L4;
- hace 3 días: M1-N3 L1-L4;
- hace 2 días: M1-N4 L1-L2 y un repaso;
- ayer: M1-N4 L3-L4 con 3 errores en 3 letras (aprueba).

Resultado hoy: módulo 1 completo, racha 5 en riesgo, repaso pendiente con las 3 letras falladas
ayer, M2-N1-L1 disponible, logros FIRST_FLAP, FIRST_LESSON, STREAK_3, NODE_DONE, GOLDEN_NODE y
MODULE_1, vidas llenas. El usuario queda con `is_demo = true`.

El módulo se importa en tiempo de ejecución (pruebas primero): mientras no exista, cada prueba
falla con `ModuleNotFoundError: app.content.demo`.
"""

from __future__ import annotations

import importlib
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from types import ModuleType
from typing import Protocol

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.core.clock import get_clock
from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limits
from app.domain.dates import TZ, add_days, to_local_day
from app.domain.enums import ProgressStatus
from app.infra.db import get_engine
from app.infra.models import (
    DailyActivity,
    Exercise,
    LessonSession,
    ReviewSession,
    SessionAnswer,
    Sign,
    SignReview,
    User,
    UserAchievement,
)
from app.services.curriculum_service import CurriculumService
from app.services.gamification_service import GamificationService
from app.services.review_service import ReviewService
from tests.api.helpers import complete_lesson, register_user
from tests.fakes import FakeClock

pytestmark = pytest.mark.usefixtures("seeded_content")

# 2026-11-04 15:00 UTC = 10:00 en Bogotá (UTC-5, sin horario de verano).
TODAY = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)
TODAY_DAY = "2026-11-04"

EXPECTED_ACHIEVEMENTS = {
    "FIRST_FLAP",
    "FIRST_LESSON",
    "STREAK_3",
    "NODE_DONE",
    "GOLDEN_NODE",
    "MODULE_1",
}
M1_LESSONS = {f"M1-N{n}-L{lesson}" for n in range(1, 5) for lesson in range(1, 5)}

# Días antes de hoy en que se aprueba cada lección (§17.4).
LESSON_OFFSETS: dict[str, int] = {
    **{f"M1-N1-L{i}": -5 for i in range(1, 5)},
    **{f"M1-N2-L{i}": -4 for i in range(1, 5)},
    **{f"M1-N3-L{i}": -3 for i in range(1, 5)},
    "M1-N4-L1": -2,
    "M1-N4-L2": -2,
    "M1-N4-L3": -1,
    "M1-N4-L4": -1,
}
TEN_AM = time(10, 0)

runner = CliRunner()
WIDE = {"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"}


# ---------------------------------------------------------------- acceso al módulo


class DemoResultLike(Protocol):
    @property
    def created(self) -> bool: ...

    @property
    def email(self) -> str: ...


def demo_module() -> ModuleType:
    # Se importa en tiempo de ejecución: el módulo aún no existe (pruebas primero).
    return importlib.import_module("app.content.demo")


def seed(settings: Settings, clock: FakeClock, *, reset: bool = False) -> DemoResultLike:
    result: DemoResultLike = demo_module().seed_demo(settings, clock, reset=reset)
    return result


def dev_password() -> str:
    value = demo_module().DEMO_DEV_PASSWORD
    assert isinstance(value, str)
    return value


# ---------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def reset_limits() -> Iterator[None]:
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def settings() -> Settings:
    """Configuración de prueba sin DEMO_PASSWORD: usa la contraseña de desarrollo."""
    return get_settings().model_copy(update={"demo_password": None})


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(TODAY)


@pytest.fixture
def api_clock(client: TestClient, clock: FakeClock) -> Iterator[FakeClock]:
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_clock] = lambda: clock
    yield clock
    app.dependency_overrides.pop(get_clock, None)


# ---------------------------------------------------------------- consultas del estado


def demo_user(settings: Settings) -> User:
    with Session(get_engine()) as session:
        user = session.execute(
            select(User).where(User.email == settings.demo_email)
        ).scalar_one_or_none()
        assert user is not None, "No se creó el usuario de demostración"
        session.expunge(user)
        return user


def local(moment: datetime) -> datetime:
    assert moment.tzinfo is not None
    return moment.astimezone(TZ)


@dataclass(frozen=True)
class DemoSnapshot:
    """Cifras del estado de la demo que no dependen del id del usuario."""

    streak_current: int
    streak_longest: int
    at_risk: bool
    hearts: int
    total_xp: int
    nectar: int
    passed_lessons: frozenset[str]
    golden_nodes: frozenset[str]
    achievements: frozenset[str]
    queue_words: tuple[str, ...]
    queue_due: int
    activity_days: tuple[str, ...]
    lesson_sessions: int
    review_sessions: int


def snapshot(settings: Settings, clock: FakeClock) -> tuple[uuid.UUID, DemoSnapshot]:
    user = demo_user(settings)
    with Session(get_engine()) as session:
        attached = session.get(User, user.id)
        assert attached is not None
        stats = GamificationService(session, clock, settings).get_stats(attached)
        path = CurriculumService(session).get_learning_path(user.id)
        queue = ReviewService(session, clock, settings).get_queue(user.id)
        passed = session.execute(
            select(LessonSession.lesson_id)
            .where(LessonSession.user_id == user.id, LessonSession.passed.is_(True))
            .order_by(LessonSession.lesson_id)
        ).scalars()
        achievements = session.execute(
            select(UserAchievement.achievement_id)
            .where(UserAchievement.user_id == user.id)
            .order_by(UserAchievement.achievement_id)
        ).scalars()
        days = session.execute(
            select(DailyActivity.day)
            .where(DailyActivity.user_id == user.id)
            .order_by(DailyActivity.day)
        ).scalars()
        lesson_count = session.execute(
            select(func.count()).select_from(LessonSession).where(LessonSession.user_id == user.id)
        ).scalar_one()
        review_count = session.execute(
            select(func.count()).select_from(ReviewSession).where(ReviewSession.user_id == user.id)
        ).scalar_one()
        golden = frozenset(
            node.id
            for module in path.modules
            for node in module.nodes
            if node.status is ProgressStatus.GOLDEN
        )
        return user.id, DemoSnapshot(
            streak_current=stats.streak.current,
            streak_longest=stats.streak.longest,
            at_risk=stats.streak.at_risk,
            hearts=stats.hearts.current,
            total_xp=stats.total_xp,
            nectar=stats.nectar,
            passed_lessons=frozenset(passed),
            golden_nodes=golden,
            achievements=frozenset(achievements),
            queue_words=tuple(sorted(sign.word for sign in queue.signs)),
            queue_due=queue.due,
            activity_days=tuple(days),
            lesson_sessions=lesson_count,
            review_sessions=review_count,
        )


def failed_letters(
    user_id: uuid.UUID, *, scored: bool = True
) -> list[tuple[str, str, LessonSession]]:
    """(sign_id, palabra, sesión) de cada respuesta incorrecta en lecciones del usuario.

    `scored=True`: los «errores» de §17.4 (cuentan en el puntaje y quitan vida). `scored=False`:
    autoevaluaciones «Necesito repasar», que no son errores (D-034)."""
    with Session(get_engine()) as session:
        rows = session.execute(
            select(Exercise.sign_id, LessonSession)
            .join(SessionAnswer, SessionAnswer.exercise_id == Exercise.id)
            .join(LessonSession, LessonSession.id == SessionAnswer.session_id)
            .where(
                LessonSession.user_id == user_id,
                SessionAnswer.correct.is_(False),
                Exercise.scored.is_(scored),
            )
            .order_by(Exercise.id)
        ).all()
        result: list[tuple[str, str, LessonSession]] = []
        for sign_id, lesson_session in rows:
            assert sign_id is not None, "Cada error de la demo debe ser sobre una seña"
            sign = session.get(Sign, sign_id)
            assert sign is not None
            result.append((sign_id, sign.word, lesson_session))
        session.expunge_all()
        return result


def day_offset(clock: FakeClock, offset: int) -> str:
    return add_days(to_local_day(clock.now()), offset)


# ================================================================ estado tras seed_demo


def test_seed_demo_crea_el_usuario_de_demostracion(settings: Settings, clock: FakeClock) -> None:
    result = seed(settings, clock)

    assert result.created is True
    assert result.email == settings.demo_email
    user = demo_user(settings)
    assert user.is_demo is True
    assert user.email == "demo@alasdesenas.co"


def test_demo_inicia_sesion_con_la_contrasena_de_desarrollo(
    client: TestClient, api_clock: FakeClock, settings: Settings
) -> None:
    seed(settings, api_clock)

    response = client.post(
        "/api/auth/login", json={"email": settings.demo_email, "password": dev_password()}
    )

    assert response.status_code == 200, response.text
    assert dev_password() == "demo-alas-2026"


def test_demo_usa_demo_password_si_esta_configurada(
    client: TestClient, api_clock: FakeClock
) -> None:
    custom = get_settings().model_copy(update={"demo_password": "Clave-De-Demo-Ñandú-9"})
    seed(custom, api_clock)

    ok = client.post(
        "/api/auth/login",
        json={"email": custom.demo_email, "password": "Clave-De-Demo-Ñandú-9"},
    )
    default = client.post(
        "/api/auth/login", json={"email": custom.demo_email, "password": dev_password()}
    )

    assert ok.status_code == 200, ok.text
    assert default.status_code == 401


def test_racha_5_en_riesgo_sin_actividad_hoy(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    _, state = snapshot(settings, clock)

    assert state.streak_current == 5
    assert state.streak_longest == 5
    assert state.at_risk is True


def test_no_hay_actividad_hoy(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        attached = session.get(User, user.id)
        assert attached is not None
        stats = GamificationService(session, clock, settings).get_stats(attached)
    assert stats.today.seconds == 0
    assert stats.today.xp == 0


def test_actividad_diaria_en_los_5_dias_anteriores(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        rows = {
            row.day: row
            for row in session.execute(
                select(DailyActivity)
                .where(DailyActivity.user_id == user.id)
                .order_by(DailyActivity.day)
            ).scalars()
        }

    expected = ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02", "2026-11-03"]
    assert sorted(rows) == expected
    assert all(rows[day].lessons >= 1 for day in expected)
    assert rows["2026-11-02"].reviews >= 1  # hace 2 días: un repaso


def test_16_lecciones_de_m1_aprobadas_una_vez_cada_una(
    settings: Settings, clock: FakeClock
) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        sessions = list(
            session.execute(
                select(LessonSession)
                .where(LessonSession.user_id == user.id)
                .order_by(LessonSession.lesson_id)
            ).scalars()
        )

    assert {s.lesson_id for s in sessions} == M1_LESSONS
    assert len(sessions) == 16
    assert all(s.passed is True and s.completed_at is not None for s in sessions)


def test_lecciones_en_su_dia_desde_las_10_de_bogota(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        sessions = list(
            session.execute(
                select(LessonSession)
                .where(LessonSession.user_id == user.id)
                .order_by(LessonSession.lesson_id)
            ).scalars()
        )

    for record in sessions:
        expected_day = day_offset(clock, LESSON_OFFSETS[record.lesson_id])
        assert record.completed_at is not None
        started = local(record.started_at)
        completed = local(record.completed_at)
        assert started.date().isoformat() == expected_day, record.lesson_id
        assert completed.date().isoformat() == expected_day, record.lesson_id
        assert started.time() >= TEN_AM, record.lesson_id
        assert completed >= started, record.lesson_id
        assert record.completed_at < clock.now()


def test_lecciones_se_aprueban_en_orden_cronologico(settings: Settings, clock: FakeClock) -> None:
    """Las lecciones se completan en el orden de la ruta (los servicios reales lo exigen)."""
    seed(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        ordered = list(
            session.execute(
                select(LessonSession.lesson_id)
                .where(LessonSession.user_id == user.id)
                .order_by(LessonSession.completed_at, LessonSession.lesson_id)
            ).scalars()
        )
    assert ordered == sorted(M1_LESSONS)


def test_reto_de_m1_n1_con_100_y_nodo_dorado(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        challenge = session.execute(
            select(LessonSession).where(
                LessonSession.user_id == user.id, LessonSession.lesson_id == "M1-N1-L4"
            )
        ).scalar_one()
    _, state = snapshot(settings, clock)

    assert challenge.score == 100
    assert "M1-N1" in state.golden_nodes


def test_ruta_modulo_1_completo_y_m2_n1_l1_disponible(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        path = CurriculumService(session).get_learning_path(user.id)

    modules = {module.id: module for module in path.modules}
    m1 = modules["M1"]
    assert m1.status is ProgressStatus.COMPLETED
    assert m1.progress == 100
    done = {ProgressStatus.COMPLETED, ProgressStatus.GOLDEN}
    assert all(node.status in done for node in m1.nodes)
    assert all(lesson.status in done for node in m1.nodes for lesson in node.lessons)

    m2_n1 = next(node for node in modules["M2"].nodes if node.id == "M2-N1")
    lessons = {lesson.id: lesson.status for lesson in m2_n1.lessons}
    assert lessons["M2-N1-L1"] is ProgressStatus.AVAILABLE
    assert lessons["M2-N1-L2"] is ProgressStatus.LOCKED


def test_ayer_3_errores_en_3_letras_distintas(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    failures = failed_letters(user.id)
    yesterday = day_offset(clock, -1)

    assert len(failures) == 3
    assert len({sign_id for sign_id, _, _ in failures}) == 3
    with Session(get_engine()) as session:
        for sign_id, _, lesson_session in failures:
            sign = session.get(Sign, sign_id)
            assert sign is not None
            assert sign.category_id == "alfabeto", sign_id
            assert lesson_session.lesson_id in {"M1-N4-L3", "M1-N4-L4"}
            assert to_local_day(lesson_session.started_at) == yesterday


def test_hace_3_dias_un_necesito_repasar_hace_posible_el_repaso_de_hace_2_dias(
    settings: Settings, clock: FakeClock
) -> None:
    """Con todo acertado ninguna seña vence hace 2 días (§7.7: cada lección del día la refuerza),
    así que el repaso de §17.4 sale de un «Necesito repasar» (sin puntaje) hace 3 días (D-034)."""
    seed(settings, clock)
    user = demo_user(settings)
    self_checks = failed_letters(user.id, scored=False)

    assert len(self_checks) == 1
    sign_id, _, lesson_session = self_checks[0]
    assert to_local_day(lesson_session.started_at) == day_offset(clock, -3)
    assert lesson_session.passed is True
    with Session(get_engine()) as session:
        sign = session.get(Sign, sign_id)
        assert sign is not None
        assert sign.category_id == "alfabeto"
        assert lesson_session.hearts_lost == 0  # una autoevaluación nunca quita vidas
        reviewed = session.execute(
            select(ReviewSession).where(ReviewSession.user_id == user.id)
        ).scalar_one()
        assert to_local_day(reviewed.started_at) == day_offset(clock, -2)
        assert sign_id in {str(item.get("signId")) for item in reviewed.items}


def test_cola_de_repaso_de_hoy_incluye_las_3_letras_falladas_ayer(
    settings: Settings, clock: FakeClock
) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    failures = failed_letters(user.id)
    _, state = snapshot(settings, clock)

    words = {word for _, word, _ in failures}
    assert len(words) == 3
    assert words <= set(state.queue_words)
    assert len(state.queue_words) <= 15
    assert state.queue_due >= 3

    with Session(get_engine()) as session:
        for sign_id, _, _ in failures:
            review = session.get(SignReview, (user.id, sign_id))
            assert review is not None, sign_id
            assert review.strength == 0
            assert review.next_review_day == TODAY_DAY
            assert to_local_day(review.last_seen_at) == day_offset(clock, -1)


def test_un_repaso_completado_hace_2_dias(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        reviews = list(
            session.execute(
                select(ReviewSession)
                .where(ReviewSession.user_id == user.id)
                .order_by(ReviewSession.started_at)
            ).scalars()
        )

    assert len(reviews) == 1
    review = reviews[0]
    assert review.completed_at is not None
    assert review.result is not None
    assert review.total is not None and review.total >= 1
    two_days_ago = day_offset(clock, -2)
    assert local(review.started_at).date().isoformat() == two_days_ago
    assert local(review.completed_at).date().isoformat() == two_days_ago
    assert local(review.started_at).time() >= TEN_AM


def test_vidas_llenas_hoy(settings: Settings, clock: FakeClock) -> None:
    """Los 3 errores de ayer quitaron vidas, pero ya se recargaron (§7.10, D24)."""
    seed(settings, clock)
    _, state = snapshot(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        attached = session.get(User, user.id)
        assert attached is not None
        stats = GamificationService(session, clock, settings).get_stats(attached)

    assert state.hearts == 5
    assert stats.hearts.max == 5
    assert stats.hearts.next_heart_at is None


def test_exactamente_los_6_logros_de_la_demo(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    _, state = snapshot(settings, clock)
    user = demo_user(settings)
    with Session(get_engine()) as session:
        unlocked_at = list(
            session.execute(
                select(UserAchievement.unlocked_at)
                .where(UserAchievement.user_id == user.id)
                .order_by(UserAchievement.achievement_id)
            ).scalars()
        )

    assert state.achievements == EXPECTED_ACHIEVEMENTS
    assert all(moment < clock.now() for moment in unlocked_at)


def test_estado_visible_por_la_api_con_el_reloj_de_hoy(
    client: TestClient, api_clock: FakeClock, settings: Settings
) -> None:
    """Lo que ve el usuario al iniciar sesión el día de la sustentación (§17.3)."""
    seed(settings, api_clock)
    login = client.post(
        "/api/auth/login", json={"email": settings.demo_email, "password": dev_password()}
    )
    assert login.status_code == 200, login.text
    token = login.json()["accessToken"]
    assert isinstance(token, str)
    headers = {"Authorization": f"Bearer {token}"}

    stats = client.get("/api/gamification/stats", headers=headers)
    queue = client.get("/api/reviews/queue", headers=headers)
    achievements = client.get("/api/gamification/achievements", headers=headers)

    assert stats.status_code == 200, stats.text
    assert stats.json()["streak"]["current"] == 5
    assert stats.json()["streak"]["atRisk"] is True
    assert stats.json()["hearts"]["current"] == 5
    assert queue.status_code == 200, queue.text
    assert queue.json()["due"] >= 3
    assert achievements.status_code == 200, achievements.text
    unlocked = {a["id"] for a in achievements.json() if a["unlockedAt"] is not None}
    assert unlocked == EXPECTED_ACHIEVEMENTS


def test_todas_las_fechas_de_negocio_son_anteriores_a_ahora(
    settings: Settings, clock: FakeClock
) -> None:
    seed(settings, clock)
    user = demo_user(settings)
    now = clock.now()
    with Session(get_engine()) as session:
        answered = list(
            session.execute(
                select(SessionAnswer.answered_at)
                .join(LessonSession, LessonSession.id == SessionAnswer.session_id)
                .where(LessonSession.user_id == user.id)
                .order_by(SessionAnswer.answered_at)
            ).scalars()
        )
        seen = list(
            session.execute(
                select(SignReview.last_seen_at)
                .where(SignReview.user_id == user.id)
                .order_by(SignReview.sign_id)
            ).scalars()
        )
    assert answered
    assert all(moment < now for moment in answered)
    assert all(moment < now for moment in seen)
    first_day = date.fromisoformat(day_offset(clock, -5))
    assert all(local(moment).date() >= first_day for moment in answered)


# ================================================================ repetición y --reset


def test_segunda_llamada_sin_reset_no_toca_nada(settings: Settings, clock: FakeClock) -> None:
    seed(settings, clock)
    first_id, before = snapshot(settings, clock)

    again = seed(settings, clock)
    second_id, after = snapshot(settings, clock)

    assert again.created is False
    assert again.email == settings.demo_email
    assert second_id == first_id
    assert after == before


def test_dos_ejecuciones_con_reset_dan_el_mismo_estado(
    settings: Settings, clock: FakeClock
) -> None:
    first = seed(settings, clock, reset=True)
    first_id, before = snapshot(settings, clock)

    second = seed(settings, clock, reset=True)
    second_id, after = snapshot(settings, clock)

    assert first.created is True
    assert second.created is True
    assert second_id != first_id
    assert after == before
    with Session(get_engine()) as session:
        leftovers = session.execute(
            select(func.count()).select_from(LessonSession).where(LessonSession.user_id == first_id)
        ).scalar_one()
        old_user = session.get(User, first_id)
    assert leftovers == 0
    assert old_user is None


def test_reset_sin_usuario_previo_lo_crea(settings: Settings, clock: FakeClock) -> None:
    result = seed(settings, clock, reset=True)
    _, state = snapshot(settings, clock)

    assert result.created is True
    assert state.streak_current == 5
    assert state.passed_lessons == M1_LESSONS


def test_reset_no_toca_a_otros_usuarios(
    client: TestClient, settings: Settings, clock: FakeClock
) -> None:
    _, other_id = register_user(client, "ana@ejemplo.com")
    complete_lesson(other_id, "M1-N1-L1", 90, True)
    other_uuid = uuid.UUID(other_id)

    def other_state() -> tuple[str, bool, int, int, int, int]:
        with Session(get_engine()) as session:
            user = session.get(User, other_uuid)
            assert user is not None
            sessions = session.execute(
                select(func.count())
                .select_from(LessonSession)
                .where(LessonSession.user_id == other_uuid)
            ).scalar_one()
            achievements = session.execute(
                select(func.count())
                .select_from(UserAchievement)
                .where(UserAchievement.user_id == other_uuid)
            ).scalar_one()
            return (user.email, user.is_demo, user.total_xp, user.nectar, sessions, achievements)

    before = other_state()
    seed(settings, clock)
    seed(settings, clock, reset=True)
    after = other_state()

    assert after == before
    assert before[1] is False
    assert before[4] == 1


# ================================================================ fechas relativas a hoy


def test_con_otro_hoy_las_fechas_se_mueven_con_el(settings: Settings) -> None:
    """B83: la demo se calcula respecto al día en que se ejecuta, no a una fecha fija."""
    later = FakeClock(TODAY + timedelta(days=7))  # 2026-11-11 10:00 en Bogotá
    seed(settings, later)
    user = demo_user(settings)
    _, state = snapshot(settings, later)

    assert state.activity_days == (
        "2026-11-06",
        "2026-11-07",
        "2026-11-08",
        "2026-11-09",
        "2026-11-10",
    )
    assert state.streak_current == 5
    assert state.at_risk is True
    assert state.hearts == 5
    with Session(get_engine()) as session:
        challenge = session.execute(
            select(LessonSession).where(
                LessonSession.user_id == user.id, LessonSession.lesson_id == "M1-N1-L4"
            )
        ).scalar_one()
    assert local(challenge.started_at).date().isoformat() == "2026-11-06"


def test_hoy_casi_a_medianoche_en_bogota_usa_el_dia_local(settings: Settings) -> None:
    """2026-11-05 04:30 UTC es todavía 2026-11-04 (23:30) en Bogotá: «hoy» es el 4."""
    late = FakeClock(datetime(2026, 11, 5, 4, 30, tzinfo=UTC))
    seed(settings, late)
    _, state = snapshot(settings, late)

    assert state.activity_days == (
        "2026-10-30",
        "2026-10-31",
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    )
    assert state.streak_current == 5
    assert state.at_risk is True


def test_hoy_temprano_en_la_manana_tambien_deja_la_demo_lista(settings: Settings) -> None:
    """A las 06:00 de Bogotá (antes de las 10:00 simuladas) nada queda en el futuro."""
    early = FakeClock(datetime(2026, 11, 4, 11, 0, tzinfo=UTC))
    seed(settings, early)
    user = demo_user(settings)
    _, state = snapshot(settings, early)

    assert state.streak_current == 5
    assert state.at_risk is True
    assert state.hearts == 5
    with Session(get_engine()) as session:
        latest = session.execute(
            select(func.max(LessonSession.completed_at)).where(LessonSession.user_id == user.id)
        ).scalar_one()
    assert latest is not None
    assert latest < early.now()
    assert to_local_day(latest) == "2026-11-03"


# ================================================================ CLI con la BD de prueba


def test_cli_seed_demo_crea_la_demo_y_la_segunda_vez_avisa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_PASSWORD", "")
    get_settings.cache_clear()
    try:
        created = runner.invoke(cli_app, ["db", "seed-demo"], env=WIDE)
        repeated = runner.invoke(cli_app, ["db", "seed-demo"], env=WIDE)
    finally:
        get_settings.cache_clear()

    assert created.exit_code == 0, created.output
    assert "Pendiente" not in created.output
    assert repeated.exit_code == 0, repeated.output
    assert "--reset" in repeated.output
    with Session(get_engine()) as session:
        count = session.execute(
            select(func.count()).select_from(User).where(User.is_demo.is_(True))
        ).scalar_one()
    assert count == 1


@pytest.mark.parametrize("reset", [False, True])
def test_nunca_borra_una_cuenta_real_que_use_el_correo_de_la_demo(
    client: TestClient, settings: Settings, clock: FakeClock, reset: bool
) -> None:
    """§17.4 «nunca toca otros usuarios»: si DEMO_EMAIL es de una persona real (is_demo = false),
    ni siquiera `--reset` la borra."""
    _, real_id = register_user(client, settings.demo_email)
    complete_lesson(real_id, "M1-N1-L1", 90, True)

    with pytest.raises(demo_module().DemoError) as excinfo:
        demo_module().seed_demo(settings, clock, reset=reset)

    assert "DEMO_EMAIL" in str(excinfo.value)
    with Session(get_engine()) as session:
        user = session.get(User, uuid.UUID(real_id))
        assert user is not None
        assert user.is_demo is False
        sessions = session.execute(
            select(func.count()).select_from(LessonSession).where(LessonSession.user_id == user.id)
        ).scalar_one()
        assert sessions == 1


def test_una_demo_password_invalida_no_borra_la_demo_existente(
    settings: Settings, clock: FakeClock
) -> None:
    """La contraseña se valida antes de tocar la base: un `--reset` con DEMO_PASSWORD inválida
    falla con DemoError y deja la demo anterior intacta."""
    first = seed(settings, clock)
    assert first.created
    user_before = demo_user(settings).id
    bad = settings.model_copy(update={"demo_password": "corta"})

    with pytest.raises(demo_module().DemoError) as excinfo:
        demo_module().seed_demo(bad, clock, reset=True)

    assert "DEMO_PASSWORD" in str(excinfo.value)
    assert demo_user(settings).id == user_before


def test_sin_contenido_cargado_falla_con_mensaje_y_no_deja_una_demo_a_medias(
    settings: Settings, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = demo_module()
    monkeypatch.setattr(module, "FIRST_LESSON", "LECCION-QUE-NO-EXISTE")

    with pytest.raises(module.DemoError) as excinfo:
        module.seed_demo(settings, clock)

    assert "alas db seed" in str(excinfo.value)
    with Session(get_engine()) as session:
        found = session.execute(
            select(User).where(User.email == settings.demo_email)
        ).scalar_one_or_none()
        assert found is None
