"""Tareas 6.1 y 6.2 — gamificación: XP, néctar, actividad diaria, racha, repasos, logros, protector
de racha y recarga de vidas (R5.1 a R5.16, R6.4, R6.5; §7.5, §7.7, §7.9, §7.10, §8.1, §8.2, §8.3;
D22, D24).

`complete` aplica la gamificación en su misma transacción SERIALIZABLE
(`GamificationService.apply_completion`). Los días de negocio son días de Bogotá
(`to_local_day(clock.now())`, UTC-5) y todos los tiempos los fija un `FakeClock` (D22).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limits
from app.domain.dates import TZ, add_days, to_local_day
from app.domain.policies.achievements import ACHIEVEMENTS
from app.infra.db import get_engine
from app.infra.models import (
    Achievement,
    DailyActivity,
    Exercise,
    Lesson,
    LessonSession,
    Module,
    Node,
    SessionAnswer,
    User,
    UserAchievement,
)
from app.infra.models import SignReview as SignReviewRow
from app.infra.models import Streak as StreakRow
from tests.api.helpers import (
    PASSWORD,
    auth,
    complete_lesson,
    correct_answer,
    register_user,
    wrong_answer,
)
from tests.fakes import FakeClock

pytestmark = pytest.mark.usefixtures("seeded_content")

JsonObject = dict[str, object]

EMAIL = "ana@ejemplo.com"

# Día local (Bogotá) de referencia, en el pasado para que ningún token quede «del futuro».
BASE_DAY = (datetime.now(TZ) - timedelta(days=10)).date()

L1 = "M1-N1-L1"  # Aprende: 3 señas, 6 ejercicios con puntaje, aprobar da 20 XP y 5 de néctar
L2 = "M1-N1-L2"
L4 = "M1-N1-L4"  # Reto final del nodo

STATS_KEYS = {"totalXp", "nectar", "streak", "today", "hearts"}
STATS_STREAK_KEYS = {"current", "longest", "freezesAvailable", "atRisk"}
TODAY_KEYS = {"seconds", "goalSeconds", "xp"}
HEARTS_KEYS = {"enabled", "current", "max", "nextHeartAt"}
ACHIEVEMENT_KEYS = {"id", "title", "description", "icon", "nectar", "unlockedAt"}
NEW_ACHIEVEMENT_KEYS = {"id", "title", "nectar"}

FIRST_LESSON = {"id": "FIRST_LESSON", "title": "Primeras alas", "nectar": 10}
STREAK_3 = {"id": "STREAK_3", "title": "Aleteo constante", "nectar": 15}
NOT_ENOUGH_NECTAR_MESSAGE = "No tienes suficiente néctar"


def local(day: int, hour: int, minute: int = 0) -> datetime:
    """Instante UTC de las `hour:minute` (hora de Bogotá) del día BASE_DAY + `day`."""
    moment = datetime.combine(BASE_DAY + timedelta(days=day), time(hour, minute), tzinfo=TZ)
    return moment.astimezone(UTC)


def day_str(day: int) -> str:
    return (BASE_DAY + timedelta(days=day)).isoformat()


T0 = local(0, 10)  # 10:00 de Bogotá del día 0


# ---------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def hearts_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Vidas activas (§7.10) aunque el `.env` local las desactive."""
    monkeypatch.setenv("HEARTS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_limits() -> Iterator[None]:
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture(autouse=True)
def clock(client: TestClient) -> Iterator[FakeClock]:
    fake = FakeClock(T0)
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_clock] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_clock, None)


@pytest.fixture
def user(client: TestClient) -> tuple[str, str]:
    return register_user(client, EMAIL)


# ---------------------------------------------------------------- ayudas HTTP


def as_obj(value: object) -> JsonObject:
    assert isinstance(value, dict), value
    return value


def as_list(value: object) -> list[JsonObject]:
    assert isinstance(value, list), value
    for item in value:
        assert isinstance(item, dict), item
    return value


def as_str(value: object) -> str:
    assert isinstance(value, str), value
    return value


def as_int(value: object) -> int:
    assert isinstance(value, int), value
    assert not isinstance(value, bool), value
    return value


def json_of(response: Response) -> JsonObject:
    return as_obj(response.json())


def parse_iso(value: object) -> datetime:
    moment = datetime.fromisoformat(as_str(value).replace("Z", "+00:00"))
    assert moment.tzinfo is not None, "La fecha debe llevar zona horaria"
    return moment


def login(client: TestClient, email: str = EMAIL) -> str:
    """Nuevo access token (el anterior vence a los 15 min del `FakeClock`)."""
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return as_str(json_of(response)["accessToken"])


def move_to(client: TestClient, clock: FakeClock, moment: datetime) -> str:
    """Fija el reloj y devuelve un token válido en ese instante."""
    clock.set(moment)
    return login(client)


def start(client: TestClient, token: str, lesson_id: str) -> JsonObject:
    response = client.post(f"/api/lessons/{lesson_id}/sessions", headers=auth(token))
    assert response.status_code == 201, response.text
    return json_of(response)


def session_id_of(session: JsonObject) -> str:
    return as_str(session["sessionId"])


def exercises_of(session: JsonObject) -> list[JsonObject]:
    return as_list(session["exercises"])


def exercise_ids(session: JsonObject) -> list[str]:
    return [as_str(e["id"]) for e in exercises_of(session)]


def scored_ids(session: JsonObject) -> list[str]:
    return [as_str(e["id"]) for e in exercises_of(session) if e["scored"] is True]


def ids_of_type(session: JsonObject, exercise_type: str) -> list[str]:
    return [as_str(e["id"]) for e in exercises_of(session) if e["type"] == exercise_type]


def post_answer(
    client: TestClient, token: str, session_id: str, exercise_id: str, answer: object
) -> None:
    response = client.post(
        f"/api/lesson-sessions/{session_id}/answers",
        headers=auth(token),
        json={"exerciseId": exercise_id, "answer": answer},
    )
    assert response.status_code == 200, response.text


