"""Tareas 7.2 y 7.3 — repaso espaciado evaluado en el servidor (R6.4 a R6.8, R5.5, R5.14;
§7.7, §8.2, §8.5; D23, D-013).

- `GET /api/reviews/queue` → `{ due, signs:[{word}] }` (hasta 15, menor fuerza primero).
- `POST /api/reviews/sessions` → 201 `{ sessionId, exercises:[{id:"R-01", type, content}] }`;
  409 `NO_REVIEWS_DUE` sin señas vencidas; reutiliza la sesión abierta de hoy.
- `POST /api/review-sessions/{id}/answers` → `{ correct, correctToken, correctTokens, correctWord,
  alreadyAnswered }`. No quita vidas.
- `POST /api/review-sessions/{id}/complete` → `{ correct, total, score, streak:{current, extended},
  heartsGained, newAchievements }`. Idempotente, SERIALIZABLE; reprograma señas, cuenta para la
  racha, +1 vida con ≥ 80 %, sin XP ni néctar (salvo logros de racha).

El cliente nunca declara sus aciertos (D23): las respuestas correctas las calcula la prueba con el
secreto del servidor a partir de `review_sessions.items` (cada item: `{id, type, signId, payload}`).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta
from itertools import pairwise

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
from app.domain.exercises.models import (
    SIDE_VIDEO,
    SIDE_WORD,
    MeaningToVideoPayload,
    VideoToMeaningPayload,
    parse_payload,
)
from app.infra.db import get_engine
from app.infra.models import (
    DailyActivity,
    Exercise,
    Lesson,
    Module,
    Node,
    ReviewAnswer,
    ReviewSession,
    Sign,
    User,
    UserAchievement,
)
from app.infra.models import SignReview as SignReviewRow
from app.infra.models import Streak as StreakRow
from tests.api.helpers import (
    PASSWORD,
    auth,
    correct_answer,
    register_user,
    tokenizer,
    wrong_answer,
)
from tests.fakes import FakeClock

pytestmark = pytest.mark.usefixtures("seeded_content")

JsonObject = dict[str, object]

EMAIL = "ana@ejemplo.com"
OTHER_EMAIL = "beto@ejemplo.com"

BASE_DAY = (datetime.now(TZ) - timedelta(days=10)).date()

L1 = "M1-N1-L1"

INTERVALS = (1, 2, 4, 7, 15, 30)  # §7.7
MAX_REVIEW = 15
REVIEW_TYPES = {"VIDEO_TO_MEANING", "MEANING_TO_VIDEO"}

QUEUE_KEYS = {"due", "signs"}
START_KEYS = {"sessionId", "exercises"}
REVIEW_ANSWER_KEYS = {"correct", "correctToken", "correctTokens", "correctWord", "alreadyAnswered"}
REVIEW_COMPLETE_KEYS = {"correct", "total", "score", "streak", "heartsGained", "newAchievements"}
NEW_ACHIEVEMENT_KEYS = {"id", "title", "nectar"}
FORBIDDEN_KEYS = {"correctId", "signId", "optionIds", "signIds", "letterIds", "correctToken"}
ITEM_ID = re.compile(r"^R-\d{2}$")
TOKEN = re.compile(r"^[0-9a-f]{10}$")

STREAK_3 = {"id": "STREAK_3", "title": "Aleteo constante", "nectar": 15}


def local(day: int, hour: int, minute: int = 0) -> datetime:
    moment = datetime.combine(BASE_DAY + timedelta(days=day), time(hour, minute), tzinfo=TZ)
    return moment.astimezone(UTC)


def day_str(day: int) -> str:
    return (BASE_DAY + timedelta(days=day)).isoformat()


T0 = local(0, 10)


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


# ---------------------------------------------------------------- ayudas HTTP genéricas


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


def login(client: TestClient, email: str = EMAIL) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return as_str(json_of(response)["accessToken"])


def move_to(client: TestClient, clock: FakeClock, moment: datetime, email: str = EMAIL) -> str:
    clock.set(moment)
    return login(client, email)


def assert_error(response: Response, status: int, code: str) -> JsonObject:
    assert response.status_code == status, response.text
    body = json_of(response)
    assert body["statusCode"] == status
    assert body["code"] == code
    assert isinstance(body["message"], str)
    assert body["message"]
    return body


def walk(value: object, key: str | None = None) -> Iterator[tuple[str | None, object]]:
    """Recorre todo el JSON y produce (clave, valor) de cada nodo."""
    yield key, value
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from walk(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from walk(child, key)


# ---------------------------------------------------------------- lecciones


def start_lesson(client: TestClient, token: str, lesson_id: str = L1) -> JsonObject:
    response = client.post(f"/api/lessons/{lesson_id}/sessions", headers=auth(token))
    assert response.status_code == 201, response.text
    return json_of(response)


def do_lesson(
    client: TestClient, token: str, lesson_id: str = L1, *, wrong: set[str] | None = None
) -> JsonObject:
    """Empieza, responde todo (bien salvo `wrong`) y completa la lección."""
    session = start_lesson(client, token, lesson_id)
    sid = as_str(session["sessionId"])
    for exercise in as_list(session["exercises"]):
        exercise_id = as_str(exercise["id"])
        body: dict[str, object] | None = None
        if wrong is not None and exercise_id in wrong:
            body = wrong_answer(sid, exercise_id)
        if body is None:
            body = correct_answer(sid, exercise_id)
        response = client.post(
            f"/api/lesson-sessions/{sid}/answers",
            headers=auth(token),
            json={"exerciseId": exercise_id, "answer": body},
        )
        assert response.status_code == 200, response.text
    response = client.post(f"/api/lesson-sessions/{sid}/complete", headers=auth(token))
    assert response.status_code == 200, response.text
    return json_of(response)


# ---------------------------------------------------------------- repaso (HTTP)


def get_queue(client: TestClient, token: str) -> JsonObject:
    response = client.get("/api/reviews/queue", headers=auth(token))
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert set(body) == QUEUE_KEYS
    for sign in as_list(body["signs"]):
        assert set(sign) == {"word"}
    return body


def post_start(client: TestClient, token: str) -> Response:
    response: Response = client.post("/api/reviews/sessions", headers=auth(token))
    return response


def start_review(client: TestClient, token: str) -> JsonObject:
    response = post_start(client, token)
    assert response.status_code == 201, response.text
    body = json_of(response)
    assert set(body) == START_KEYS
    return body


def review_id_of(session: JsonObject) -> str:
    return as_str(session["sessionId"])


def review_exercises(session: JsonObject) -> list[JsonObject]:
    return as_list(session["exercises"])


def post_review_answer(
    client: TestClient, token: str, session_id: str, item_id: str, answer: object
) -> Response:
    response: Response = client.post(
        f"/api/review-sessions/{session_id}/answers",
        headers=auth(token),
        json={"exerciseId": item_id, "answer": answer},
    )
    return response


def review_answer(
    client: TestClient, token: str, session_id: str, item_id: str, answer: object
) -> JsonObject:
    response = post_review_answer(client, token, session_id, item_id, answer)
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert set(body) == REVIEW_ANSWER_KEYS
    return body


def post_review_complete(client: TestClient, token: str, session_id: str) -> Response:
    response: Response = client.post(
        f"/api/review-sessions/{session_id}/complete", headers=auth(token)
    )
    return response


def complete_review(client: TestClient, token: str, session_id: str) -> JsonObject:
    response = post_review_complete(client, token, session_id)
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert set(body) == REVIEW_COMPLETE_KEYS
    assert set(as_obj(body["streak"])) == {"current", "extended"}
    for item in as_list(body["newAchievements"]):
        assert set(item) == NEW_ACHIEVEMENT_KEYS
    return body


def answer_review_all(
    client: TestClient, token: str, session: JsonObject, *, wrong_signs: set[str] | None = None
) -> None:
    """Responde todos los ejercicios del repaso: bien, salvo los de las señas en `wrong_signs`."""
    sid = review_id_of(session)
    for item in db_review_items(sid):
        item_id = as_str(item["id"])
        if wrong_signs is not None and item["signId"] in wrong_signs:
            review_answer(client, token, sid, item_id, review_wrong_answer(sid, item))
        else:
            review_answer(client, token, sid, item_id, review_correct_answer(sid, item))


def answer_review_count(
    client: TestClient, token: str, session: JsonObject, *, correct: int
) -> None:
    """Responde bien los primeros `correct` ejercicios (por id) y mal el resto."""
    sid = review_id_of(session)
    for index, item in enumerate(db_review_items(sid)):
        item_id = as_str(item["id"])
        body = (
            review_correct_answer(sid, item) if index < correct else review_wrong_answer(sid, item)
        )
        review_answer(client, token, sid, item_id, body)


def get_stats(client: TestClient, token: str) -> JsonObject:
    response = client.get("/api/gamification/stats", headers=auth(token))
    assert response.status_code == 200, response.text
    return json_of(response)


def hearts_now(client: TestClient, token: str) -> int:
    return as_int(as_obj(get_stats(client, token)["hearts"])["current"])


# ---------------------------------------------------------------- respuestas calculadas


def item_payload(item: JsonObject) -> VideoToMeaningPayload | MeaningToVideoPayload:
    payload = parse_payload(item["payload"])
    assert isinstance(payload, VideoToMeaningPayload | MeaningToVideoPayload), payload
    return payload


def item_side(payload: VideoToMeaningPayload | MeaningToVideoPayload) -> str:
    return SIDE_WORD if isinstance(payload, VideoToMeaningPayload) else SIDE_VIDEO


def review_correct_token(session_id: str, item: JsonObject) -> str:
    payload = item_payload(item)
    return tokenizer(session_id, as_str(item["id"]))(item_side(payload), payload.correct_id)


def review_correct_answer(session_id: str, item: JsonObject) -> dict[str, object]:
    return {"optionToken": review_correct_token(session_id, item)}


def review_wrong_answer(session_id: str, item: JsonObject) -> dict[str, object]:
    payload = item_payload(item)
    other = next(o for o in payload.option_ids if o != payload.correct_id)
    return {"optionToken": tokenizer(session_id, as_str(item["id"]))(item_side(payload), other)}


# ---------------------------------------------------------------- ayudas de BD


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


def lesson_signs_in_order() -> list[str]:
    """Señas distintas con ejercicio en lecciones publicadas, en el orden del currículo."""
    with Session(get_engine()) as db:
        rows = db.execute(
            select(Exercise.sign_id, Exercise.lesson_id, Exercise.order)
            .join(Lesson, Lesson.id == Exercise.lesson_id)
            .join(Node, Node.id == Lesson.node_id)
            .join(Module, Module.id == Node.module_id)
            .where(Module.published.is_(True), Exercise.sign_id.is_not(None))
            .order_by(Module.order, Node.order, Lesson.order, Exercise.order)
        ).all()
    ordered: list[str] = []
    for sign_id, _, _ in rows:
        if sign_id is not None and sign_id not in ordered:
            ordered.append(sign_id)
    return ordered


def all_slugs() -> set[str]:
    with Session(get_engine()) as db:
        return set(db.execute(select(Sign.id).order_by(Sign.id)).scalars())


def sign_word(sign_id: str) -> str:
    with Session(get_engine()) as db:
        return db.execute(select(Sign.word).where(Sign.id == sign_id)).scalar_one()


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


def seed_reviews(user_id: str, entries: dict[str, tuple[int, int]]) -> None:
    """Crea o reemplaza filas de `sign_reviews`: sign_id → (strength, día relativo)."""
    with Session(get_engine()) as db:
        for sign_id, (strength, offset) in entries.items():
            db.merge(
                SignReviewRow(
                    user_id=uuid.UUID(user_id),
                    sign_id=sign_id,
                    strength=strength,
                    next_review_day=day_str(offset),
                    last_seen_at=T0 - timedelta(days=5),
                )
            )
        db.commit()


def seed_due(user_id: str, count: int, *, strength: int = 0, offset: int = 0) -> list[str]:
    """`count` señas vencidas (más 3 vistas que no vencen, para los distractores)."""
    signs = lesson_signs_in_order()
    assert len(signs) >= count + 3, "Premisa: el contenido tiene suficientes señas"
    due = signs[:count]
    entries = dict.fromkeys(due, (strength, offset))
    entries.update(dict.fromkeys(signs[count : count + 3], (3, 20)))
    seed_reviews(user_id, entries)
    return due


def db_reviews(user_id: str) -> dict[str, tuple[int, str]]:
    """sign_id → (strength, next_review_day)."""
    with Session(get_engine()) as db:
        rows = db.execute(
            select(SignReviewRow.sign_id, SignReviewRow.strength, SignReviewRow.next_review_day)
            .where(SignReviewRow.user_id == uuid.UUID(user_id))
            .order_by(SignReviewRow.sign_id)
        ).all()
        return {sign_id: (strength, next_day) for sign_id, strength, next_day in rows}


def db_review_session(session_id: str) -> ReviewSession:
    with Session(get_engine()) as db:
        found = db.get(ReviewSession, uuid.UUID(session_id))
        assert found is not None
        db.expunge(found)
        return found


def db_review_sessions(user_id: str) -> list[ReviewSession]:
    with Session(get_engine()) as db:
        rows = list(
            db.execute(
                select(ReviewSession)
                .where(ReviewSession.user_id == uuid.UUID(user_id))
                .order_by(ReviewSession.started_at, ReviewSession.id)
            ).scalars()
        )
        for row in rows:
            db.expunge(row)
        return rows


def db_review_items(session_id: str) -> list[JsonObject]:
    """Items guardados (con respuesta, solo servidor), ordenados por id (R-01, R-02…)."""
    items = [as_obj(item) for item in db_review_session(session_id).items]
    for item in items:
        assert {"id", "type", "signId", "payload"} <= set(item), item
    return sorted(items, key=lambda item: as_str(item["id"]))


def db_review_answers(session_id: str) -> list[ReviewAnswer]:
    with Session(get_engine()) as db:
        rows = list(
            db.execute(
                select(ReviewAnswer)
                .where(ReviewAnswer.session_id == uuid.UUID(session_id))
                .order_by(ReviewAnswer.item_id)
            ).scalars()
        )
        for row in rows:
            db.expunge(row)
        return rows


def db_user(user_id: str) -> User:
    with Session(get_engine()) as db:
        found = db.get(User, uuid.UUID(user_id))
        assert found is not None
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


def db_streak(user_id: str) -> StreakRow | None:
    with Session(get_engine()) as db:
        found = db.get(StreakRow, uuid.UUID(user_id))
        if found is not None:
            db.expunge(found)
        return found


def db_user_achievement_ids(user_id: str) -> list[str]:
    with Session(get_engine()) as db:
        return list(
            db.execute(
                select(UserAchievement.achievement_id)
                .where(UserAchievement.user_id == uuid.UUID(user_id))
                .order_by(UserAchievement.achievement_id)
            ).scalars()
        )


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


# ================================================================ autenticación y D23


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/reviews/queue"),
        ("POST", "/api/reviews/sessions"),
        ("POST", f"/api/review-sessions/{uuid.uuid4()}/answers"),
        ("POST", f"/api/review-sessions/{uuid.uuid4()}/complete"),
    ],
)
def test_endpoints_de_repaso_sin_token_401(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path)
    assert response.status_code == 401, response.text


def test_no_existe_endpoint_donde_el_cliente_declare_sus_aciertos(client: TestClient) -> None:
    """D23, R6.7: las únicas rutas de repaso son la cola, iniciar, responder y completar."""
    app = client.app
    assert isinstance(app, FastAPI)
    paths = {re.sub(r"\{[^}]+\}", "{id}", path) for path in app.openapi()["paths"]}
    review_paths = {path for path in paths if "review" in path}
    assert review_paths == {
        "/api/reviews/queue",
        "/api/reviews/sessions",
        "/api/review-sessions/{id}/answers",
        "/api/review-sessions/{id}/complete",
    }


def test_complete_del_repaso_ignora_aciertos_enviados_por_el_cliente(
    client: TestClient, user: tuple[str, str]
) -> None:
    """Aunque el cliente mande `correct`/`total`, cuenta solo lo que evaluó el servidor."""
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    answer_review_count(client, token, session, correct=0)
    response = client.post(
        f"/api/review-sessions/{review_id_of(session)}/complete",
        headers=auth(token),
        json={"correct": 2, "total": 2, "score": 100},
    )
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert body["correct"] == 0
    assert body["score"] == 0


# ================================================================ cola


def test_cola_de_usuario_nuevo_vacia(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    assert get_queue(client, token) == {"due": 0, "signs": []}


def test_sena_fallada_en_l1_aparece_en_la_cola_al_dia_siguiente(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """R6.4 (integración): fallar una seña la programa para mañana; hoy no está vencida."""
    token, _ = user
    target = next(e for e in db_exercises(L1) if e.type.value == "VIDEO_TO_MEANING")
    assert target.sign_id is not None
    do_lesson(client, token, wrong={target.id})

    assert get_queue(client, token) == {"due": 0, "signs": []}
    assert_error(post_start(client, token), 409, "NO_REVIEWS_DUE")

    token = move_to(client, clock, local(1, 10))
    assert get_queue(client, token) == {"due": 1, "signs": [{"word": sign_word(target.sign_id)}]}


def test_leccion_perfecta_no_deja_repasos_para_manana_sino_en_dos_dias(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    do_lesson(client, token)
    token = move_to(client, clock, local(1, 10))
    assert get_queue(client, token)["due"] == 0
    token = move_to(client, clock, local(2, 10))
    assert get_queue(client, token)["due"] == 3


def test_cola_incluye_vencidas_hoy_y_atrasadas_pero_no_futuras(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    signs = lesson_signs_in_order()
    seed_reviews(
        user_id,
        {signs[0]: (1, 0), signs[1]: (1, -4), signs[2]: (1, 1), signs[3]: (1, 7)},
    )
    body = get_queue(client, token)
    assert body["due"] == 2
    assert {as_str(s["word"]) for s in as_list(body["signs"])} == {
        sign_word(signs[0]),
        sign_word(signs[1]),
    }


def test_cola_ordena_por_menor_fuerza_y_desempata_por_dia_y_sena(
    client: TestClient, user: tuple[str, str]
) -> None:
    """§7.7: menor `strength` primero; empate → `next_review_day`, luego `sign_id`."""
    token, user_id = user
    signs = sorted(lesson_signs_in_order()[:5])  # orden por sign_id
    seed_reviews(
        user_id,
        {
            signs[0]: (3, 0),
            signs[1]: (0, 0),
            signs[2]: (1, -2),
            signs[3]: (1, -5),
            signs[4]: (0, 0),
        },
    )
    expected = [signs[1], signs[4], signs[3], signs[2], signs[0]]
    body = get_queue(client, token)
    assert body["due"] == 5
    assert body["signs"] == [{"word": sign_word(s)} for s in expected]


def test_cola_muestra_como_maximo_15_pero_cuenta_todas(
    client: TestClient, user: tuple[str, str]
) -> None:
    """R6.6: 18 vencidas → due 18 y 15 señas (las de menor fuerza)."""
    token, user_id = user
    signs = lesson_signs_in_order()
    assert len(signs) >= 18
    weak = signs[:15]
    strong = signs[15:18]
    entries = dict.fromkeys(weak, (0, 0))
    entries.update(dict.fromkeys(strong, (4, 0)))
    seed_reviews(user_id, entries)

    body = get_queue(client, token)
    assert body["due"] == 18
    words = [as_str(s["word"]) for s in as_list(body["signs"])]
    assert len(words) == MAX_REVIEW
    assert set(words) == {sign_word(s) for s in weak}


def test_cola_usa_el_dia_de_bogota(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """A las 23:30 de Bogotá ya es mañana en UTC, pero una seña de mañana aún no vence."""
    _, user_id = user
    signs = lesson_signs_in_order()
    seed_reviews(user_id, {signs[0]: (0, 1), signs[1]: (0, 0)})
    token = move_to(client, clock, local(0, 23, 30))
    assert clock.now().date() != BASE_DAY
    body = get_queue(client, token)
    assert body == {"due": 1, "signs": [{"word": sign_word(signs[1])}]}

    token = move_to(client, clock, local(1, 0, 5))
    assert get_queue(client, token)["due"] == 2


def test_cola_no_mezcla_senas_de_otro_usuario(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    _, other_id = register_user(client, OTHER_EMAIL)
    seed_due(other_id, 4)
    assert get_queue(client, token) == {"due": 0, "signs": []}


# ================================================================ iniciar sesión de repaso


def test_iniciar_sin_senas_vencidas_409_no_reviews_due(
    client: TestClient, user: tuple[str, str]
) -> None:
    """R6.8: sin señas pendientes no se inicia el repaso (ni se crea sesión)."""
    token, user_id = user
    assert_error(post_start(client, token), 409, "NO_REVIEWS_DUE")
    assert db_review_sessions(user_id) == []


def test_iniciar_con_solo_senas_futuras_409(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    signs = lesson_signs_in_order()
    seed_reviews(user_id, {signs[0]: (2, 1), signs[1]: (0, 3)})
    assert_error(post_start(client, token), 409, "NO_REVIEWS_DUE")


def test_iniciar_devuelve_un_ejercicio_por_sena_vencida(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    due = seed_due(user_id, 4)
    session = start_review(client, token)

    exercises = review_exercises(session)
    assert [e["id"] for e in exercises] == ["R-01", "R-02", "R-03", "R-04"]
    for exercise in exercises:
        assert {"id", "type", "content"} <= set(exercise)
        assert exercise["type"] in REVIEW_TYPES
        assert as_obj(exercise["content"])["type"] == exercise["type"]
    stored = db_review_session(review_id_of(session))
    assert str(stored.user_id) == user_id
    assert stored.started_at == clock.now()  # D22
    assert stored.completed_at is None
    assert {item["signId"] for item in db_review_items(review_id_of(session))} == set(due)


def test_tipos_alternan_video_a_significado_y_significado_a_video(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    seed_due(user_id, 6)
    types = [e["type"] for e in review_exercises(start_review(client, token))]
    assert set(types) == REVIEW_TYPES
    for current, following in pairwise(types):
        assert current != following, types


def test_contenido_publico_de_cada_tipo(client: TestClient, user: tuple[str, str]) -> None:
    """Igual que en lecciones (§7.6): V→S con video y opciones de palabra; S→V al revés."""
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    items = {as_str(i["id"]): i for i in db_review_items(review_id_of(session))}
    for exercise in review_exercises(session):
        content = as_obj(exercise["content"])
        item = items[as_str(exercise["id"])]
        assert item["type"] == exercise["type"]
        options = as_list(content["options"])
        assert 2 <= len(options) <= 4
        sign = as_str(item["signId"])
        if exercise["type"] == "VIDEO_TO_MEANING":
            assert "video" in content
            for option in options:
                assert set(option) == {"token", "word"}
            assert sign_word(sign) in {o["word"] for o in options}
        else:
            assert content["word"] == sign_word(sign)
            for option in options:
                assert set(option) == {"token", "video"}


def test_maximo_15_ejercicios_por_sesion(client: TestClient, user: tuple[str, str]) -> None:
    """R6.6: con 18 vencidas, la sesión tiene 15 (las de menor fuerza)."""
    token, user_id = user
    signs = lesson_signs_in_order()
    weak = signs[:15]
    entries = dict.fromkeys(weak, (0, 0))
    entries.update(dict.fromkeys(signs[15:18], (4, 0)))
    seed_reviews(user_id, entries)

    session = start_review(client, token)
    exercises = review_exercises(session)
    assert len(exercises) == MAX_REVIEW
    assert [e["id"] for e in exercises] == [f"R-{i:02d}" for i in range(1, 16)]
    assert {i["signId"] for i in db_review_items(review_id_of(session))} == set(weak)


def test_respuestas_ocultas_y_tokens_sin_slugs(client: TestClient, user: tuple[str, str]) -> None:
    """PRUEBA OBLIGATORIA (D20, D23, R6.7): nada en el JSON permite deducir la respuesta."""
    token, user_id = user
    seed_due(user_id, 6)
    body = start_review(client, token)
    slugs = all_slugs()
    # Los slugs solo con letras hexadecimales no se distinguen de un token al azar.
    distinctive = [slug for slug in slugs if re.search(r"[^0-9a-f]", slug)]

    for key, value in walk(body):
        assert key not in FORBIDDEN_KEYS, f"Clave prohibida «{key}» en la respuesta"
        assert key != "cameraLabel"
        if isinstance(value, str):
            assert value not in slugs, f"Slug «{value}» expuesto en «{key}»"

    sid = review_id_of(body)
    for exercise in review_exercises(body):
        exercise_id = as_str(exercise["id"])
        assert ITEM_ID.match(exercise_id), exercise_id
        assert not any(slug in exercise_id for slug in distinctive)
        assert sid not in exercise_id
        for option in as_list(as_obj(exercise["content"])["options"]):
            token_value = as_str(option["token"])
            assert TOKEN.fullmatch(token_value), token_value
            assert token_value not in slugs
            assert not any(slug in token_value for slug in distinctive), token_value
        for key, value in walk(exercise["content"]):
            if key == "src" and isinstance(value, str):
                assert not any(slug in value for slug in distinctive), value


def test_iniciar_dos_veces_el_mismo_dia_devuelve_la_misma_sesion(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """§8.5: protege del doble montaje de StrictMode."""
    token, user_id = user
    seed_due(user_id, 3)
    first = start_review(client, token)
    clock.advance(minutes=5)
    response = post_start(client, token)
    assert response.status_code in (200, 201), response.text
    second = json_of(response)

    assert second["sessionId"] == first["sessionId"]
    assert second["exercises"] == first["exercises"]
    assert len(db_review_sessions(user_id)) == 1


def test_dos_inicios_simultaneos_crean_una_sola_sesion(
    client: TestClient, user: tuple[str, str]
) -> None:
    """B5 / doble montaje: dos POST a la vez → la misma sesión."""
    token, user_id = user
    seed_due(user_id, 3)

    def begin(_: int) -> tuple[int, str]:
        with TestClient(client.app) as other:
            response = post_start(other, token)
        return response.status_code, as_str(json_of(response)["sessionId"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(begin, [0, 1]))

    assert all(code in (200, 201) for code, _ in outcomes), outcomes
    assert outcomes[0][1] == outcomes[1][1]
    assert len(db_review_sessions(user_id)) == 1


def test_sesion_abierta_de_ayer_no_se_reutiliza(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    seed_due(user_id, 3)
    yesterday = start_review(client, token)

    token = move_to(client, clock, local(1, 10))
    today = start_review(client, token)
    assert today["sessionId"] != yesterday["sessionId"]
    assert len(db_review_sessions(user_id)) == 2


def test_sesion_de_otro_usuario_no_se_reutiliza(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    other_token, other_id = register_user(client, OTHER_EMAIL)
    seed_due(user_id, 2)
    seed_due(other_id, 2)
    mine = start_review(client, token)
    theirs = start_review(client, other_token)
    assert mine["sessionId"] != theirs["sessionId"]


def test_sesion_completada_no_se_reutiliza(client: TestClient, user: tuple[str, str]) -> None:
    """Tras completar, las señas quedan reprogramadas: el segundo inicio del día da 409."""
    token, user_id = user
    seed_due(user_id, 3)
    session = start_review(client, token)
    answer_review_all(client, token, session)
    complete_review(client, token, review_id_of(session))

    assert_error(post_start(client, token), 409, "NO_REVIEWS_DUE")
    assert len(db_review_sessions(user_id)) == 1


# ================================================================ responder


def test_respuesta_correcta(client: TestClient, user: tuple[str, str], clock: FakeClock) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    for item in db_review_items(sid):
        expected = review_correct_token(sid, item)
        body = review_answer(
            client, token, sid, as_str(item["id"]), review_correct_answer(sid, item)
        )
        assert body["correct"] is True
        assert body["alreadyAnswered"] is False
        assert body["correctToken"] == expected
        assert body["correctTokens"] == [expected]
        assert body["correctWord"] == sign_word(as_str(item["signId"]))

    answers = db_review_answers(sid)
    assert [a.item_id for a in answers] == ["R-01", "R-02"]
    assert all(a.correct for a in answers)
    assert all(a.answered_at == clock.now() for a in answers)  # D22


def test_respuesta_incorrecta_marca_la_correcta(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    item = db_review_items(sid)[0]
    body = review_answer(client, token, sid, as_str(item["id"]), review_wrong_answer(sid, item))
    assert body["correct"] is False
    assert body["alreadyAnswered"] is False
    assert body["correctToken"] == review_correct_token(sid, item)
    assert body["correctWord"] == sign_word(as_str(item["signId"]))


def test_el_primer_intento_manda(client: TestClient, user: tuple[str, str]) -> None:
    """Responder mal y luego bien devuelve la evaluación original (alreadyAnswered)."""
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    item = db_review_items(sid)[0]
    item_id = as_str(item["id"])

    first = review_answer(client, token, sid, item_id, review_wrong_answer(sid, item))
    second = review_answer(client, token, sid, item_id, review_correct_answer(sid, item))
    assert first["correct"] is False
    assert second["correct"] is False
    assert second["alreadyAnswered"] is True
    assert second["correctToken"] == first["correctToken"]
    answers = db_review_answers(sid)
    assert len(answers) == 1
    assert answers[0].correct is False


def test_token_inventado_es_incorrecto(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    body = review_answer(client, token, sid, "R-01", {"optionToken": "0123456789"})
    assert body["correct"] is False


def test_token_de_otra_sesion_no_sirve(client: TestClient, user: tuple[str, str]) -> None:
    """Los tokens dependen de la sesión (D20): el de otra sesión no acierta."""
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    item = db_review_items(sid)[0]
    foreign = review_correct_answer(str(uuid.uuid4()), item)
    assert review_answer(client, token, sid, as_str(item["id"]), foreign)["correct"] is False


def test_error_en_el_repaso_no_quita_vidas(client: TestClient, user: tuple[str, str]) -> None:
    """R5.13, §8.5: el repaso NO quita vidas."""
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    seed_due(user_id, 3)
    session = start_review(client, token)
    sid = review_id_of(session)
    for item in db_review_items(sid):
        review_answer(client, token, sid, as_str(item["id"]), review_wrong_answer(sid, item))

    stored = db_user(user_id)
    assert stored.hearts == 2
    assert stored.hearts_updated_at == T0
    assert hearts_now(client, token) == 2


def test_error_con_5_vidas_no_las_toca(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 1)
    session = start_review(client, token)
    sid = review_id_of(session)
    item = db_review_items(sid)[0]
    review_answer(client, token, sid, as_str(item["id"]), review_wrong_answer(sid, item))
    assert db_user(user_id).hearts == 5


def test_responder_en_sesion_de_otro_usuario_404(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    item = db_review_items(sid)[0]
    other_token, _ = register_user(client, OTHER_EMAIL)

    response = post_review_answer(
        client, other_token, sid, as_str(item["id"]), review_correct_answer(sid, item)
    )
    assert response.status_code == 404, response.text
    assert db_review_answers(sid) == []


def test_responder_en_sesion_inexistente_404(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    response = post_review_answer(
        client, token, str(uuid.uuid4()), "R-01", {"optionToken": "0123456789"}
    )
    assert response.status_code == 404, response.text


def test_ejercicio_inexistente_404(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    sid = review_id_of(start_review(client, token))
    response = post_review_answer(client, token, sid, "R-99", {"optionToken": "0123456789"})
    assert response.status_code == 404, response.text


def test_ejercicio_de_leccion_en_sesion_de_repaso_404(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    sid = review_id_of(start_review(client, token))
    exercise_id = db_exercises(L1)[1].id
    response = post_review_answer(client, token, sid, exercise_id, {"optionToken": "0123456789"})
    assert response.status_code == 404, response.text


def test_respuesta_con_forma_invalida_422(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    sid = review_id_of(start_review(client, token))
    response = post_review_answer(client, token, sid, "R-01", {"optionToken": 12, "extra": True})
    assert response.status_code == 422, response.text
    assert db_review_answers(sid) == []


def test_responder_en_sesion_completada_409(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    answer_review_all(client, token, session)
    complete_review(client, token, sid)

    item = db_review_items(sid)[0]
    response = post_review_answer(
        client, token, sid, as_str(item["id"]), review_correct_answer(sid, item)
    )
    assert_error(response, 409, "SESSION_COMPLETED")


def test_responder_despues_de_24_horas_410(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    item = db_review_items(sid)[0]

    token = move_to(client, clock, T0 + timedelta(hours=24, minutes=1))
    response = post_review_answer(
        client, token, sid, as_str(item["id"]), review_correct_answer(sid, item)
    )
    assert_error(response, 410, "SESSION_EXPIRED")
    assert db_review_answers(sid) == []


def test_responder_antes_de_24_horas_sigue_activa(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    item = db_review_items(sid)[0]

    token = move_to(client, clock, T0 + timedelta(hours=23, minutes=59))
    body = review_answer(client, token, sid, as_str(item["id"]), review_correct_answer(sid, item))
    assert body["correct"] is True


# ================================================================ completar


def test_completar_sin_responder_todo_409(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 3)
    session = start_review(client, token)
    sid = review_id_of(session)
    item = db_review_items(sid)[0]
    review_answer(client, token, sid, as_str(item["id"]), review_correct_answer(sid, item))

    assert_error(post_review_complete(client, token, sid), 409, "SESSION_INCOMPLETE")
    assert db_review_session(sid).completed_at is None
    assert db_activity(user_id) == []


def test_completar_sin_ninguna_respuesta_409(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    sid = review_id_of(start_review(client, token))
    assert_error(post_review_complete(client, token, sid), 409, "SESSION_INCOMPLETE")


def test_completar_repaso_perfecto(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    seed_due(user_id, 4)
    session = start_review(client, token)
    answer_review_all(client, token, session)
    clock.advance(minutes=2)
    result = complete_review(client, token, review_id_of(session))

    assert result["correct"] == 4
    assert result["total"] == 4
    assert result["score"] == 100
    assert result["heartsGained"] == 0  # ya tenía 5
    assert result["streak"] == {"current": 1, "extended": True}
    assert result["newAchievements"] == []
    stored = db_review_session(review_id_of(session))
    assert stored.completed_at == clock.now()  # D22
    assert stored.correct == 4
    assert stored.total == 4


def test_puntaje_del_repaso_es_division_entera(client: TestClient, user: tuple[str, str]) -> None:
    """score = correct * 100 // total: 2 de 3 → 66."""
    token, user_id = user
    seed_due(user_id, 3)
    session = start_review(client, token)
    answer_review_count(client, token, session, correct=2)
    result = complete_review(client, token, review_id_of(session))
    assert result["correct"] == 2
    assert result["total"] == 3
    assert result["score"] == 66


