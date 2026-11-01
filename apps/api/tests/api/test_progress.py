"""Tarea 7.1 — progreso: resumen, historial y resultados por unidad (R6.1 a R6.3; §8.2).

- `GET /api/progress/summary` → `{ percent, modules:[{id, title, order, percent}], totalXp, streak,
  signsLearned }`. Los porcentajes usan la misma regla que la ruta de aprendizaje
  (`module_progress_percent` / `round_half_up`: .5 hacia arriba): aprobadas (distintas) * 100 ÷
  lecciones de módulos publicados. `signsLearned` = señas introducidas en lecciones aprobadas.
- `GET /api/progress/history?page=1` → `{ items, page, pageSize, total }`: 20 por página, solo
  sesiones completadas del usuario, más recientes primero.
- `GET /api/progress/units` → promedio entero (hacia abajo) del puntaje y precisión
  (correctas * 100 // respuestas con puntaje) por módulo y nodo; `null` si no hay datos.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
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
from app.domain.dates import TZ
from app.infra.db import get_engine
from app.infra.models import Exercise, Lesson, LessonSession, Module, Node, Sign, User
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
OTHER_EMAIL = "beto@ejemplo.com"

BASE_DAY = (datetime.now(TZ) - timedelta(days=10)).date()

L1 = "M1-N1-L1"  # Aprende: aprobar da 20 XP
L2 = "M1-N1-L2"

SUMMARY_KEYS = {"percent", "modules", "totalXp", "streak", "signsLearned"}
SUMMARY_MODULE_KEYS = {"id", "title", "order", "percent"}
HISTORY_KEYS = {"items", "page", "pageSize", "total"}
HISTORY_ITEM_KEYS = {
    "sessionId",
    "lessonId",
    "lessonTitle",
    "nodeTitle",
    "completedAt",
    "score",
    "passed",
    "xpEarned",
}
UNITS_KEYS = {"modules"}
UNIT_MODULE_KEYS = {"id", "title", "order", "averageScore", "accuracy", "nodes"}
UNIT_NODE_KEYS = {"id", "title", "order", "averageScore", "accuracy"}

PAGE_SIZE = 20


def local(day: int, hour: int, minute: int = 0) -> datetime:
    moment = datetime.combine(BASE_DAY + timedelta(days=day), time(hour, minute), tzinfo=TZ)
    return moment.astimezone(UTC)


def day_str(day: int) -> str:
    return (BASE_DAY + timedelta(days=day)).isoformat()


T0 = local(0, 10)


def half_up(a: int, b: int) -> int:
    """a / b con .5 hacia arriba, solo enteros (la regla de la ruta de aprendizaje)."""
    return (2 * a + b) // (2 * b)


# ---------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def hearts_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
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
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return as_str(json_of(response)["accessToken"])


def move_to(client: TestClient, clock: FakeClock, moment: datetime, email: str = EMAIL) -> str:
    clock.set(moment)
    return login(client, email)


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
    sid = session_id_of(session)
    for exercise_id in exercise_ids(session):
        body: dict[str, object] | None = None
        if wrong is not None and exercise_id in wrong:
            body = wrong_answer(sid, exercise_id)
        if body is None:
            body = correct_answer(sid, exercise_id)
        post_answer(client, token, sid, exercise_id, body)


def complete(client: TestClient, token: str, session_id: str) -> JsonObject:
    response = client.post(f"/api/lesson-sessions/{session_id}/complete", headers=auth(token))
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
    result = complete(client, token, session_id_of(session))
    result["_sessionId"] = session_id_of(session)
    return result


def get_summary(client: TestClient, token: str) -> JsonObject:
    response = client.get("/api/progress/summary", headers=auth(token))
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert set(body) == SUMMARY_KEYS
    for module in as_list(body["modules"]):
        assert set(module) == SUMMARY_MODULE_KEYS
    return body


def get_history(client: TestClient, token: str, page: int | None = None) -> JsonObject:
    params = {} if page is None else {"page": page}
    response = client.get("/api/progress/history", headers=auth(token), params=params)
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert set(body) == HISTORY_KEYS
    for item in as_list(body["items"]):
        assert set(item) == HISTORY_ITEM_KEYS
    return body


def get_units(client: TestClient, token: str) -> JsonObject:
    response = client.get("/api/progress/units", headers=auth(token))
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert set(body) == UNITS_KEYS
    for module in as_list(body["modules"]):
        assert set(module) == UNIT_MODULE_KEYS
        for node in as_list(module["nodes"]):
            assert set(node) == UNIT_NODE_KEYS
    return body


def summary_module(body: JsonObject, module_id: str) -> JsonObject:
    return next(m for m in as_list(body["modules"]) if m["id"] == module_id)


def unit_module(body: JsonObject, module_id: str) -> JsonObject:
    return next(m for m in as_list(body["modules"]) if m["id"] == module_id)


def unit_node(body: JsonObject, node_id: str) -> JsonObject:
    for module in as_list(body["modules"]):
        for node in as_list(module["nodes"]):
            if node["id"] == node_id:
                return node
    raise AssertionError(f"Nodo {node_id} no está en /progress/units")


# ---------------------------------------------------------------- ayudas de BD


def published_modules() -> list[Module]:
    with Session(get_engine()) as db:
        rows = list(
            db.execute(
                select(Module).where(Module.published.is_(True)).order_by(Module.order)
            ).scalars()
        )
        for row in rows:
            db.expunge(row)
        return rows


def nodes_of(module_id: str) -> list[Node]:
    with Session(get_engine()) as db:
        rows = list(
            db.execute(
                select(Node).where(Node.module_id == module_id).order_by(Node.order)
            ).scalars()
        )
        for row in rows:
            db.expunge(row)
        return rows


def lessons_in_order(module_id: str | None = None) -> list[str]:
    """Lecciones de módulos publicados en el orden global (o solo de `module_id`)."""
    with Session(get_engine()) as db:
        query = (
            select(Lesson.id)
            .join(Node, Node.id == Lesson.node_id)
            .join(Module, Module.id == Node.module_id)
            .where(Module.published.is_(True))
        )
        if module_id is not None:
            query = query.where(Module.id == module_id)
        rows = db.execute(query.order_by(Module.order, Node.order, Lesson.order)).scalars()
        return list(rows)


def lesson_row(lesson_id: str) -> Lesson:
    with Session(get_engine()) as db:
        found = db.get(Lesson, lesson_id)
        assert found is not None
        db.expunge(found)
        return found


def node_title(node_id: str) -> str:
    with Session(get_engine()) as db:
        found = db.get(Node, node_id)
        assert found is not None
        return found.title


def signs_introduced_in(lesson_ids: set[str]) -> set[str]:
    with Session(get_engine()) as db:
        rows = db.execute(
            select(Sign.id).where(Sign.introduced_in_lesson_id.in_(lesson_ids)).order_by(Sign.id)
        ).scalars()
        return set(rows)


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


def set_user_values(user_id: str, **values: object) -> None:
    with Session(get_engine()) as db:
        db.execute(update(User).where(User.id == uuid.UUID(user_id)).values(**values))
        db.commit()


def set_streak(
    user_id: str,
    *,
    current: int = 0,
    longest: int = 0,
    freezes: int = 0,
    last_active_day: str | None = None,
) -> None:
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


def insert_completed_session(
    user_id: str,
    lesson_id: str,
    completed_at: datetime | None,
    *,
    score: int = 100,
    passed: bool = True,
    xp: int = 10,
) -> str:
    """Inserta una sesión (cerrada, o abierta si `completed_at` es None); devuelve su id."""
    session_id = uuid.uuid4()
    started = (completed_at or T0) - timedelta(minutes=3)
    with Session(get_engine()) as db:
        db.add(
            LessonSession(
                id=session_id,
                user_id=uuid.UUID(user_id),
                lesson_id=lesson_id,
                started_at=started,
                completed_at=completed_at,
                hearts_lost=0,
                score=score if completed_at is not None else None,
                correct=score // 10 if completed_at is not None else None,
                total=10 if completed_at is not None else None,
                passed=passed if completed_at is not None else None,
                xp_earned=xp if completed_at is not None else None,
                nectar_earned=0 if completed_at is not None else None,
                duration_sec=180 if completed_at is not None else None,
            )
        )
        db.commit()
    return str(session_id)


# ================================================================ autenticación


@pytest.mark.parametrize(
    "path", ["/api/progress/summary", "/api/progress/history", "/api/progress/units"]
)
def test_endpoints_de_progreso_sin_token_401(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    "path", ["/api/progress/summary", "/api/progress/history", "/api/progress/units"]
)
def test_endpoints_de_progreso_con_token_invalido_401(client: TestClient, path: str) -> None:
    assert client.get(path, headers=auth("no-es-un-token")).status_code == 401


# ================================================================ summary


def test_resumen_de_usuario_nuevo_todo_en_cero(client: TestClient, user: tuple[str, str]) -> None:
    """R6.1: usuario nuevo → 0 % global y por módulo, 0 XP, racha 0, 0 señas."""
    token, _ = user
    body = get_summary(client, token)

    assert body["percent"] == 0
    assert body["totalXp"] == 0
    assert body["streak"] == 0
    assert body["signsLearned"] == 0
    assert body["modules"] == [
        {"id": m.id, "title": m.title, "order": m.order, "percent": 0} for m in published_modules()
    ]


def test_resumen_solo_incluye_modulos_publicados_en_orden(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, _ = user
    modules = as_list(get_summary(client, token)["modules"])
    published = published_modules()
    assert len(published) >= 1
    assert [m["id"] for m in modules] == [m.id for m in published]
    orders = [as_int(m["order"]) for m in modules]
    assert orders == sorted(orders)
    assert "M4" not in {m["id"] for m in modules}  # M4 no está publicado en el contenido


def test_resumen_despues_de_aprobar_l1(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R6.1: avance global y de M1 con la misma regla de la ruta, XP, racha y señas de L1."""
    token, _ = user
    result = do_lesson(client, token, clock)
    assert result["passed"] is True

    body = get_summary(client, token)
    total = len(lessons_in_order())
    m1_total = len(lessons_in_order("M1"))
    assert body["percent"] == half_up(100, total)
    assert summary_module(body, "M1")["percent"] == half_up(100, m1_total)
    for module in as_list(body["modules"]):
        if module["id"] != "M1":
            assert module["percent"] == 0
    assert body["totalXp"] == 20
    assert body["streak"] == 1
    introduced = signs_introduced_in({L1})
    assert len(introduced) > 0
    assert body["signsLearned"] == len(introduced)