def answer_all(
    client: TestClient, token: str, session: JsonObject, *, wrong: set[str] | None = None
) -> None:
    """Responde todos los ejercicios: bien, salvo los de `wrong` (los OBSERVE siempre bien)."""
    sid = session_id_of(session)
    for exercise_id in exercise_ids(session):
        body: dict[str, object] | None = None
        if wrong is not None and exercise_id in wrong:
            body = wrong_answer(sid, exercise_id)
        if body is None:
            body = correct_answer(sid, exercise_id)
        post_answer(client, token, sid, exercise_id, body)


def post_complete(client: TestClient, token: str, session_id: str) -> Response:
    response: Response = client.post(
        f"/api/lesson-sessions/{session_id}/complete", headers=auth(token)
    )
    return response


def complete(client: TestClient, token: str, session_id: str) -> JsonObject:
    response = post_complete(client, token, session_id)
    assert response.status_code == 200, response.text
    return json_of(response)


def do_lesson(
    client: TestClient,
    token: str,
    clock: FakeClock,
    lesson_id: str = L1,
    *,
    minutes: int = 0,
    wrong: set[str] | None = None,
    wrong_all_scored: bool = False,
) -> JsonObject:
    """Empieza, responde todo, deja pasar `minutes` y completa; devuelve el resultado."""
    session = start(client, token, lesson_id)
    to_fail = set(wrong or set())
    if wrong_all_scored:
        to_fail |= set(scored_ids(session))
    answer_all(client, token, session, wrong=to_fail)
    if minutes:
        clock.advance(minutes=minutes)
    return complete(client, token, session_id_of(session))


def streak_of(result: JsonObject) -> JsonObject:
    streak = as_obj(result["streak"])
    assert set(streak) == {"current", "extended"}
    return streak


def new_achievements(result: JsonObject) -> list[JsonObject]:
    items = as_list(result["newAchievements"])
    for item in items:
        assert set(item) == NEW_ACHIEVEMENT_KEYS, item
    return items


def new_achievement_ids(result: JsonObject) -> list[str]:
    return [as_str(item["id"]) for item in new_achievements(result)]


def achievements_nectar(result: JsonObject) -> int:
    return sum(as_int(item["nectar"]) for item in new_achievements(result))


def get_stats(client: TestClient, token: str) -> JsonObject:
    response = client.get("/api/gamification/stats", headers=auth(token))
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert set(body) == STATS_KEYS
    assert set(as_obj(body["streak"])) == STATS_STREAK_KEYS
    assert set(as_obj(body["today"])) == TODAY_KEYS
    assert set(as_obj(body["hearts"])) == HEARTS_KEYS
    return body


def get_achievements(client: TestClient, token: str) -> list[JsonObject]:
    response = client.get("/api/gamification/achievements", headers=auth(token))
    assert response.status_code == 200, response.text
    return as_list(response.json())


def buy_freeze(client: TestClient, token: str) -> Response:
    response: Response = client.post("/api/gamification/streak-freeze", headers=auth(token))
    return response


def refill_hearts(client: TestClient, token: str) -> Response:
    response: Response = client.post("/api/gamification/hearts-refill", headers=auth(token))
    return response


def assert_error(response: Response, status: int, code: str) -> JsonObject:
    assert response.status_code == status, response.text
    body = json_of(response)
    assert body["statusCode"] == status
    assert body["code"] == code
    assert isinstance(body["message"], str)
    assert body["message"]
    return body


# ---------------------------------------------------------------- ayudas de BD


def db_user(user_id: str) -> User:
    with Session(get_engine()) as db:
        found = db.get(User, uuid.UUID(user_id))
        assert found is not None
        db.expunge(found)
        return found


def db_streak(user_id: str) -> StreakRow | None:
    with Session(get_engine()) as db:
        found = db.get(StreakRow, uuid.UUID(user_id))
        if found is not None:
            db.expunge(found)
        return found


def db_activity(user_id: str) -> list[DailyActivity]:
    with Session(get_engine()) as db:
        rows = list(
            db.execute(
                select(DailyActivity)
                .where(DailyActivity.user_id == uuid.UUID(user_id))
                .order_by(DailyActivity.day)
            ).scalars()
        )
        for row in rows:
            db.expunge(row)
        return rows


def db_reviews(user_id: str) -> dict[str, tuple[int, str]]:
    """sign_id → (strength, next_review_day)."""
    with Session(get_engine()) as db:
        rows = db.execute(
            select(SignReviewRow.sign_id, SignReviewRow.strength, SignReviewRow.next_review_day)
            .where(SignReviewRow.user_id == uuid.UUID(user_id))
            .order_by(SignReviewRow.sign_id)
        ).all()
        return {sign_id: (strength, next_day) for sign_id, strength, next_day in rows}


def db_user_achievements(user_id: str) -> list[UserAchievement]:
    with Session(get_engine()) as db:
        rows = list(
            db.execute(
                select(UserAchievement)
                .where(UserAchievement.user_id == uuid.UUID(user_id))
                .order_by(UserAchievement.achievement_id)
            ).scalars()
        )
        for row in rows:
            db.expunge(row)
        return rows


def db_achievement_catalog() -> list[Achievement]:
    with Session(get_engine()) as db:
        rows = list(db.execute(select(Achievement).order_by(Achievement.order)).scalars())
        for row in rows:
            db.expunge(row)
        return rows


def db_exercises(lesson_id: str) -> list[Exercise]:
    with Session(get_engine()) as db:
        rows = list(
            db.execute(
                select(Exercise).where(Exercise.lesson_id == lesson_id).order_by(Exercise.order)
            ).scalars()
        )
        for row in rows:
            db.expunge(row)
        return rows


def lesson_signs(lesson_id: str) -> set[str]:
    return {e.sign_id for e in db_exercises(lesson_id) if e.sign_id is not None}


def set_user_values(user_id: str, **values: object) -> None:
    with Session(get_engine()) as db:
        db.execute(update(User).where(User.id == uuid.UUID(user_id)).values(**values))
        db.commit()


def set_nectar(user_id: str, nectar: int) -> None:
    set_user_values(user_id, nectar=nectar)