def test_complete_cuenta_el_primer_intento(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    sid = review_id_of(session)
    items = db_review_items(sid)
    review_answer(client, token, sid, as_str(items[0]["id"]), review_wrong_answer(sid, items[0]))
    review_answer(client, token, sid, as_str(items[0]["id"]), review_correct_answer(sid, items[0]))
    review_answer(client, token, sid, as_str(items[1]["id"]), review_correct_answer(sid, items[1]))
    result = complete_review(client, token, sid)
    assert result["correct"] == 1
    assert result["total"] == 2


def test_completar_reprograma_cada_sena_con_el_scheduler(
    client: TestClient, user: tuple[str, str]
) -> None:
    """§7.7, R6.4, R6.5: acierto → fuerza + 1 (tope 5) e INTERVALS[fuerza]; error → 0 y mañana."""
    token, user_id = user
    signs = lesson_signs_in_order()
    a, b, c, d, e = signs[:5]
    fillers = signs[5:8]
    entries = {a: (0, 0), b: (2, -1), c: (5, 0), d: (3, -3), e: (1, 0)}
    entries.update(dict.fromkeys(fillers, (3, 20)))
    seed_reviews(user_id, entries)

    session = start_review(client, token)
    answer_review_all(client, token, session, wrong_signs={d, e})
    complete_review(client, token, review_id_of(session))

    reviews = db_reviews(user_id)
    assert reviews[a] == (1, day_str(INTERVALS[1]))
    assert reviews[b] == (3, day_str(INTERVALS[3]))
    assert reviews[c] == (5, day_str(INTERVALS[5]))
    assert reviews[d] == (0, day_str(INTERVALS[0]))
    assert reviews[e] == (0, day_str(INTERVALS[0]))
    for filler in fillers:
        assert reviews[filler] == (3, day_str(20))  # no vencidas: intactas


def test_despues_de_completar_la_cola_de_hoy_queda_vacia_y_no_hay_segundo_repaso(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """PRUEBA 7.3: segunda sesión el mismo día → 409 NO_REVIEWS_DUE (aunque falle señas)."""
    token, user_id = user
    due = seed_due(user_id, 3)
    session = start_review(client, token)
    answer_review_all(client, token, session, wrong_signs={due[0]})
    complete_review(client, token, review_id_of(session))

    assert get_queue(client, token) == {"due": 0, "signs": []}
    assert_error(post_start(client, token), 409, "NO_REVIEWS_DUE")

    token = move_to(client, clock, local(1, 10))  # la fallada vuelve mañana
    assert get_queue(client, token) == {"due": 1, "signs": [{"word": sign_word(due[0])}]}


def test_repaso_no_da_xp_ni_nectar(client: TestClient, user: tuple[str, str]) -> None:
    """R6.6: el repaso no otorga XP; tampoco néctar (§8.5)."""
    token, user_id = user
    set_user_values(user_id, total_xp=120, nectar=33)
    seed_due(user_id, 3)
    session = start_review(client, token)
    answer_review_all(client, token, session)
    result = complete_review(client, token, review_id_of(session))

    assert "xpEarned" not in result
    assert "nectarEarned" not in result
    stored = db_user(user_id)
    assert stored.total_xp == 120
    assert stored.nectar == 33
    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].xp == 0


def test_repaso_registra_actividad_del_dia(client: TestClient, user: tuple[str, str]) -> None:
    """R5.5: el repaso cuenta como actividad (`daily_activity.reviews += 1`)."""
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    answer_review_all(client, token, session)
    complete_review(client, token, review_id_of(session))

    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].day == day_str(0)
    assert rows[0].reviews == 1
    assert rows[0].lessons == 0
    assert rows[0].xp == 0
    streak = db_streak(user_id)
    assert streak is not None
    assert streak.current == 1
    assert streak.last_active_day == day_str(0)