def test_resumen_leccion_reprobada_no_cuenta_como_avance_ni_senas(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    result = do_lesson(client, token, clock, wrong_all_scored=True)
    assert result["passed"] is False

    body = get_summary(client, token)
    assert body["percent"] == 0
    assert summary_module(body, "M1")["percent"] == 0
    assert body["signsLearned"] == 0
    assert body["totalXp"] == 0
    assert body["streak"] == 1  # reprobar también cuenta como actividad (R5.3)


def test_resumen_cuenta_lecciones_aprobadas_distintas(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """Repetir L1 aprobada no suma avance ni señas otra vez."""
    token, _ = user
    do_lesson(client, token, clock)
    do_lesson(client, token, clock)

    body = get_summary(client, token)
    assert body["percent"] == half_up(100, len(lessons_in_order()))
    assert summary_module(body, "M1")["percent"] == half_up(100, len(lessons_in_order("M1")))
    assert body["signsLearned"] == len(signs_introduced_in({L1}))
    assert body["totalXp"] == 30  # 20 + 10 (repetida)


def test_resumen_porcentajes_redondean_hacia_arriba_en_punto_cinco(
    client: TestClient, user: tuple[str, str]
) -> None:
    """Corrección del coordinador: misma regla que /learning-path (`round_half_up`), no floor."""
    token, user_id = user
    m1 = lessons_in_order("M1")
    total = len(lessons_in_order())
    # Primer k cuyo porcentaje de M1 difiere entre floor y redondeo .5 hacia arriba.
    candidates = [k for k in range(1, len(m1)) if half_up(k * 100, len(m1)) != k * 100 // len(m1)]
    assert candidates, "Premisa: el contenido debe tener un k donde floor ≠ redondeo"
    k = candidates[0]
    for lesson_id in m1[:k]:
        complete_lesson(user_id, lesson_id, 100, True)

    body = get_summary(client, token)
    assert summary_module(body, "M1")["percent"] == half_up(k * 100, len(m1))
    assert summary_module(body, "M1")["percent"] != k * 100 // len(m1)
    assert body["percent"] == half_up(k * 100, total)


def test_resumen_porcentaje_global_coincide_con_la_ruta(
    client: TestClient, user: tuple[str, str]
) -> None:
    """Global = round_half_up(aprobadas * 100, lecciones publicadas); por módulo, igual."""
    token, user_id = user
    ordered = lessons_in_order()
    approved = ordered[:7]
    for lesson_id in approved:
        complete_lesson(user_id, lesson_id, 90, True)
    complete_lesson(user_id, ordered[7], 40, False)  # reprobada: no cuenta

    body = get_summary(client, token)
    assert body["percent"] == half_up(len(approved) * 100, len(ordered))
    for module in published_modules():
        lessons = lessons_in_order(module.id)
        done = sum(1 for lesson_id in approved if lesson_id in lessons)
        assert summary_module(body, module.id)["percent"] == half_up(done * 100, len(lessons))


def test_resumen_todo_m1_aprobado_da_100_en_m1(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    m1 = lessons_in_order("M1")
    for lesson_id in m1:
        complete_lesson(user_id, lesson_id, 100, True)

    body = get_summary(client, token)
    assert summary_module(body, "M1")["percent"] == 100
    assert body["percent"] == half_up(len(m1) * 100, len(lessons_in_order()))
    assert body["signsLearned"] == len(signs_introduced_in(set(m1)))


def test_resumen_senas_aprendidas_son_las_introducidas_en_lecciones_aprobadas(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    ordered = lessons_in_order()
    approved = set(ordered[:3])
    for lesson_id in approved:
        complete_lesson(user_id, lesson_id, 100, True)
    complete_lesson(user_id, ordered[3], 30, False)
    complete_lesson(user_id, ordered[4], 100, True, completed_at=None)  # abierta: no cuenta

    expected = signs_introduced_in(approved)
    assert as_int(get_summary(client, token)["signsLearned"]) == len(expected)


def test_resumen_no_mezcla_el_progreso_de_otro_usuario(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    other_token, _ = register_user(client, OTHER_EMAIL)
    do_lesson(client, other_token, clock)

    body = get_summary(client, token)
    assert body["percent"] == 0
    assert body["totalXp"] == 0
    assert body["streak"] == 0
    assert body["signsLearned"] == 0


def test_resumen_racha_caducada_se_muestra_en_0(client: TestClient, user: tuple[str, str]) -> None:
    """`streak` es la racha mostrada (StreakPolicy.display), no la guardada."""
    token, user_id = user
    set_streak(user_id, current=5, longest=7, last_active_day=day_str(-3))
    assert get_summary(client, token)["streak"] == 0


def test_resumen_racha_de_ayer_se_muestra(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    set_streak(user_id, current=5, longest=7, last_active_day=day_str(-1))
    assert get_summary(client, token)["streak"] == 5


def test_resumen_racha_salvable_con_protector_se_muestra(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_streak(user_id, current=4, longest=4, freezes=1, last_active_day=day_str(-2))
    assert get_summary(client, token)["streak"] == 4


def test_resumen_total_xp_es_el_del_usuario(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    set_user_values(user_id, total_xp=345)
    assert get_summary(client, token)["totalXp"] == 345


# ================================================================ history


def test_historial_de_usuario_nuevo_vacio(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    assert get_history(client, token) == {"items": [], "page": 1, "pageSize": 20, "total": 0}


def test_historial_con_una_leccion_completada(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R6.2: fecha, lección, puntaje y XP."""
    token, _ = user
    result = do_lesson(client, token, clock, minutes=3)

    body = get_history(client, token)
    assert body["page"] == 1
    assert body["pageSize"] == PAGE_SIZE
    assert body["total"] == 1
    items = as_list(body["items"])
    assert len(items) == 1
    item = items[0]
    lesson = lesson_row(L1)
    assert item["sessionId"] == result["_sessionId"]
    assert item["lessonId"] == L1
    assert item["lessonTitle"] == lesson.title
    assert item["nodeTitle"] == node_title(lesson.node_id)
    assert parse_iso(item["completedAt"]) == T0 + timedelta(minutes=3)
    assert item["score"] == result["score"]
    assert item["passed"] is True
    assert item["xpEarned"] == 20


def test_historial_leccion_reprobada_aparece_con_0_xp(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    result = do_lesson(client, token, clock, wrong_all_scored=True)
    item = as_list(get_history(client, token)["items"])[0]
    assert item["passed"] is False
    assert item["xpEarned"] == 0
    assert item["score"] == result["score"]


def test_historial_no_incluye_sesiones_abiertas(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    start(client, token, L1)  # sin completar
    assert get_history(client, token) == {"items": [], "page": 1, "pageSize": 20, "total": 0}

    do_lesson(client, token, clock)
    body = get_history(client, token)
    assert body["total"] == 1
    assert len(as_list(body["items"])) == 1


def test_historial_no_incluye_sesiones_de_otro_usuario(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    other_token, _ = register_user(client, OTHER_EMAIL)
    do_lesson(client, other_token, clock)
    assert get_history(client, token)["total"] == 0
    assert get_history(client, other_token)["total"] == 1


def test_historial_mas_recientes_primero(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    first = do_lesson(client, token, clock, minutes=1)
    clock.advance(minutes=10)
    token = login(client)  # el token de acceso dura 15 min
    second = do_lesson(client, token, clock, L2, minutes=1)
    clock.advance(minutes=10)
    token = login(client)
    third = do_lesson(client, token, clock, minutes=1)

    items = as_list(get_history(client, token)["items"])
    assert [item["sessionId"] for item in items] == [
        third["_sessionId"],
        second["_sessionId"],
        first["_sessionId"],
    ]
    assert [item["lessonId"] for item in items] == [L1, L2, L1]
    moments = [parse_iso(item["completedAt"]) for item in items]
    assert moments == sorted(moments, reverse=True)


def test_historial_pagina_de_20_en_20(client: TestClient, user: tuple[str, str]) -> None:
    """R6.2: 25 sesiones → 20 en la página 1, 5 en la 2 y la 3 vacía."""
    token, user_id = user
    created = [
        insert_completed_session(user_id, L1, T0 - timedelta(hours=i), score=50 + i)
        for i in range(25)
    ]  # created[0] es la más reciente

    page1 = get_history(client, token)
    assert page1["page"] == 1
    assert page1["pageSize"] == 20
    assert page1["total"] == 25
    assert [i["sessionId"] for i in as_list(page1["items"])] == created[:20]

    page2 = get_history(client, token, 2)
    assert page2["page"] == 2
    assert page2["pageSize"] == 20
    assert page2["total"] == 25
    assert [i["sessionId"] for i in as_list(page2["items"])] == created[20:]

    page3 = get_history(client, token, 3)
    assert page3 == {"items": [], "page": 3, "pageSize": 20, "total": 25}


def test_historial_pagina_por_defecto_es_la_1(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    for i in range(3):
        insert_completed_session(user_id, L1, T0 - timedelta(hours=i))
    assert get_history(client, token) == get_history(client, token, 1)


def test_historial_exactamente_20_no_tiene_segunda_pagina(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    for i in range(20):
        insert_completed_session(user_id, L1, T0 - timedelta(minutes=i))
    assert len(as_list(get_history(client, token, 1)["items"])) == 20
    assert get_history(client, token, 2)["items"] == []


def test_historial_empates_de_fecha_paginan_sin_repetir_ni_perder(
    client: TestClient, user: tuple[str, str]
) -> None:
    """Desempate por id: con la misma `completedAt`, las páginas no se solapan."""
    token, user_id = user
    created = {insert_completed_session(user_id, L1, T0) for _ in range(25)}

    page1 = [as_str(i["sessionId"]) for i in as_list(get_history(client, token, 1)["items"])]
    page2 = [as_str(i["sessionId"]) for i in as_list(get_history(client, token, 2)["items"])]
    assert len(page1) == 20
    assert len(page2) == 5
    assert set(page1) | set(page2) == created
    assert not set(page1) & set(page2)
    again = [as_str(i["sessionId"]) for i in as_list(get_history(client, token, 1)["items"])]
    assert again == page1  # orden estable


@pytest.mark.parametrize("page", ["0", "-1", "abc"])
def test_historial_pagina_invalida_422(
    client: TestClient, user: tuple[str, str], page: str
) -> None:
    token, _ = user
    response = client.get(f"/api/progress/history?page={page}", headers=auth(token))
    assert response.status_code == 422, response.text
    body = json_of(response)
    assert body["statusCode"] == 422
    assert body["code"] == "VALIDATION_ERROR"


def test_historial_fecha_con_zona_horaria(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """La fecha la fija el Clock (D22) y se expone con zona horaria (a las 23:30 de Bogotá)."""
    token, _ = user
    token = move_to(client, clock, local(0, 23, 30))
    do_lesson(client, token, clock)
    item = as_list(get_history(client, token)["items"])[0]
    assert parse_iso(item["completedAt"]) == local(0, 23, 30)


# ================================================================ units


def test_unidades_de_usuario_nuevo_sin_datos(client: TestClient, user: tuple[str, str]) -> None:
    """R6.3: sin sesiones → promedio y precisión `null` en todos los módulos y nodos."""
    token, _ = user
    body = get_units(client, token)
    assert body["modules"] == [
        {
            "id": m.id,
            "title": m.title,
            "order": m.order,
            "averageScore": None,
            "accuracy": None,
            "nodes": [
                {
                    "id": n.id,
                    "title": n.title,
                    "order": n.order,
                    "averageScore": None,
                    "accuracy": None,
                }
                for n in nodes_of(m.id)
            ],
        }
        for m in published_modules()
    ]


def test_unidades_solo_modulos_publicados(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    modules = as_list(get_units(client, token)["modules"])
    assert [m["id"] for m in modules] == [m.id for m in published_modules()]
    assert "M4" not in {m["id"] for m in modules}


def test_unidades_leccion_perfecta_da_100_y_100(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    do_lesson(client, token, clock)

    body = get_units(client, token)
    node_id = lesson_row(L1).node_id
    assert unit_node(body, node_id)["averageScore"] == 100
    assert unit_node(body, node_id)["accuracy"] == 100
    assert unit_module(body, "M1")["averageScore"] == 100
    assert unit_module(body, "M1")["accuracy"] == 100
    for node in nodes_of("M1"):
        if node.id != node_id:
            assert unit_node(body, node.id)["averageScore"] is None
            assert unit_node(body, node.id)["accuracy"] is None
    for module in published_modules():
        if module.id != "M1":
            assert unit_module(body, module.id)["averageScore"] is None
            assert unit_module(body, module.id)["accuracy"] is None


def test_unidades_promedio_y_precision_con_division_entera_hacia_abajo(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """Dos sesiones de L1: perfecta y con un error. Promedio y precisión truncan (no redondean)."""
    token, _ = user
    scored = [e for e in db_exercises(L1) if e.scored]
    n = len(scored)
    assert n >= 2
    target = next(e for e in scored if e.type.value == "VIDEO_TO_MEANING")

    first = do_lesson(client, token, clock)
    second = do_lesson(client, token, clock, wrong={target.id})
    assert first["score"] == 100
    second_score = as_int(second["score"])
    assert second_score < 100

    expected_average = (100 + second_score) // 2
    expected_accuracy = (2 * n - 1) * 100 // (2 * n)
    body = get_units(client, token)
    node = unit_node(body, lesson_row(L1).node_id)
    assert node["averageScore"] == expected_average
    assert node["accuracy"] == expected_accuracy
    assert unit_module(body, "M1")["averageScore"] == expected_average
    assert unit_module(body, "M1")["accuracy"] == expected_accuracy


def test_unidades_promedio_trunca_y_excluye_sesiones_abiertas(
    client: TestClient, user: tuple[str, str]
) -> None:
    """Puntajes 100, 81 y 70 → 251 // 3 = 83 (con redondeo serían 84). Sin respuestas → null."""
    token, user_id = user
    node_lessons = [lesson for lesson in lessons_in_order("M1") if lesson.startswith("M1-N1-")]
    assert len(node_lessons) >= 3
    insert_completed_session(user_id, node_lessons[0], T0 - timedelta(hours=3), score=100)
    insert_completed_session(user_id, node_lessons[1], T0 - timedelta(hours=2), score=81)
    insert_completed_session(
        user_id, node_lessons[2], T0 - timedelta(hours=1), score=70, passed=False
    )
    insert_completed_session(user_id, node_lessons[0], None)  # abierta: no cuenta

    body = get_units(client, token)
    node = unit_node(body, "M1-N1")
    assert node["averageScore"] == 83
    assert node["accuracy"] is None  # ninguna respuesta registrada
    assert unit_module(body, "M1")["averageScore"] == 83
    assert unit_module(body, "M1")["accuracy"] is None


def test_unidades_promedio_del_modulo_junta_todos_sus_nodos(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    nodes = nodes_of("M1")
    assert len(nodes) >= 2
    first_lessons = {
        node.id: next(
            lesson for lesson in lessons_in_order("M1") if lesson.startswith(f"{node.id}-")
        )
        for node in nodes[:2]
    }
    insert_completed_session(user_id, first_lessons[nodes[0].id], T0, score=90)
    insert_completed_session(user_id, first_lessons[nodes[0].id], T0, score=70)
    insert_completed_session(user_id, first_lessons[nodes[1].id], T0, score=55)

    body = get_units(client, token)
    assert unit_node(body, nodes[0].id)["averageScore"] == 80
    assert unit_node(body, nodes[1].id)["averageScore"] == 55
    assert unit_module(body, "M1")["averageScore"] == (90 + 70 + 55) // 3  # 71


def test_unidades_precision_ignora_ejercicios_sin_puntaje(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """PRODUCE con «Necesito repasar» (sin puntaje) no baja la precisión."""
    token, _ = user
    produce = next(e for e in db_exercises(L1) if e.type.value == "PRODUCE")
    assert produce.scored is False
    session = start(client, token, L1)
    sid = session_id_of(session)
    for exercise_id in exercise_ids(session):
        if exercise_id == produce.id:
            post_answer(client, token, sid, exercise_id, {"method": "self", "ok": False})
        else:
            post_answer(client, token, sid, exercise_id, correct_answer(sid, exercise_id))
    complete(client, token, sid)

    node = unit_node(get_units(client, token), lesson_row(L1).node_id)
    assert node["accuracy"] == 100


def test_unidades_leccion_toda_mal_da_precision_0(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    result = do_lesson(client, token, clock, wrong_all_scored=True)
    node = unit_node(get_units(client, token), lesson_row(L1).node_id)
    assert node["accuracy"] == 0
    assert node["averageScore"] == result["score"]


def test_unidades_no_mezclan_datos_de_otro_usuario(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    do_lesson(client, token, clock)
    other_token, _ = register_user(client, OTHER_EMAIL)
    do_lesson(client, other_token, clock, wrong_all_scored=True)

    node = unit_node(get_units(client, token), lesson_row(L1).node_id)
    assert node["averageScore"] == 100
    assert node["accuracy"] == 100
    other_node = unit_node(get_units(client, other_token), lesson_row(L1).node_id)
    assert other_node["accuracy"] == 0


def test_precision_excluye_respuestas_de_sesiones_abandonadas(
    client: TestClient, user: tuple[str, str]
) -> None:
    """Revisión del Grupo 7: una lección empezada, fallada y abandonada no baja la precisión
    (el promedio tampoco la cuenta)."""
    token, _ = user
    session = start(client, token, L1)
    answer_all(client, token, session, wrong=set(scored_ids(session)))

    node = unit_node(get_units(client, token), "M1-N1")
    assert node["averageScore"] is None
    assert node["accuracy"] is None