def set_streak(
    user_id: str,
    *,
    current: int = 0,
    longest: int = 0,
    freezes: int = 0,
    last_active_day: str | None = None,
) -> None:
    """Crea o reemplaza la fila de `streaks` del usuario."""
    values = {
        "current": current,
        "longest": longest,
        "freezes_available": freezes,
        "last_active_day": last_active_day,
    }
    with Session(get_engine()) as db:
        db.execute(
            insert(StreakRow)
            .values(user_id=uuid.UUID(user_id), **values)
            .on_conflict_do_update(index_elements=[StreakRow.user_id], set_=values)
        )
        db.commit()


def add_activity(user_id: str, day: str, *, seconds: int, xp: int, lessons: int = 1) -> None:
    with Session(get_engine()) as db:
        db.add(
            DailyActivity(
                user_id=uuid.UUID(user_id),
                day=day,
                seconds=seconds,
                xp=xp,
                lessons=lessons,
                reviews=0,
            )
        )
        db.commit()


def lessons_in_order() -> list[str]:
    with Session(get_engine()) as db:
        rows = db.execute(
            select(Lesson.id)
            .join(Node, Node.id == Lesson.node_id)
            .join(Module, Module.id == Node.module_id)
            .where(Module.published.is_(True))
            .order_by(Module.order, Node.order, Lesson.order)
        ).scalars()
        return list(rows)


def approve_lessons_before(user_id: str, lesson_id: str) -> None:
    """Aprueba (directo en la BD) todas las lecciones anteriores en el orden global."""
    ordered = lessons_in_order()
    for previous in ordered[: ordered.index(lesson_id)]:
        complete_lesson(user_id, previous, 100, True)


def seed_correct_signs(user_id: str, count: int, *, exclude: set[str]) -> int:
    """Inserta en la BD sesiones cerradas con respuestas correctas en ejercicios con puntaje
    hasta cubrir `count` señas distintas (fuera de `exclude`). Devuelve cuántas cubrió."""
    covered: set[str] = set()
    with Session(get_engine()) as db:
        for lesson_id in lessons_in_order():
            if len(covered) >= count:
                break
            picked: list[str] = []
            for exercise in db_exercises(lesson_id):
                sign = exercise.sign_id
                if not exercise.scored or sign is None or sign in exclude or sign in covered:
                    continue
                if len(covered) >= count:
                    break
                covered.add(sign)
                picked.append(exercise.id)
            if not picked:
                continue
            session_id = uuid.uuid4()
            db.add(
                LessonSession(
                    id=session_id,
                    user_id=uuid.UUID(user_id),
                    lesson_id=lesson_id,
                    started_at=T0 - timedelta(days=1),
                    completed_at=T0 - timedelta(days=1),
                    hearts_lost=0,
                    score=0,
                    correct=0,
                    total=10,
                    passed=False,
                )
            )
            db.flush()
            for exercise_id in picked:
                db.add(
                    SessionAnswer(
                        session_id=session_id,
                        exercise_id=exercise_id,
                        answer={},
                        correct=True,
                        answered_at=T0 - timedelta(days=1),
                    )
                )
        db.commit()
    return len(covered)


# ================================================================ 6.1 · actividad diaria


def test_l1_aprobada_registra_actividad_del_dia_local(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R5.11, §8.1: `complete` suma segundos, XP y una lección al día de Bogotá."""
    token, user_id = user
    result = do_lesson(client, token, clock, minutes=3)
    assert result["passed"] is True
    assert result["xpEarned"] == 20

    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].day == day_str(0)
    assert rows[0].day == to_local_day(clock.now())
    assert rows[0].seconds == 180
    assert rows[0].xp == 20
    assert rows[0].lessons == 1
    assert rows[0].reviews == 0


def test_dos_lecciones_el_mismo_dia_acumulan_en_una_sola_fila(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    do_lesson(client, token, clock, minutes=3)
    second = do_lesson(client, token, clock, minutes=2)
    assert second["xpEarned"] == 10  # repetida: la mitad

    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].seconds == 300
    assert rows[0].xp == 30
    assert rows[0].lessons == 2


def test_duracion_con_tope_de_15_minutos_en_la_actividad(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """B16: la actividad diaria usa `duration_sec` (tope 900 s), no el tiempo bruto."""
    token, user_id = user
    session = start(client, token, L1)
    answer_all(client, token, session)
    clock.advance(hours=2)
    token = login(client)
    complete(client, token, session_id_of(session))

    assert db_activity(user_id)[0].seconds == 900


def test_leccion_no_aprobada_da_0_xp_pero_cuenta_como_actividad(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R5.3: reprobar da 0 XP, 0 néctar, sin logros, pero cuenta para el día y la racha."""
    token, user_id = user
    result = do_lesson(client, token, clock, minutes=1, wrong_all_scored=True)

    assert result["passed"] is False
    assert result["xpEarned"] == 0
    assert result["nectarEarned"] == 0
    assert result["newAchievements"] == []
    assert streak_of(result) == {"current": 1, "extended": True}

    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].lessons == 1
    assert rows[0].xp == 0
    assert rows[0].seconds == 60
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.current == 1
    assert stored.last_active_day == day_str(0)
    assert db_user(user_id).nectar == 0
    assert db_user(user_id).total_xp == 0