def test_leccion_un_dia_y_repaso_al_siguiente_extienden_la_racha(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """PRUEBA 7.3 (R5.5): lección el día 0 con un error → repaso el día 1 → racha 2."""
    token, user_id = user
    target = next(e for e in db_exercises(L1) if e.type.value == "VIDEO_TO_MEANING")
    first = do_lesson(client, token, wrong={target.id})
    assert first["streak"] == {"current": 1, "extended": True}

    token = move_to(client, clock, local(1, 10))
    session = start_review(client, token)
    answer_review_all(client, token, session)
    result = complete_review(client, token, review_id_of(session))

    assert result["streak"] == {"current": 2, "extended": True}
    assert [(r.day, r.lessons, r.reviews) for r in db_activity(user_id)] == [
        (day_str(0), 1, 0),
        (day_str(1), 0, 1),
    ]
    streak = db_streak(user_id)
    assert streak is not None
    assert streak.current == 2
    assert streak.longest == 2
    assert streak.last_active_day == day_str(1)


def test_repaso_despues_de_leccion_el_mismo_dia_no_extiende_otra_vez(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    do_lesson(client, token)
    seed_due(user_id, 2)  # señas de otras lecciones vencidas hoy
    session = start_review(client, token)
    answer_review_all(client, token, session)
    result = complete_review(client, token, review_id_of(session))

    assert result["streak"] == {"current": 1, "extended": False}
    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].lessons == 1
    assert rows[0].reviews == 1


def test_repaso_reprobado_tambien_cuenta_para_la_racha(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_streak(user_id, current=4, longest=4, last_active_day=day_str(-1))
    seed_due(user_id, 2)
    session = start_review(client, token)
    answer_review_count(client, token, session, correct=0)
    result = complete_review(client, token, review_id_of(session))
    assert result["score"] == 0
    assert result["streak"] == {"current": 5, "extended": True}


def test_racha_de_tres_con_un_repaso_otorga_streak_3(
    client: TestClient, user: tuple[str, str]
) -> None:
    """§7.9: STREAK_3 puede cumplirse al completar un repaso; su néctar sí se suma."""
    token, user_id = user
    set_streak(user_id, current=2, longest=2, last_active_day=day_str(-1))
    seed_due(user_id, 2)
    session = start_review(client, token)
    answer_review_all(client, token, session)
    result = complete_review(client, token, review_id_of(session))

    assert result["streak"] == {"current": 3, "extended": True}
    assert result["newAchievements"] == [STREAK_3]
    assert db_user_achievement_ids(user_id) == ["STREAK_3"]
    stored = db_user(user_id)
    assert stored.nectar == 15
    assert stored.total_xp == 0


def test_streak_3_ya_obtenido_no_se_repite_en_el_repaso(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_streak(user_id, current=2, longest=2, last_active_day=day_str(-1))
    seed_due(user_id, 2)
    first = start_review(client, token)
    answer_review_all(client, token, first)
    assert complete_review(client, token, review_id_of(first))["newAchievements"] == [STREAK_3]
    set_streak(user_id, current=3, longest=3, last_active_day=day_str(-1))
    signs = lesson_signs_in_order()
    seed_reviews(user_id, {signs[10]: (0, 0)})
    second = start_review(client, token)
    answer_review_all(client, token, second)
    assert complete_review(client, token, review_id_of(second))["newAchievements"] == []
    assert db_user(user_id).nectar == 15


# ---------------------------------------------------------------- vidas al completar


def test_repaso_con_80_por_ciento_da_una_vida(client: TestClient, user: tuple[str, str]) -> None:
    """R5.14: correct * 100 >= 80 * total → +1 vida (4 de 5 = 80 %)."""
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    seed_due(user_id, 5)
    session = start_review(client, token)
    answer_review_count(client, token, session, correct=4)
    result = complete_review(client, token, review_id_of(session))

    assert result["score"] == 80
    assert result["heartsGained"] == 1
    assert hearts_now(client, token) == 3
    assert db_review_session(review_id_of(session)).hearts_gained == 1


def test_repaso_perfecto_da_una_vida_si_le_faltan(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    set_user_values(user_id, hearts=0, hearts_updated_at=T0)
    seed_due(user_id, 3)
    session = start_review(client, token)
    answer_review_all(client, token, session)
    result = complete_review(client, token, review_id_of(session))
    assert result["heartsGained"] == 1
    assert hearts_now(client, token) == 1


def test_repaso_con_menos_de_80_por_ciento_no_da_vida(
    client: TestClient, user: tuple[str, str]
) -> None:
    """3 de 5 = 60 % → 0 vidas."""
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    seed_due(user_id, 5)
    session = start_review(client, token)
    answer_review_count(client, token, session, correct=3)
    result = complete_review(client, token, review_id_of(session))

    assert result["heartsGained"] == 0
    assert hearts_now(client, token) == 2


def test_repaso_justo_bajo_el_80_por_ciento_no_da_vida(
    client: TestClient, user: tuple[str, str]
) -> None:
    """11 de 14 = 78,6 % → 0 vidas (sin redondeos hacia arriba)."""
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    seed_due(user_id, 14)
    session = start_review(client, token)
    answer_review_count(client, token, session, correct=11)
    result = complete_review(client, token, review_id_of(session))
    assert result["score"] == 78
    assert result["heartsGained"] == 0
    assert hearts_now(client, token) == 2


def test_repaso_con_5_vidas_no_suma_vida(client: TestClient, user: tuple[str, str]) -> None:
    """Tope 5 (§7.10): heartsGained 0."""
    token, user_id = user
    seed_due(user_id, 3)
    session = start_review(client, token)
    answer_review_all(client, token, session)
    result = complete_review(client, token, review_id_of(session))
    assert result["heartsGained"] == 0
    assert db_user(user_id).hearts == 5
    assert hearts_now(client, token) == 5


def test_vida_ganada_respeta_las_recuperadas_por_tiempo(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """D24: con 4 vidas guardadas y 4 h transcurridas ya tiene 5 → heartsGained 0."""
    _, user_id = user
    set_user_values(user_id, hearts=4, hearts_updated_at=T0 - timedelta(hours=4))
    token = login(client)
    seed_due(user_id, 2)
    session = start_review(client, token)
    answer_review_all(client, token, session)
    result = complete_review(client, token, review_id_of(session))
    assert result["heartsGained"] == 0
    assert hearts_now(client, token) == 5


# ---------------------------------------------------------------- idempotencia y errores


def test_complete_repetido_devuelve_lo_mismo_sin_duplicar(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """Idempotente: ni doble actividad, ni doble vida, ni doble reprogramación."""
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    seed_due(user_id, 3)
    session = start_review(client, token)
    sid = review_id_of(session)
    answer_review_all(client, token, session)

    first = complete_review(client, token, sid)
    reviews_after_first = db_reviews(user_id)
    clock.advance(minutes=1)
    second = complete_review(client, token, sid)

    assert second == first
    assert first["heartsGained"] == 1
    assert hearts_now(client, token) == 3
    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].reviews == 1
    assert db_reviews(user_id) == reviews_after_first
    assert db_review_session(sid).completed_at == T0  # no se reescribe


def test_dos_complete_simultaneos_aplican_una_vez(
    client: TestClient, user: tuple[str, str]
) -> None:
    """SERIALIZABLE (§8.5, B5): dos solicitudes a la vez → mismo resultado, efectos una vez."""
    token, user_id = user
    set_user_values(user_id, hearts=2, hearts_updated_at=T0)
    seed_due(user_id, 3)
    session = start_review(client, token)
    sid = review_id_of(session)
    answer_review_all(client, token, session)

    def finish(_: int) -> tuple[int, JsonObject]:
        with TestClient(client.app) as other:
            response = post_review_complete(other, token, sid)
        return response.status_code, as_obj(response.json())

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(finish, [0, 1]))

    assert [code for code, _ in outcomes] == [200, 200]
    assert outcomes[0][1] == outcomes[1][1]
    assert db_user(user_id).hearts == 3
    rows = db_activity(user_id)
    assert len(rows) == 1
    assert rows[0].reviews == 1
    streak = db_streak(user_id)
    assert streak is not None
    assert streak.current == 1


def test_completar_sesion_de_otro_usuario_404(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    answer_review_all(client, token, session)
    other_token, other_id = register_user(client, OTHER_EMAIL)

    response = post_review_complete(client, other_token, review_id_of(session))
    assert response.status_code == 404, response.text
    assert db_review_session(review_id_of(session)).completed_at is None
    assert db_activity(other_id) == []


def test_completar_sesion_inexistente_404(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    response = post_review_complete(client, token, str(uuid.uuid4()))
    assert response.status_code == 404, response.text


def test_completar_despues_de_24_horas_410(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    seed_due(user_id, 2)
    session = start_review(client, token)
    answer_review_all(client, token, session)

    token = move_to(client, clock, T0 + timedelta(hours=25))
    assert_error(post_review_complete(client, token, review_id_of(session)), 410, "SESSION_EXPIRED")
    assert db_activity(user_id) == []
    assert db_review_session(review_id_of(session)).completed_at is None


def test_sesion_de_ayer_queda_cerrada_al_empezar_otra_y_no_paga_dos_veces(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """Revisión del Grupo 7 (R6.8): la sesión de ayer, respondida pero sin completar, no se
    puede completar después de empezar la de hoy; las señas se reprograman una sola vez."""
    token, user_id = user
    # 3 vidas desde las 00:00 del día 1: a las 00:05 aún no se recupera ninguna sola.
    set_user_values(user_id, hearts=3, hearts_updated_at=local(1, 0, 0))
    seed_due(user_id, 3)
    clock.set(local(0, 23, 55))
    token = login(client)
    yesterday = start_review(client, token)
    answer_review_all(client, token, yesterday)

    token = move_to(client, clock, local(1, 0, 5))
    today = start_review(client, token)
    answer_review_all(client, token, today)

    late = post_review_complete(client, token, review_id_of(yesterday))
    assert_error(late, 409, "SESSION_COMPLETED")
    result = complete_review(client, token, review_id_of(today))
    assert result["heartsGained"] == 1
    rows = db_activity(user_id)
    assert sum(row.reviews for row in rows) == 1