def test_actividad_de_noche_cuenta_en_el_dia_de_bogota_no_en_el_de_utc(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """20:00 de Bogotá es la 01:00 UTC del día siguiente: el día de negocio es el de Bogotá."""
    _, user_id = user
    token = move_to(client, clock, local(0, 20))
    assert clock.now().date() != BASE_DAY  # en UTC ya es el día siguiente
    do_lesson(client, token, clock)

    assert [row.day for row in db_activity(user_id)] == [day_str(0)]


# ================================================================ 6.1 · racha


def test_primera_leccion_inicia_la_racha_en_1_y_la_extiende(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    result = do_lesson(client, token, clock)

    assert streak_of(result) == {"current": 1, "extended": True}
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.current == 1
    assert stored.longest == 1
    assert stored.freezes_available == 0
    assert stored.last_active_day == day_str(0)


def test_dos_lecciones_el_mismo_dia_no_suben_la_racha_dos_veces(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """PRUEBA OBLIGATORIA §7.5, R5.6."""
    token, user_id = user
    first = do_lesson(client, token, clock)
    clock.advance(minutes=5)
    second = do_lesson(client, token, clock)

    assert streak_of(first) == {"current": 1, "extended": True}
    assert streak_of(second) == {"current": 1, "extended": False}
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.current == 1


def test_23_59_y_00_01_de_bogota_cuentan_como_dos_dias(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """PRUEBA OBLIGATORIA §7.5: 23:59 y 00:01 (UTC-5) son dos días locales distintos, aunque en
    UTC ambos instantes caen el mismo día."""
    _, user_id = user
    token = move_to(client, clock, local(0, 23, 55))
    first = do_lesson(client, token, clock, minutes=4)
    assert clock.now() == local(0, 23, 59)

    clock.set(local(1, 0, 1))
    assert local(0, 23, 59).date() == local(1, 0, 1).date()  # mismo día UTC
    second = do_lesson(client, token, clock)

    assert streak_of(first) == {"current": 1, "extended": True}
    assert streak_of(second) == {"current": 2, "extended": True}
    assert [row.day for row in db_activity(user_id)] == [day_str(0), day_str(1)]
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.current == 2
    assert stored.longest == 2
    assert stored.last_active_day == day_str(1)


def test_dias_consecutivos_suben_la_racha(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R5.5."""
    token, _ = user
    do_lesson(client, token, clock)
    token = move_to(client, clock, local(1, 10))
    result = do_lesson(client, token, clock)
    assert streak_of(result) == {"current": 2, "extended": True}


def test_un_dia_perdido_con_un_protector_conserva_la_racha_y_lo_consume(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """PRUEBA OBLIGATORIA §7.5, R5.7."""
    token, user_id = user
    do_lesson(client, token, clock)
    set_streak(user_id, current=1, longest=1, freezes=1, last_active_day=day_str(0))

    token = move_to(client, clock, local(2, 10))  # el día 1 no hubo actividad
    result = do_lesson(client, token, clock)

    assert streak_of(result) == {"current": 2, "extended": True}
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.current == 2
    assert stored.freezes_available == 0
    assert stored.last_active_day == day_str(2)


def test_dos_dias_perdidos_con_un_protector_reinicia_la_racha_a_1(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """PRUEBA OBLIGATORIA §7.5, R5.8."""
    token, user_id = user
    do_lesson(client, token, clock)
    set_streak(user_id, current=4, longest=4, freezes=1, last_active_day=day_str(0))

    token = move_to(client, clock, local(3, 10))  # días 1 y 2 sin actividad
    result = do_lesson(client, token, clock)

    assert streak_of(result) == {"current": 1, "extended": True}
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.current == 1
    assert stored.longest == 4  # el récord no se pierde
    assert stored.freezes_available == 1  # no alcanzaba: no se consume
    assert stored.last_active_day == day_str(3)


def test_racha_de_tres_dias_otorga_streak_3(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    first = do_lesson(client, token, clock)
    token = move_to(client, clock, local(1, 10))
    second = do_lesson(client, token, clock)
    token = move_to(client, clock, local(2, 10))
    third = do_lesson(client, token, clock)

    assert "STREAK_3" not in new_achievement_ids(first)
    assert "STREAK_3" not in new_achievement_ids(second)
    assert "FIRST_LESSON" not in new_achievement_ids(second)
    assert streak_of(third) == {"current": 3, "extended": True}
    assert new_achievements(third) == [STREAK_3]
    assert "STREAK_3" in {row.achievement_id for row in db_user_achievements(user_id)}


# ================================================================ 6.1 · repasos programados


def test_leccion_perfecta_programa_cada_sena_a_dos_dias_con_fuerza_1(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """§7.7: primera vez (fuerza 0) + acierto → fuerza 1 y repaso en INTERVALS[1] = 2 días."""
    token, user_id = user
    do_lesson(client, token, clock)

    signs = lesson_signs(L1)
    assert len(signs) == 3
    assert db_reviews(user_id) == dict.fromkeys(signs, (1, day_str(2)))


def test_sena_con_un_error_queda_con_fuerza_0_y_repaso_manana(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R6.4: basta un error en cualquier ejercicio de la seña para programarla mañana."""
    token, user_id = user
    target = next(e for e in db_exercises(L1) if e.type.value == "VIDEO_TO_MEANING")
    assert target.sign_id is not None
    result = do_lesson(client, token, clock, wrong={target.id})
    assert result["passed"] is True

    reviews = db_reviews(user_id)
    assert set(reviews) == lesson_signs(L1)
    assert reviews[target.sign_id] == (0, day_str(1))
    for sign_id in lesson_signs(L1) - {target.sign_id}:
        assert reviews[sign_id] == (1, day_str(2))


def test_necesito_repasar_en_produce_programa_la_sena_para_manana(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R6.4: PRODUCE con «Necesito repasar» no cuenta en el puntaje pero sí en el repaso."""
    token, user_id = user
    produce = next(e for e in db_exercises(L1) if e.type.value == "PRODUCE")
    assert produce.sign_id is not None
    session = start(client, token, L1)
    sid = session_id_of(session)
    for exercise_id in exercise_ids(session):
        if exercise_id == produce.id:
            post_answer(client, token, sid, exercise_id, {"method": "self", "ok": False})
        else:
            post_answer(client, token, sid, exercise_id, correct_answer(sid, exercise_id))
    result = complete(client, token, sid)
    assert result["score"] == 100

    reviews = db_reviews(user_id)
    assert reviews[produce.sign_id] == (0, day_str(1))
    for sign_id in lesson_signs(L1) - {produce.sign_id}:
        assert reviews[sign_id] == (1, day_str(2))


def test_leccion_reprobada_programa_todas_sus_senas_para_manana(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    do_lesson(client, token, clock, wrong_all_scored=True)
    assert db_reviews(user_id) == dict.fromkeys(lesson_signs(L1), (0, day_str(1)))


def test_segundo_acierto_sube_la_fuerza_y_espacia_el_repaso(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R6.5: fuerza 1 → 2 y repaso en INTERVALS[2] = 4 días desde hoy."""
    token, user_id = user
    do_lesson(client, token, clock)
    token = move_to(client, clock, local(1, 10))
    do_lesson(client, token, clock)

    assert db_reviews(user_id) == dict.fromkeys(lesson_signs(L1), (2, day_str(5)))


def test_error_en_una_sena_ya_programada_la_reinicia_a_fuerza_0(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    do_lesson(client, token, clock)
    target = next(e for e in db_exercises(L1) if e.type.value == "VIDEO_TO_MEANING")
    assert target.sign_id is not None

    token = move_to(client, clock, local(1, 10))
    do_lesson(client, token, clock, wrong={target.id})

    reviews = db_reviews(user_id)
    assert reviews[target.sign_id] == (0, day_str(2))
    for sign_id in lesson_signs(L1) - {target.sign_id}:
        assert reviews[sign_id] == (2, day_str(5))


# ================================================================ 6.1 · logros y néctar


def test_primera_leccion_aprobada_otorga_primeras_alas(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """§7.9: el néctar del logro se suma aparte de `nectarEarned` (que es solo la lección)."""
    token, user_id = user
    result = do_lesson(client, token, clock)

    assert result["nectarEarned"] == 5
    assert new_achievements(result) == [FIRST_LESSON]
    stored = db_user(user_id)
    assert stored.nectar == 15
    assert stored.total_xp == 20
    unlocked = db_user_achievements(user_id)
    assert [row.achievement_id for row in unlocked] == ["FIRST_LESSON"]
    assert unlocked[0].unlocked_at == T0  # D22: lo fija el Clock


def test_otra_leccion_aprobada_no_vuelve_a_dar_primeras_alas(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R5.10."""
    token, user_id = user
    first = do_lesson(client, token, clock)
    second = do_lesson(client, token, clock, L2)

    assert new_achievement_ids(first) == ["FIRST_LESSON"]
    assert second["passed"] is True
    assert "FIRST_LESSON" not in new_achievement_ids(second)
    assert db_user(user_id).nectar == 5 + 10 + as_int(second["nectarEarned"]) + (
        achievements_nectar(second)
    )
    assert [row.achievement_id for row in db_user_achievements(user_id)] == ["FIRST_LESSON"]


def test_repetir_la_misma_leccion_no_vuelve_a_dar_el_logro(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    do_lesson(client, token, clock)
    again = do_lesson(client, token, clock)
    assert again["newAchievements"] == []
    assert db_user(user_id).nectar == 15 + 5


def test_complete_repetido_devuelve_lo_mismo_sin_duplicar_gamificacion(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """B2, R4.10: el segundo `complete` no suma otra vez actividad, racha, néctar ni logros."""
    token, user_id = user
    session = start(client, token, L1)
    answer_all(client, token, session)
    clock.advance(minutes=3)
    sid = session_id_of(session)

    first = complete(client, token, sid)
    clock.advance(minutes=1)
    second = complete(client, token, sid)

    assert second == first
    assert new_achievements(first) == [FIRST_LESSON]
    assert streak_of(first) == {"current": 1, "extended": True}
    stored = db_user(user_id)
    assert stored.nectar == 15
    assert stored.total_xp == 20
    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].lessons == 1
    assert rows[0].seconds == 180
    assert rows[0].xp == 20
    streak = db_streak(user_id)
    assert streak is not None
    assert streak.current == 1
    assert len(db_user_achievements(user_id)) == 1


def test_dos_complete_simultaneos_otorgan_el_logro_una_sola_vez(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """PRUEBA OBLIGATORIA §7.9, R5.10, B5: dos solicitudes a la vez → una fila y néctar una vez."""
    token, user_id = user
    session = start(client, token, L1)
    answer_all(client, token, session)
    sid = session_id_of(session)

    def finish(_: int) -> tuple[int, JsonObject]:
        with TestClient(client.app) as other:
            response = other.post(f"/api/lesson-sessions/{sid}/complete", headers=auth(token))
        return response.status_code, as_obj(response.json())

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(finish, [0, 1]))

    assert [code for code, _ in outcomes] == [200, 200]
    assert outcomes[0][1] == outcomes[1][1]
    assert new_achievements(outcomes[0][1]) == [FIRST_LESSON]
    assert [row.achievement_id for row in db_user_achievements(user_id)] == ["FIRST_LESSON"]
    stored = db_user(user_id)
    assert stored.nectar == 15
    assert stored.total_xp == 20
    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].lessons == 1


def test_reto_perfecto_otorga_nodo_superado_y_nodo_dorado(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    approve_lessons_before(user_id, L4)
    result = do_lesson(client, token, clock, L4)

    assert result["score"] == 100
    ids = new_achievement_ids(result)
    assert {"NODE_DONE", "GOLDEN_NODE"} <= set(ids)
    by_id = {as_str(a["id"]): a for a in new_achievements(result)}
    assert by_id["NODE_DONE"] == {"id": "NODE_DONE", "title": "Nodo superado", "nectar": 15}
    assert by_id["GOLDEN_NODE"] == {"id": "GOLDEN_NODE", "title": "Nodo dorado", "nectar": 20}
    assert db_user(user_id).nectar == as_int(result["nectarEarned"]) + achievements_nectar(result)


def test_reto_aprobado_sin_100_otorga_nodo_superado_pero_no_dorado(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    approve_lessons_before(user_id, L4)
    session = start(client, token, L4)
    answer_all(client, token, session, wrong={scored_ids(session)[0]})
    result = complete(client, token, session_id_of(session))

    assert result["passed"] is True
    assert as_int(result["score"]) < 100
    ids = new_achievement_ids(result)
    assert "NODE_DONE" in ids
    assert "GOLDEN_NODE" not in ids


def test_logros_en_el_orden_del_catalogo(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """`newAchievements` sigue el orden de ACHIEVEMENTS (FIRST_LESSON antes que NODE_DONE…)."""
    token, user_id = user
    approve_lessons_before(user_id, L4)
    ids = new_achievement_ids(do_lesson(client, token, clock, L4))
    order = [rule.id for rule in ACHIEVEMENTS]
    assert ids == sorted(ids, key=order.index)


def test_aprobar_todo_el_modulo_1_otorga_fundamentos_dominados(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    last_m1 = [lesson for lesson in lessons_in_order() if lesson.startswith("M1-")][-1]
    approve_lessons_before(user_id, last_m1)
    result = do_lesson(client, token, clock, last_m1)

    assert result["passed"] is True
    assert "MODULE_1" in new_achievement_ids(result)
    by_id = {as_str(a["id"]): a for a in new_achievements(result)}
    assert by_id["MODULE_1"] == {"id": "MODULE_1", "title": "Fundamentos dominados", "nectar": 40}


def test_falta_una_leccion_de_m1_no_otorga_fundamentos_dominados(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    last_m1 = [lesson for lesson in lessons_in_order() if lesson.startswith("M1-")][-1]
    approve_lessons_before(user_id, last_m1)
    session = start(client, token, last_m1)
    answer_all(client, token, session, wrong=set(scored_ids(session)))
    result = complete(client, token, session_id_of(session))
    assert result["passed"] is False
    assert "MODULE_1" not in new_achievement_ids(result)


def test_veinte_reconocimientos_con_camara_otorgan_ojo_de_colibri_al_completar(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    set_user_values(user_id, recognitions_correct=20)
    result = do_lesson(client, token, clock)
    assert "HUMMINGBIRD_EYE" in new_achievement_ids(result)
    assert db_user(user_id).nectar == 5 + 10 + 30


def test_diecinueve_reconocimientos_no_otorgan_ojo_de_colibri(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    set_user_values(user_id, recognitions_correct=19)
    result = do_lesson(client, token, clock)
    assert "HUMMINGBIRD_EYE" not in new_achievement_ids(result)


def test_cincuenta_senas_distintas_correctas_otorgan_manos_que_hablan(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    l1_signs = lesson_signs(L1)
    assert seed_correct_signs(user_id, 50 - len(l1_signs), exclude=l1_signs) == 47
    result = do_lesson(client, token, clock)
    assert "SIGNS_50" in new_achievement_ids(result)


def test_cuarenta_y_nueve_senas_distintas_no_otorgan_manos_que_hablan(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    l1_signs = lesson_signs(L1)
    assert seed_correct_signs(user_id, 49 - len(l1_signs), exclude=l1_signs) == 46
    result = do_lesson(client, token, clock)
    assert "SIGNS_50" not in new_achievement_ids(result)


def test_senas_falladas_no_cuentan_para_manos_que_hablan(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """47 señas previas + las 3 de L1 todas mal → 47 < 50."""
    token, user_id = user
    l1_signs = lesson_signs(L1)
    assert seed_correct_signs(user_id, 47, exclude=l1_signs) == 47
    result = do_lesson(client, token, clock, wrong_all_scored=True)
    assert "SIGNS_50" not in new_achievement_ids(result)


# ================================================================ 6.2 · autenticación


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/gamification/stats"),
        ("GET", "/api/gamification/achievements"),
        ("POST", "/api/gamification/streak-freeze"),
        ("POST", "/api/gamification/hearts-refill"),
    ],
)
def test_endpoints_de_gamificacion_sin_token_401(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, path)
    assert response.status_code == 401, response.text


# ================================================================ 6.2 · stats


def test_stats_de_usuario_nuevo(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    assert get_stats(client, token) == {
        "totalXp": 0,
        "nectar": 0,
        "streak": {"current": 0, "longest": 0, "freezesAvailable": 0, "atRisk": False},
        "today": {"seconds": 0, "goalSeconds": 600, "xp": 0},
        "hearts": {"enabled": True, "current": 5, "max": 5, "nextHeartAt": None},
    }


def test_stats_despues_de_aprobar_l1(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    do_lesson(client, token, clock, minutes=3)
    assert get_stats(client, token) == {
        "totalXp": 20,
        "nectar": 15,
        "streak": {"current": 1, "longest": 1, "freezesAvailable": 0, "atRisk": False},
        "today": {"seconds": 180, "goalSeconds": 600, "xp": 20},
        "hearts": {"enabled": True, "current": 5, "max": 5, "nextHeartAt": None},
    }


def test_meta_diaria_en_segundos_sigue_la_meta_del_usuario(
    client: TestClient, user: tuple[str, str]
) -> None:
    """R5.11: goalSeconds = dailyGoalMinutes * 60."""
    token, user_id = user
    set_user_values(user_id, daily_goal_minutes=20)
    today = as_obj(get_stats(client, token)["today"])
    assert today["goalSeconds"] == 1200


def test_today_vuelve_a_cero_al_dia_siguiente_y_la_racha_queda_en_riesgo(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    do_lesson(client, token, clock, minutes=3)
    token = move_to(client, clock, local(1, 9))

    stats = get_stats(client, token)
    assert stats["today"] == {"seconds": 0, "goalSeconds": 600, "xp": 0}
    assert stats["streak"] == {
        "current": 1,
        "longest": 1,
        "freezesAvailable": 0,
        "atRisk": True,
    }
    assert stats["totalXp"] == 20


def test_today_solo_suma_el_dia_local_actual(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    add_activity(user_id, day_str(-1), seconds=500, xp=40)
    add_activity(user_id, day_str(0), seconds=120, xp=15, lessons=2)
    assert as_obj(get_stats(client, token)["today"]) == {
        "seconds": 120,
        "goalSeconds": 600,
        "xp": 15,
    }


def test_today_usa_el_dia_de_bogota_a_las_23_59(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """A las 23:59 de Bogotá ya es el día siguiente en UTC; `today` es el día local."""
    _, user_id = user
    add_activity(user_id, day_str(0), seconds=300, xp=20)
    add_activity(user_id, day_str(1), seconds=60, xp=5)
    token = move_to(client, clock, local(0, 23, 59))
    assert as_obj(get_stats(client, token)["today"]) == {
        "seconds": 300,
        "goalSeconds": 600,
        "xp": 20,
    }


def test_racha_caducada_se_muestra_en_0_sin_modificar_la_bd(
    client: TestClient, user: tuple[str, str]
) -> None:
    """§7.5 `display_streak`: solo lectura."""
    token, user_id = user
    set_streak(user_id, current=5, longest=7, freezes=0, last_active_day=day_str(-3))

    streak = as_obj(get_stats(client, token)["streak"])
    assert streak == {"current": 0, "longest": 7, "freezesAvailable": 0, "atRisk": False}
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.current == 5
    assert stored.freezes_available == 0
    assert stored.last_active_day == day_str(-3)


def test_racha_de_ayer_se_muestra_y_esta_en_riesgo(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_streak(user_id, current=5, longest=7, freezes=0, last_active_day=day_str(-1))
    streak = as_obj(get_stats(client, token)["streak"])
    assert streak == {"current": 5, "longest": 7, "freezesAvailable": 0, "atRisk": True}


def test_racha_de_hoy_no_esta_en_riesgo(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    set_streak(user_id, current=5, longest=7, freezes=0, last_active_day=day_str(0))
    streak = as_obj(get_stats(client, token)["streak"])
    assert streak == {"current": 5, "longest": 7, "freezesAvailable": 0, "atRisk": False}


def test_racha_protegida_por_protector_se_sigue_mostrando(
    client: TestClient, user: tuple[str, str]
) -> None:
    """Un día perdido y 1 protector: la racha se muestra (aún se puede salvar)."""
    token, user_id = user
    set_streak(user_id, current=5, longest=7, freezes=1, last_active_day=day_str(-2))
    streak = as_obj(get_stats(client, token)["streak"])
    assert streak == {"current": 5, "longest": 7, "freezesAvailable": 1, "atRisk": False}
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.freezes_available == 1  # mostrar no consume protectores


def test_stats_con_vidas_gastadas_muestra_la_proxima_recarga(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    hearts = as_obj(get_stats(client, token)["hearts"])
    assert hearts["enabled"] is True
    assert hearts["current"] == 2
    assert hearts["max"] == 5
    assert parse_iso(hearts["nextHeartAt"]) == T0 + timedelta(hours=4)


def test_stats_con_vidas_desactivadas(
    client: TestClient, user: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """R5.16: HEARTS_ENABLED=false."""
    token, _ = user
    monkeypatch.setenv("HEARTS_ENABLED", "false")
    get_settings.cache_clear()
    hearts = as_obj(get_stats(client, token)["hearts"])
    assert hearts["enabled"] is False


# ================================================================ 6.2 · achievements


def test_lista_de_logros_completa_en_orden_y_bloqueados(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, _ = user
    items = get_achievements(client, token)
    catalog = db_achievement_catalog()

    assert [item["id"] for item in items] == [rule.id for rule in ACHIEVEMENTS]
    assert len(items) == 9
    for item, rule, row in zip(items, ACHIEVEMENTS, catalog, strict=True):
        assert set(item) == ACHIEVEMENT_KEYS
        assert item["title"] == rule.title
        assert item["nectar"] == rule.nectar_reward
        assert item["description"] == row.description
        assert item["icon"] == row.icon
        assert as_str(item["description"])
        assert as_str(item["icon"])
        assert item["unlockedAt"] is None


def test_logro_desbloqueado_muestra_la_fecha(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    do_lesson(client, token, clock)
    clock.advance(minutes=1)

    items = {as_str(item["id"]): item for item in get_achievements(client, token)}
    assert parse_iso(items["FIRST_LESSON"]["unlockedAt"]) == T0
    for achievement_id, item in items.items():
        if achievement_id != "FIRST_LESSON":
            assert item["unlockedAt"] is None, achievement_id


def test_logros_de_otro_usuario_no_se_muestran(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    do_lesson(client, token, clock)
    other_token, _ = register_user(client, "beto@ejemplo.com")
    assert all(item["unlockedAt"] is None for item in get_achievements(client, other_token))


# ================================================================ 6.2 · streak-freeze


def test_comprar_protector_descuenta_50_y_suma_uno(
    client: TestClient, user: tuple[str, str]
) -> None:
    """R5.9: el cuerpo de la respuesta es el mismo que `stats`."""
    token, user_id = user
    set_nectar(user_id, 120)

    response = buy_freeze(client, token)
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert body == get_stats(client, token)
    assert body["nectar"] == 70
    assert as_obj(body["streak"])["freezesAvailable"] == 1
    assert db_user(user_id).nectar == 70
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.freezes_available == 1


def test_comprar_protector_con_exactamente_50(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    set_nectar(user_id, 50)
    response = buy_freeze(client, token)
    assert response.status_code == 200, response.text
    assert json_of(response)["nectar"] == 0
    assert db_user(user_id).nectar == 0


def test_protector_sin_nectar_suficiente_409(client: TestClient, user: tuple[str, str]) -> None:
    """R5.9: «No tienes suficiente néctar»."""
    token, user_id = user
    set_nectar(user_id, 49)

    body = assert_error(buy_freeze(client, token), 409, "NOT_ENOUGH_NECTAR")
    assert body["message"] == NOT_ENOUGH_NECTAR_MESSAGE
    assert db_user(user_id).nectar == 49
    stored = db_streak(user_id)
    assert stored is None or stored.freezes_available == 0


def test_maximo_dos_protectores(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    set_nectar(user_id, 200)
    assert buy_freeze(client, token).status_code == 200
    second = buy_freeze(client, token)
    assert second.status_code == 200, second.text
    assert as_obj(json_of(second)["streak"])["freezesAvailable"] == 2

    assert_error(buy_freeze(client, token), 409, "MAX_FREEZES")
    assert db_user(user_id).nectar == 100
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.freezes_available == 2


def test_max_freezes_se_comprueba_antes_que_el_nectar(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_streak(user_id, current=3, longest=3, freezes=2, last_active_day=day_str(0))
    set_nectar(user_id, 0)
    assert_error(buy_freeze(client, token), 409, "MAX_FREEZES")


def test_comprar_protector_conserva_la_racha(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    set_streak(user_id, current=4, longest=6, freezes=0, last_active_day=day_str(0))
    set_nectar(user_id, 50)
    body = json_of(buy_freeze(client, token))
    assert body["streak"] == {"current": 4, "longest": 6, "freezesAvailable": 1, "atRisk": False}
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.current == 4
    assert stored.last_active_day == day_str(0)


# ================================================================ 6.2 · hearts-refill


def test_recargar_vidas_descuenta_30_y_llena_las_5(
    client: TestClient, user: tuple[str, str]
) -> None:
    """R5.14, §7.10."""
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    set_nectar(user_id, 40)

    response = refill_hearts(client, token)
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert body == get_stats(client, token)
    assert body["nectar"] == 10
    assert body["hearts"] == {"enabled": True, "current": 5, "max": 5, "nextHeartAt": None}
    stored = db_user(user_id)
    assert stored.nectar == 10
    assert stored.hearts == 5


def test_recargar_vidas_con_exactamente_30(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    set_user_values(user_id, hearts=0, hearts_updated_at=T0)
    set_nectar(user_id, 30)
    response = refill_hearts(client, token)
    assert response.status_code == 200, response.text
    assert json_of(response)["nectar"] == 0


def test_recargar_vidas_llenas_409_hearts_full(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    set_nectar(user_id, 100)
    assert_error(refill_hearts(client, token), 409, "HEARTS_FULL")
    assert db_user(user_id).nectar == 100


def test_vidas_recuperadas_por_tiempo_cuentan_como_llenas(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """D24: con 4 vidas y 4 h transcurridas ya tiene 5 (derivado), aunque la BD diga 4."""
    token, user_id = user
    set_user_values(user_id, hearts=4, hearts_updated_at=T0)
    set_nectar(user_id, 100)
    token = move_to(client, clock, T0 + timedelta(hours=4))
    assert_error(refill_hearts(client, token), 409, "HEARTS_FULL")
    assert db_user(user_id).nectar == 100


def test_recargar_vidas_sin_nectar_409(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    set_nectar(user_id, 29)

    body = assert_error(refill_hearts(client, token), 409, "NOT_ENOUGH_NECTAR")
    assert body["message"] == NOT_ENOUGH_NECTAR_MESSAGE
    stored = db_user(user_id)
    assert stored.nectar == 29
    assert stored.hearts == 2


def test_hearts_full_se_comprueba_antes_que_el_nectar(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_nectar(user_id, 0)
    assert_error(refill_hearts(client, token), 409, "HEARTS_FULL")


def test_recargar_con_vidas_desactivadas_409_hearts_full(
    client: TestClient, user: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    set_nectar(user_id, 100)
    monkeypatch.setenv("HEARTS_ENABLED", "false")
    get_settings.cache_clear()

    assert_error(refill_hearts(client, token), 409, "HEARTS_FULL")
    assert db_user(user_id).nectar == 100


def test_nectar_de_logros_permite_comprar_protector(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """Integración: 15 de L1 + FIRST_LESSON no alcanzan; con 50 sí."""
    token, user_id = user
    do_lesson(client, token, clock)
    assert_error(buy_freeze(client, token), 409, "NOT_ENOUGH_NECTAR")
    set_nectar(user_id, 50)
    body = json_of(buy_freeze(client, token))
    assert body["streak"] == {"current": 1, "longest": 1, "freezesAvailable": 1, "atRisk": False}
    assert body["totalXp"] == 20


# ---------------------------------------------------------------- revisión del Grupo 6


def test_protector_comprado_tras_romper_la_racha_no_la_revive(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """D-013.8: el protector no es retroactivo; una racha ya rota sigue rota."""
    token, user_id = user
    today = to_local_day(T0)
    set_streak(user_id, current=10, longest=10, last_active_day=add_days(today, -3))
    set_nectar(user_id, 100)
    assert as_obj(get_stats(client, token)["streak"])["current"] == 0

    assert buy_freeze(client, token).status_code == 200
    assert buy_freeze(client, token).status_code == 200

    assert as_obj(get_stats(client, token)["streak"])["current"] == 0
    result = do_lesson(client, token, clock)
    assert streak_of(result)["current"] == 1
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.longest == 10
    assert stored.freezes_available == 2  # no se gastaron en la racha vieja


def test_dos_compras_simultaneas_de_protector_cobran_una_vez(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_nectar(user_id, 60)

    def buy(_: int) -> tuple[int, str]:
        with TestClient(client.app) as other:
            response = buy_freeze(other, token)
        return response.status_code, as_str(json_of(response).get("code", ""))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(buy, [0, 1]))

    assert outcomes == [(200, ""), (409, "NOT_ENOUGH_NECTAR")]
    assert db_user(user_id).nectar == 10
    stored = db_streak(user_id)
    assert stored is not None
    assert stored.freezes_available == 1


def test_dos_recargas_simultaneas_de_vidas_cobran_una_vez(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_user_values(user_id, nectar=40, hearts=0, hearts_updated_at=T0)

    def refill(_: int) -> tuple[int, str]:
        with TestClient(client.app) as other:
            response = refill_hearts(other, token)
        return response.status_code, as_str(json_of(response).get("code", ""))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(refill, [0, 1]))

    assert outcomes == [(200, ""), (409, "HEARTS_FULL")]
    stored = db_user(user_id)
    assert stored.nectar == 10
    assert stored.hearts == 5


def test_dos_lecciones_distintas_completadas_a_la_vez(
    client: TestClient, user: tuple[str, str]
) -> None:
    """Dos pestañas: dos sesiones distintas compiten por la racha, la actividad y los logros."""
    token, user_id = user
    sessions = [start(client, token, L1), start(client, token, L1)]
    for session in sessions:
        answer_all(client, token, session)

    def finish(index: int) -> JsonObject:
        with TestClient(client.app) as other:
            return complete(other, token, session_id_of(sessions[index]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finish, [0, 1]))

    assert [row.achievement_id for row in db_user_achievements(user_id)] == ["FIRST_LESSON"]
    assert sum(len(new_achievements(r)) for r in results) == 1
    assert sorted(bool(streak_of(r)["extended"]) for r in results) == [False, True]
    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].lessons == 2
    stored = db_user(user_id)
    assert stored.nectar == sum(as_int(r["nectarEarned"]) for r in results) + 10
    streak = db_streak(user_id)
    assert streak is not None
    assert streak.current == 1
