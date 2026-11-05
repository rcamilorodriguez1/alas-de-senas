"""Tareas 5.1 y 5.2 — sesión de lección: `start`, `answers` y `complete` (R3.8, R4.4 a R4.10c,
R5.13 a R5.15; §7.2, §7.3, §7.6, §7.10, §8.2, §8.3; B1 a B3, B9, B16, B54, B61, B63, B77, B80, B81,
B88, B89; D20, D22, D-008).

Las pruebas responden «bien» calculando los tokens con el secreto del servidor y el payload real
de la BD (`helpers.correct_answer`): la API nunca revela la respuesta antes de contestar (B89).
Todos los tiempos los fija un `FakeClock` inyectado en `get_clock` (D22).
"""

from __future__ import annotations

import csv
import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limits
from app.domain.exercises.models import MeaningToVideoPayload, VideoToMeaningPayload
from app.infra.db import get_engine
from app.infra.models import (
    Exercise,
    Lesson,
    LessonSession,
    Module,
    Node,
    SessionAnswer,
    Sign,
    User,
)
from tests.api.helpers import (
    PASSWORD,
    auth,
    complete_lesson,
    correct_answer,
    correct_tokens,
    exercise_payload,
    register_user,
    wrong_answer,
)
from tests.fakes import FakeClock
from tests.unit.content.real_content import CONTENT_DIR

pytestmark = pytest.mark.usefixtures("seeded_content")

JsonObject = dict[str, object]

# PyJWT rechaza tokens con `iat` posterior a la hora REAL (no la del `Clock`): el reloj simulado
# empieza 3 días antes para que los tokens emitidos tras `advance()` (hasta 24 h) sigan válidos.
T0 = (datetime.now(UTC) - timedelta(days=3)).replace(minute=0, second=0, microsecond=0)
EMAIL = "ana@ejemplo.com"

START_KEYS = {"sessionId", "lesson", "exercises", "hearts"}
LESSON_KEYS = {
    "id",
    "order",
    "type",
    "title",
    "nodeId",
    "nodeTitle",
    "nodeOrder",
    "moduleOrder",
    "estimatedXp",
}
EXERCISE_KEYS = {"id", "order", "activity", "type", "scored", "group", "content"}
HEARTS_KEYS = {"enabled", "current", "max", "nextHeartAt"}
ANSWER_KEYS = {
    "correct",
    "correctToken",
    "correctTokens",
    "correctWord",
    "alreadyAnswered",
    "hearts",
}
COMPLETE_KEYS = {
    "score",
    "correct",
    "total",
    "passed",
    "xpEarned",
    "nectarEarned",
    "streak",
    "newAchievements",
    "unlocked",
    "mascotMood",
    "mascotMessage",
}
FORBIDDEN_KEYS = {"correctId", "signId", "optionIds", "signIds", "letterIds", "correctToken"}
ACTIVITIES = {"OBSERVE", "SELECT", "PRODUCE", "USE"}
UNGROUPED_TYPES = {"MEMORY_MATCH", "CONVERSATION", "SPELLING"}
VIDEO_SRC = re.compile(r"^/media/v/[0-9a-f]{16}\.mp4$")
POSTER_SRC = re.compile(r"^/media/p/[0-9a-f]{16}\.jpg$")

LESSON_LOCKED = {
    "statusCode": 403,
    "code": "LESSON_LOCKED",
    "message": "Esta lección aún está bloqueada",
}
SESSION_INCOMPLETE = {
    "statusCode": 409,
    "code": "SESSION_INCOMPLETE",
    "message": "Responde todos los ejercicios para terminar la lección",
}

L1 = "M1-N1-L1"  # Aprende: hola, buenos-dias, buenas-tardes (12 ejercicios, 6 con puntaje)
L2 = "M1-N1-L2"  # Reconoce: buenas-noches, como-estas, adios + conversación (10, 7 con puntaje)
L3 = "M1-N1-L3"  # Practica (incluye PRODUCE)
L4 = "M1-N1-L4"  # Reto final


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


# ---------------------------------------------------------------- ayudas


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


def json_of(response: Response) -> JsonObject:
    return as_obj(response.json())


def parse_iso(value: object) -> datetime:
    text = as_str(value).replace("Z", "+00:00")
    moment = datetime.fromisoformat(text)
    assert moment.tzinfo is not None, "nextHeartAt debe llevar zona horaria"
    return moment


def login(client: TestClient, email: str = EMAIL) -> str:
    """Nuevo access token (el anterior vence a los 15 min del `FakeClock`)."""
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return as_str(json_of(response)["accessToken"])


def post_start(client: TestClient, token: str, lesson_id: str) -> Response:
    response: Response = client.post(f"/api/lessons/{lesson_id}/sessions", headers=auth(token))
    return response


def start(client: TestClient, token: str, lesson_id: str) -> JsonObject:
    response = post_start(client, token, lesson_id)
    assert response.status_code == 201, response.text
    return json_of(response)


def session_id_of(session: JsonObject) -> str:
    return as_str(session["sessionId"])


def exercises_of(session: JsonObject) -> list[JsonObject]:
    return as_list(session["exercises"])


def exercise_ids(session: JsonObject) -> list[str]:
    return [as_str(e["id"]) for e in exercises_of(session)]


def post_answer(
    client: TestClient, token: str, session_id: str, exercise_id: str, answer: object
) -> Response:
    response: Response = client.post(
        f"/api/lesson-sessions/{session_id}/answers",
        headers=auth(token),
        json={"exerciseId": exercise_id, "answer": answer},
    )
    return response


def answer_ok(
    client: TestClient, token: str, session_id: str, exercise_id: str, answer: object
) -> JsonObject:
    response = post_answer(client, token, session_id, exercise_id, answer)
    assert response.status_code == 200, response.text
    return json_of(response)


def answer_right(client: TestClient, token: str, session_id: str, exercise_id: str) -> JsonObject:
    return answer_ok(
        client, token, session_id, exercise_id, correct_answer(session_id, exercise_id)
    )


def answer_wrong(client: TestClient, token: str, session_id: str, exercise_id: str) -> JsonObject:
    wrong = wrong_answer(session_id, exercise_id)
    body = correct_answer(session_id, exercise_id) if wrong is None else wrong
    return answer_ok(client, token, session_id, exercise_id, body)


def answer_all(
    client: TestClient, token: str, session: JsonObject, *, wrong: set[str] | None = None
) -> None:
    """Responde todos los ejercicios: bien, salvo los de `wrong` (los OBSERVE siempre bien)."""
    sid = session_id_of(session)
    for exercise_id in exercise_ids(session):
        if wrong is not None and exercise_id in wrong:
            answer_wrong(client, token, sid, exercise_id)
        else:
            answer_right(client, token, sid, exercise_id)


def post_complete(client: TestClient, token: str, session_id: str) -> Response:
    response: Response = client.post(
        f"/api/lesson-sessions/{session_id}/complete", headers=auth(token)
    )
    return response


def complete(client: TestClient, token: str, session_id: str) -> JsonObject:
    response = post_complete(client, token, session_id)
    assert response.status_code == 200, response.text
    return json_of(response)


def assert_error(response: Response, status: int, code: str) -> JsonObject:
    assert response.status_code == status, response.text
    body = json_of(response)
    assert body["statusCode"] == status
    assert body["code"] == code
    assert isinstance(body["message"], str)
    assert body["message"]
    return body


def scored_ids(session: JsonObject) -> list[str]:
    return [as_str(e["id"]) for e in exercises_of(session) if e["scored"] is True]


def ids_of_type(session: JsonObject, exercise_type: str) -> list[str]:
    return [as_str(e["id"]) for e in exercises_of(session) if e["type"] == exercise_type]


def db_user(user_id: str) -> User:
    with Session(get_engine()) as db:
        found = db.get(User, uuid.UUID(user_id))
        assert found is not None
        db.expunge(found)
        return found


def db_session(session_id: str) -> LessonSession:
    with Session(get_engine()) as db:
        found = db.get(LessonSession, uuid.UUID(session_id))
        assert found is not None
        db.expunge(found)
        return found


def db_answer(session_id: str, exercise_id: str) -> SessionAnswer:
    with Session(get_engine()) as db:
        found = db.get(SessionAnswer, (uuid.UUID(session_id), exercise_id))
        assert found is not None
        db.expunge(found)
        return found


def set_hearts(user_id: str, hearts: int, updated_at: datetime | None) -> None:
    with Session(get_engine()) as db:
        db.execute(
            update(User)
            .where(User.id == uuid.UUID(user_id))
            .values(hearts=hearts, hearts_updated_at=updated_at)
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


def sign_word(sign_id: str) -> str:
    with Session(get_engine()) as db:
        return db.execute(select(Sign.word).where(Sign.id == sign_id)).scalar_one()


def content_slugs() -> set[str]:
    with (CONTENT_DIR / "signs.csv").open(encoding="utf-8", newline="") as handle:
        return {row["slug"] for row in csv.DictReader(handle)}


def walk(value: object, key: str | None = None) -> Iterator[tuple[str | None, object]]:
    """Recorre todo el JSON y produce (clave, valor) de cada nodo."""
    yield key, value
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from walk(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from walk(child, key)


def learning_path_status(client: TestClient, token: str, lesson_id: str) -> object:
    response = client.get("/api/learning-path", headers=auth(token))
    assert response.status_code == 200, response.text
    for mod in as_list(json_of(response)["modules"]):
        for nd in as_list(mod["nodes"]):
            for item in as_list(nd["lessons"]):
                if item["id"] == lesson_id:
                    return item["status"]
    raise AssertionError(f"Falta la lección {lesson_id}")


def learning_path_estimated_xp(client: TestClient, token: str, lesson_id: str) -> object:
    response = client.get("/api/learning-path", headers=auth(token))
    assert response.status_code == 200, response.text
    for mod in as_list(json_of(response)["modules"]):
        for nd in as_list(mod["nodes"]):
            for item in as_list(nd["lessons"]):
                if item["id"] == lesson_id:
                    return item["estimatedXp"]
    raise AssertionError(f"Falta la lección {lesson_id}")


# ================================================================ start


def test_iniciar_l1_devuelve_201_con_sesion_leccion_ejercicios_y_vidas(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, _ = user
    body = start(client, token, L1)

    assert set(body) == START_KEYS
    uuid.UUID(session_id_of(body))

    lesson = as_obj(body["lesson"])
    assert set(lesson) == LESSON_KEYS
    assert lesson["id"] == L1
    assert lesson["order"] == 1
    assert lesson["type"] == "LEARN"
    assert isinstance(lesson["title"], str)
    assert lesson["title"]
    assert lesson["nodeId"] == "M1-N1"
    assert isinstance(lesson["nodeTitle"], str)
    assert lesson["nodeTitle"]
    assert lesson["nodeOrder"] == 1
    assert lesson["moduleOrder"] == 1
    assert lesson["estimatedXp"] == learning_path_estimated_xp(client, token, L1)

    assert as_obj(body["hearts"]) == {"enabled": True, "current": 5, "max": 5, "nextHeartAt": None}


def test_ejercicios_en_orden_con_actividad_tipo_y_puntaje_de_la_bd(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, _ = user
    exercises = exercises_of(start(client, token, L1))
    rows = db_exercises(L1)

    assert len(exercises) == len(rows) == 12
    for public, row in zip(exercises, rows, strict=True):
        assert set(public) == EXERCISE_KEYS
        assert public["id"] == row.id
        assert public["order"] == row.order
        assert public["activity"] == row.activity.value
        assert public["activity"] in ACTIVITIES
        assert public["type"] == row.type.value
        assert public["scored"] is row.scored
        assert as_obj(public["content"])["type"] == row.type.value
    orders = [int(str(e["order"])) for e in exercises]
    assert orders == sorted(orders)
    assert sum(1 for e in exercises if e["scored"] is True) == 6  # R4.10c: ≥ 4 con puntaje


def test_contenido_publico_en_camel_case(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    exercises = exercises_of(start(client, token, L1))
    observe = as_obj(exercises[0]["content"])
    assert observe["type"] == "OBSERVE"
    assert {"video", "word", "howTo", "usageExample"} <= set(observe)
    assert observe["word"] == "Hola"
    video = as_obj(observe["video"])
    assert VIDEO_SRC.match(as_str(video["src"]))
    assert POSTER_SRC.match(as_str(video["poster"]))
    produce = next(as_obj(e["content"]) for e in exercises if e["type"] == "PRODUCE")
    assert produce["type"] == "PRODUCE"
    assert "cameraLabel" in produce


def test_grupo_por_sena_en_l1(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    exercises = exercises_of(start(client, token, L1))
    # D-021: se observan las 3 señas (grupos 0, 1, 2) y después se recuerdan mezcladas: las
    # preguntas y la producción no pertenecen a una sola seña, así que no llevan grupo.
    assert [e["group"] for e in exercises] == [0, 1, 2] + [None] * 9
    assert [e["activity"] for e in exercises[:3]] == ["OBSERVE"] * 3


def test_grupo_null_en_la_conversacion_final_de_l2(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    exercises = exercises_of(start(client, token, L2))
    assert [e["group"] for e in exercises] == [0, 1, 2] + [None] * 7  # D-021
    assert exercises[-1]["type"] == "CONVERSATION"
    assert exercises[-1]["activity"] == "USE"


def test_grupo_null_en_memory_match_y_spelling(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    approve_lessons_before(user_id, "M1-N3-L3")
    exercises = exercises_of(start(client, token, "M1-N3-L3"))
    rows = db_exercises("M1-N3-L3")

    # D-021: solo las señas que se observan llevan grupo (en orden); el resto, ninguno.
    observed: list[str] = []
    for public, row in zip(exercises, rows, strict=True):
        if public["type"] == "OBSERVE":
            assert row.sign_id is not None
            observed.append(row.sign_id)
            assert public["group"] == len(observed) - 1, public["id"]
        else:
            assert public["group"] is None, public["id"]
    assert observed
    assert {"MEMORY_MATCH", "SPELLING"} <= {e["type"] for e in exercises}


def test_grupo_null_en_todos_los_ejercicios_del_reto(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    approve_lessons_before(user_id, L4)
    exercises = exercises_of(start(client, token, L4))
    assert exercises
    assert all(e["group"] is None for e in exercises)


@pytest.mark.parametrize(
    "lesson_id",
    [L1, L2, L3, L4, "M1-N3-L2", "M1-N3-L3", "M1-N3-L4"],
)
def test_respuestas_ocultas_y_opciones_sin_slugs(
    client: TestClient, user: tuple[str, str], lesson_id: str
) -> None:
    """PRUEBA OBLIGATORIA (B1, B54, R4.4, D20): nada en el JSON permite deducir la respuesta."""
    token, user_id = user
    approve_lessons_before(user_id, lesson_id)
    body = start(client, token, lesson_id)
    slugs = content_slugs()

    for key, value in walk(body):
        assert key not in FORBIDDEN_KEYS, f"Clave prohibida «{key}» en la respuesta"
        # Ningún valor (opciones, tarjetas, palabras, rutas) es un slug. Únicas excepciones:
        # `cameraLabel` y `gestureLabel` de PRODUCE, que los modelos de cámara necesitan
        # (§7.6, D-026): PRODUCE ya muestra la palabra y no tiene opciones que adivinar.
        if isinstance(value, str) and key not in {"cameraLabel", "gestureLabel"}:
            assert value not in slugs, f"Slug «{value}» expuesto en «{key}»"

    for _, value in walk(body):
        if not isinstance(value, dict):
            continue
        for container in ("options", "videoCards", "wordCards"):
            if container not in value:
                continue
            for option in as_list(value[container]):
                assert set(option) <= {"token", "word", "video"}, option
                token_value = as_str(option["token"])
                assert token_value not in slugs
                assert re.fullmatch(r"[0-9a-f]{10}", token_value), token_value
        if "src" in value:
            src = as_str(value["src"])
            # Ruta por contenido (D19): solo hexadecimal, nunca la palabra ni el slug.
            assert VIDEO_SRC.match(src), src
            assert not any(slug in src for slug in slugs if re.search(r"[^0-9a-f]", slug)), src
            assert POSTER_SRC.match(as_str(value["poster"]))


def test_l2_bloqueada_403_lesson_locked(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    response = post_start(client, token, L2)
    assert response.status_code == 403
    assert response.json() == LESSON_LOCKED


def test_leccion_inexistente_404(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    assert_error(post_start(client, token, "M9-N9-L9"), 404, "LESSON_NOT_FOUND")


@pytest.fixture
def unpublished_m1() -> Iterator[None]:
    """Despublica M1 durante la prueba y lo restaura (el contenido no se trunca)."""
    with Session(get_engine()) as db:
        db.execute(update(Module).where(Module.id == "M1").values(published=False))
        db.commit()
    try:
        yield
    finally:
        with Session(get_engine()) as db:
            db.execute(update(Module).where(Module.id == "M1").values(published=True))
            db.commit()


@pytest.mark.usefixtures("unpublished_m1")
def test_leccion_de_modulo_no_publicado_404(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    assert_error(post_start(client, token, L1), 404, "LESSON_NOT_FOUND")


def test_sin_autenticacion_401(client: TestClient) -> None:
    assert client.post(f"/api/lessons/{L1}/sessions").status_code == 401


def test_sin_vidas_l2_responde_403_no_hearts_con_next_heart_at(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    set_hearts(user_id, 0, T0)

    body = assert_error(post_start(client, token, L2), 403, "NO_HEARTS")
    assert parse_iso(body["nextHeartAt"]) == T0 + timedelta(hours=4)


def test_sin_vidas_aprende_siempre_se_puede_empezar(
    client: TestClient, user: tuple[str, str]
) -> None:
    """B81: L1 nunca pide vidas, para no dejar a nadie atascado."""
    token, user_id = user
    set_hearts(user_id, 0, T0)

    body = start(client, token, L1)
    hearts = as_obj(body["hearts"])
    assert hearts["current"] == 0
    assert parse_iso(hearts["nextHeartAt"]) == T0 + timedelta(hours=4)


def test_vidas_recargadas_por_tiempo_permiten_empezar_l2(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    set_hearts(user_id, 0, T0)
    clock.advance(hours=4)
    token = login(client)

    hearts = as_obj(start(client, token, L2)["hearts"])
    assert hearts["current"] == 1


def test_started_at_lo_fija_el_clock(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    sid = session_id_of(start(client, token, L1))
    assert db_session(sid).started_at == T0


# ================================================================ answers


def test_respuesta_correcta_video_a_significado(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    exercise_id = ids_of_type(session, "VIDEO_TO_MEANING")[0]
    payload = exercise_payload(exercise_id)
    assert isinstance(payload, VideoToMeaningPayload)

    body = answer_right(client, token, sid, exercise_id)
    assert set(body) == ANSWER_KEYS
    assert body["correct"] is True
    assert body["alreadyAnswered"] is False
    expected = correct_tokens(sid, exercise_id)
    assert body["correctToken"] == expected[0]
    assert body["correctTokens"] == expected
    assert body["correctWord"] == sign_word(payload.correct_id)
    assert as_obj(body["hearts"]) == {"enabled": True, "current": 5, "max": 5, "nextHeartAt": None}


def test_respuesta_incorrecta_marca_la_opcion_correcta(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    exercise_id = ids_of_type(session, "MEANING_TO_VIDEO")[0]
    payload = exercise_payload(exercise_id)
    assert isinstance(payload, MeaningToVideoPayload)

    body = answer_wrong(client, token, sid, exercise_id)
    assert body["correct"] is False
    assert body["correctToken"] == correct_tokens(sid, exercise_id)[0]
    assert body["correctWord"] == sign_word(payload.correct_id)


def test_observe_es_correcta_sin_token(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    session = start(client, token, L1)
    exercise_id = ids_of_type(session, "OBSERVE")[0]
    body = answer_ok(client, token, session_id_of(session), exercise_id, {"watched": True})
    assert body["correct"] is True
    assert body["correctToken"] is None
    assert body["correctTokens"] == []
    assert body["correctWord"] is None


def test_conversacion_devuelve_un_token_por_turno(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    session = start(client, token, L2)
    sid = session_id_of(session)
    exercise_id = ids_of_type(session, "CONVERSATION")[0]

    body = answer_right(client, token, sid, exercise_id)
    expected = correct_tokens(sid, exercise_id)
    assert len(expected) == 2
    assert body["correct"] is True
    assert body["correctTokens"] == expected
    assert body["correctToken"] == expected[0]


def test_conversacion_con_un_turno_mal_es_incorrecta(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    session = start(client, token, L2)
    sid = session_id_of(session)
    exercise_id = ids_of_type(session, "CONVERSATION")[0]
    right = correct_answer(sid, exercise_id)
    wrong = wrong_answer(sid, exercise_id)
    assert wrong is not None
    right_choices = right["choices"]
    wrong_choices = wrong["choices"]
    assert isinstance(right_choices, list)
    assert isinstance(wrong_choices, list)

    body = answer_ok(
        client, token, sid, exercise_id, {"choices": [right_choices[0], wrong_choices[1]]}
    )
    assert body["correct"] is False


def test_segundo_intento_conserva_la_evaluacion_del_primero(
    client: TestClient, user: tuple[str, str]
) -> None:
    """B3, R4.6: mal y luego bien → sigue contando como mal."""
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    exercise_id = ids_of_type(session, "VIDEO_TO_MEANING")[0]
    wrong = wrong_answer(sid, exercise_id)
    assert wrong is not None

    first = answer_ok(client, token, sid, exercise_id, wrong)
    second = answer_right(client, token, sid, exercise_id)

    assert first["correct"] is False
    assert first["alreadyAnswered"] is False
    assert second["alreadyAnswered"] is True
    assert second["correct"] is False
    assert second["correctToken"] == first["correctToken"]
    stored = db_answer(sid, exercise_id)
    assert stored.correct is False
    assert stored.answer == wrong


def test_segundo_intento_bien_despues_de_bien_sigue_bien(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    exercise_id = ids_of_type(session, "VIDEO_TO_MEANING")[0]
    answer_right(client, token, sid, exercise_id)
    second = answer_wrong(client, token, sid, exercise_id)
    assert second["alreadyAnswered"] is True
    assert second["correct"] is True


def test_error_en_l2_quita_una_vida_y_programa_la_recarga(
    client: TestClient, user: tuple[str, str]
) -> None:
    """R5.13, §7.10: 5 → 4 y `nextHeartAt` = ahora + 4 h."""
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    session = start(client, token, L2)
    sid = session_id_of(session)

    body = answer_wrong(client, token, sid, scored_ids(session)[0])
    hearts = as_obj(body["hearts"])
    assert hearts["enabled"] is True
    assert hearts["current"] == 4
    assert hearts["max"] == 5
    assert parse_iso(hearts["nextHeartAt"]) == T0 + timedelta(hours=4)
    assert db_user(user_id).hearts == 4
    assert db_session(sid).hearts_lost == 1


def test_acierto_en_l2_no_quita_vidas(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    session = start(client, token, L2)
    body = answer_right(client, token, session_id_of(session), scored_ids(session)[0])
    assert as_obj(body["hearts"])["current"] == 5
    assert db_user(user_id).hearts == 5


def test_reintento_de_la_respuesta_no_descuenta_otra_vida(
    client: TestClient, user: tuple[str, str]
) -> None:
    """B80: repetir la misma respuesta incorrecta (reintento de red) descuenta una sola vida."""
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    session = start(client, token, L2)
    sid = session_id_of(session)
    exercise_id = scored_ids(session)[0]

    first = answer_wrong(client, token, sid, exercise_id)
    second = answer_wrong(client, token, sid, exercise_id)

    assert as_obj(first["hearts"])["current"] == 4
    assert second["alreadyAnswered"] is True
    assert second["correct"] is False
    assert as_obj(second["hearts"])["current"] == 4
    assert db_user(user_id).hearts == 4
    assert db_session(sid).hearts_lost == 1


def test_error_en_l1_no_quita_vidas(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    for exercise_id in scored_ids(session):
        body = answer_wrong(client, token, sid, exercise_id)
        assert body["correct"] is False
        assert as_obj(body["hearts"]) == {
            "enabled": True,
            "current": 5,
            "max": 5,
            "nextHeartAt": None,
        }
    assert db_user(user_id).hearts == 5
    assert db_session(sid).hearts_lost == 0


def test_produce_con_ok_false_no_quita_vidas(client: TestClient, user: tuple[str, str]) -> None:
    """R4.7: PRODUCE no tiene puntaje; «Necesito repasar» no cuesta vidas ni en L3."""
    token, user_id = user
    approve_lessons_before(user_id, L3)
    session = start(client, token, L3)
    sid = session_id_of(session)
    produce_id = ids_of_type(session, "PRODUCE")[0]
    produce = next(e for e in exercises_of(session) if e["id"] == produce_id)
    assert produce["scored"] is False

    body = answer_ok(client, token, sid, produce_id, {"method": "self", "ok": False})
    assert body["correct"] is False
    assert as_obj(body["hearts"])["current"] == 5
    assert db_user(user_id).hearts == 5
    assert db_session(sid).hearts_lost == 0


def test_vidas_en_cero_a_mitad_de_leccion_se_puede_terminar(
    client: TestClient, user: tuple[str, str]
) -> None:
    """B88: `answer` y `complete` nunca revisan vidas; solo `start`."""
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    session = start(client, token, L2)
    sid = session_id_of(session)
    set_hearts(user_id, 1, T0)
    scored = scored_ids(session)

    first = answer_wrong(client, token, sid, scored[0])
    assert as_obj(first["hearts"])["current"] == 0
    second = answer_wrong(client, token, sid, scored[1])  # con 0 vidas no baja de 0
    assert as_obj(second["hearts"])["current"] == 0
    for exercise_id in exercise_ids(session):
        if exercise_id not in scored[:2]:
            answer_right(client, token, sid, exercise_id)

    result = complete(client, token, sid)
    assert result["total"] == 7
    assert result["correct"] == 5
    assert db_user(user_id).hearts == 0


def test_answered_at_lo_fija_el_clock(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    exercise_id = exercise_ids(session)[0]
    clock.advance(minutes=1)
    answer_right(client, token, sid, exercise_id)
    assert db_answer(sid, exercise_id).answered_at == T0 + timedelta(minutes=1)


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda ok: {"optionToken": 5}, id="token-numerico"),
        pytest.param(lambda ok: {**ok, "extra": 1}, id="campo-extra"),
        pytest.param(lambda ok: {"watched": True}, id="forma-de-otro-tipo"),
        pytest.param(lambda ok: {}, id="vacia"),
        pytest.param(lambda ok: "texto", id="no-es-objeto"),
    ],
)
def test_respuesta_con_forma_invalida_422_y_no_se_guarda(
    client: TestClient,
    user: tuple[str, str],
    build: object,
) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    exercise_id = ids_of_type(session, "VIDEO_TO_MEANING")[0]
    right = correct_answer(sid, exercise_id)
    assert callable(build)
    invalid: object = build(right)

    response = post_answer(client, token, sid, exercise_id, invalid)
    assert_error(response, 422, "VALIDATION_ERROR")

    after = answer_ok(client, token, sid, exercise_id, right)
    assert after["alreadyAnswered"] is False
    assert after["correct"] is True


def test_cuerpo_con_campo_extra_422(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    exercise_id = exercise_ids(session)[0]
    response = client.post(
        f"/api/lesson-sessions/{sid}/answers",
        headers=auth(token),
        json={"exerciseId": exercise_id, "answer": {"watched": True}, "correct": True},
    )
    assert_error(response, 422, "VALIDATION_ERROR")


def test_ejercicio_que_no_es_de_la_leccion_404(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    sid = session_id_of(start(client, token, L1))
    response = post_answer(client, token, sid, "M1-N1-L2-01", {"watched": True})
    assert_error(response, 404, "EXERCISE_NOT_FOUND")
    response = post_answer(client, token, sid, "NO-EXISTE-99", {"watched": True})
    assert_error(response, 404, "EXERCISE_NOT_FOUND")


def test_sesion_de_otro_usuario_404(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    other_token, _ = register_user(client, "beto@ejemplo.com")

    response = post_answer(client, other_token, sid, exercise_ids(session)[0], {"watched": True})
    assert_error(response, 404, "SESSION_NOT_FOUND")
    answer_all(client, token, session)
    assert_error(post_complete(client, other_token, sid), 404, "SESSION_NOT_FOUND")
    # El dueño sigue pudiendo cerrarla: el intento ajeno no la tocó.
    assert complete(client, token, sid)["passed"] is True


def test_sesion_inexistente_404(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    missing = str(uuid.uuid4())
    response = post_answer(client, token, missing, "M1-N1-L1-01", {"watched": True})
    assert_error(response, 404, "SESSION_NOT_FOUND")
    assert_error(post_complete(client, token, missing), 404, "SESSION_NOT_FOUND")


def test_responder_en_sesion_completada_409(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    answer_all(client, token, session)
    complete(client, token, sid)

    response = post_answer(client, token, sid, exercise_ids(session)[0], {"watched": True})
    assert_error(response, 409, "SESSION_COMPLETED")


def test_sesion_de_mas_de_24_horas_expira_410(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    ids = exercise_ids(session)
    for exercise_id in ids[1:]:
        answer_right(client, token, sid, exercise_id)

    clock.advance(hours=24, seconds=1)
    token = login(client)

    response = post_answer(client, token, sid, ids[0], {"watched": True})
    assert_error(response, 410, "SESSION_EXPIRED")
    assert_error(post_complete(client, token, sid), 410, "SESSION_EXPIRED")
    # No se borra (§8.3 regla 6).
    assert db_session(sid).completed_at is None


def test_sesion_de_menos_de_24_horas_sigue_activa(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    clock.advance(hours=23, minutes=59)
    token = login(client)
    answer_all(client, token, session)
    assert complete(client, token, sid)["passed"] is True


@pytest.fixture
def reloaded_exercise() -> Iterator[str]:
    """Ejercicio de L1 cuyo payload cambia («contenido recargado»); se restaura al final."""
    exercise_id = "M1-N1-L1-04"  # primera pregunta «¿qué significa?» (D-021)
    with Session(get_engine()) as db:
        original = db.execute(
            select(Exercise.payload).where(Exercise.id == exercise_id)
        ).scalar_one()
    try:
        yield exercise_id
    finally:
        with Session(get_engine()) as db:
            db.execute(update(Exercise).where(Exercise.id == exercise_id).values(payload=original))
            db.commit()


def test_contenido_recargado_expira_la_sesion_410(
    client: TestClient, user: tuple[str, str], reloaded_exercise: str
) -> None:
    """§8.3 regla 8, R4.10b: si los ejercicios cambiaron, la lección se empieza de nuevo."""
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    ids = exercise_ids(session)
    answer_right(client, token, sid, ids[0])

    payload = exercise_payload(reloaded_exercise)
    assert isinstance(payload, VideoToMeaningPayload)
    new_correct = next(o for o in payload.option_ids if o != payload.correct_id)
    changed = payload.model_copy(update={"correct_id": new_correct})
    with Session(get_engine()) as db:
        db.execute(
            update(Exercise)
            .where(Exercise.id == reloaded_exercise)
            .values(payload=changed.model_dump(mode="json", by_alias=True))
        )
        db.commit()

    response = post_answer(client, token, sid, ids[1], {"watched": True})
    assert_error(response, 410, "SESSION_EXPIRED")
    assert_error(post_complete(client, token, sid), 410, "SESSION_EXPIRED")


# ================================================================ complete


def test_completar_sin_responder_todo_409(client: TestClient, user: tuple[str, str]) -> None:
    """B63, R4.10a: no se puede «completar» una sesión vacía ni a medias."""
    token, user_id = user
    session = start(client, token, L1)
    sid = session_id_of(session)

    empty = post_complete(client, token, sid)
    assert empty.status_code == 409
    assert empty.json() == SESSION_INCOMPLETE

    ids = exercise_ids(session)
    for exercise_id in ids[:-1]:
        answer_right(client, token, sid, exercise_id)
    partial = post_complete(client, token, sid)
    assert partial.status_code == 409
    assert partial.json() == SESSION_INCOMPLETE

    assert db_session(sid).completed_at is None
    assert db_user(user_id).total_xp == 0


def test_completar_l1_perfecta_da_recompensas_y_desbloquea_l2(
    client: TestClient, user: tuple[str, str]
) -> None:
    """B61: `complete` en sesión SERIALIZABLE propia con un usuario autenticado."""
    token, user_id = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    answer_all(client, token, session)

    result = complete(client, token, sid)
    assert set(result) == COMPLETE_KEYS
    assert result["score"] == 100
    assert result["correct"] == 6
    assert result["total"] == 6
    assert result["passed"] is True
    assert result["xpEarned"] == 20  # §7.3: 10 + 5 + 5
    assert result["nectarEarned"] == 5
    streak = as_obj(result["streak"])
    assert set(streak) == {"current", "extended"}
    assert isinstance(streak["current"], int)
    assert isinstance(streak["extended"], bool)
    assert isinstance(result["newAchievements"], list)
    assert {"type": "LESSON", "id": L2} in as_list(result["unlocked"])
    assert isinstance(result["mascotMood"], str)
    assert isinstance(result["mascotMessage"], str)
    assert result["mascotMessage"]

    assert learning_path_status(client, token, L2) == "AVAILABLE"
    stored = db_user(user_id)
    assert stored.total_xp == 20
    # 5 de la lección + 10 del logro FIRST_LESSON (§7.9, Grupo 6).
    assert stored.nectar == 5 + 10
    closed = db_session(sid)
    assert closed.score == 100
    assert closed.passed is True
    assert closed.xp_earned == 20


def test_doble_complete_devuelve_lo_mismo_sin_duplicar_xp(
    client: TestClient, user: tuple[str, str]
) -> None:
    """B2, R4.10: doble clic o StrictMode → mismo resultado, recompensas una sola vez."""
    token, user_id = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    answer_all(client, token, session)

    first = complete(client, token, sid)
    second = complete(client, token, sid)

    assert second == first
    stored = db_user(user_id)
    assert stored.total_xp == 20
    assert stored.nectar == 5 + 10  # lección + FIRST_LESSON, una sola vez


def test_repetir_leccion_aprobada_da_la_mitad_de_xp(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    first = start(client, token, L1)
    answer_all(client, token, first)
    assert complete(client, token, session_id_of(first))["xpEarned"] == 20

    again = start(client, token, L1)
    assert session_id_of(again) != session_id_of(first)
    answer_all(client, token, again)
    result = complete(client, token, session_id_of(again))

    assert result["passed"] is True
    assert result["xpEarned"] == 10  # ceil(20 / 2)
    assert db_user(user_id).total_xp == 30


def test_l2_todo_mal_no_aprueba_ni_desbloquea(client: TestClient, user: tuple[str, str]) -> None:
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    session = start(client, token, L2)
    sid = session_id_of(session)
    answer_all(client, token, session, wrong=set(exercise_ids(session)))

    result = complete(client, token, sid)
    assert result["correct"] == 0
    assert result["total"] == 7  # solo los ejercicios con puntaje
    assert result["score"] == 0
    assert result["passed"] is False
    assert result["xpEarned"] == 0
    assert result["nectarEarned"] == 0
    assert result["unlocked"] == []
    assert learning_path_status(client, token, L3) == "LOCKED"
    assert db_user(user_id).total_xp == 0


def test_puntaje_redondeado_hacia_arriba_y_aprobacion(
    client: TestClient, user: tuple[str, str]
) -> None:
    """§7.2: 5/7 → round_half_up(500, 7) = 71 y aprueba (≥ 60 %). Observa no cuenta en `total`."""
    token, user_id = user
    complete_lesson(user_id, L1, 100, True)
    session = start(client, token, L2)
    sid = session_id_of(session)
    wrong = set(ids_of_type(session, "VIDEO_TO_MEANING")[:2])
    answer_all(client, token, session, wrong=wrong)

    result = complete(client, token, sid)
    assert result["correct"] == 5
    assert result["total"] == 7
    assert result["score"] == 71
    assert result["passed"] is True
    assert {"type": "LESSON", "id": L3} in as_list(result["unlocked"])


def test_produce_no_cuenta_en_el_puntaje(client: TestClient, user: tuple[str, str]) -> None:
    """R4.7: PRODUCE con ok=false y todo lo demás bien → 100 %."""
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    answer_all(client, token, session, wrong=set(ids_of_type(session, "PRODUCE")))

    result = complete(client, token, sid)
    assert result["total"] == 6
    assert result["correct"] == 6
    assert result["score"] == 100


def test_duracion_con_tope_de_15_minutos(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """B16: una pestaña abierta 2 h cuenta como 15 min (900 s)."""
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    answer_all(client, token, session)
    clock.advance(hours=2)
    token = login(client)

    complete(client, token, sid)
    assert db_session(sid).duration_sec == 900


def test_duracion_real_bajo_el_tope(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    answer_all(client, token, session)
    clock.advance(minutes=3)

    complete(client, token, sid)
    assert db_session(sid).duration_sec == 180


def test_tiempos_de_la_sesion_los_fija_el_clock(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    """D22, B77: `started_at`, `answered_at` y `completed_at` vienen del `Clock`, no de la BD."""
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    ids = exercise_ids(session)

    clock.advance(minutes=1)
    answer_right(client, token, sid, ids[0])
    clock.advance(minutes=1)
    for exercise_id in ids[1:]:
        answer_right(client, token, sid, exercise_id)
    clock.advance(minutes=2)
    complete(client, token, sid)

    closed = db_session(sid)
    assert closed.started_at == T0
    assert closed.completed_at == T0 + timedelta(minutes=4)
    assert closed.duration_sec == 240
    assert db_answer(sid, ids[0]).answered_at == T0 + timedelta(minutes=1)
    assert db_answer(sid, ids[-1]).answered_at == T0 + timedelta(minutes=2)


# ---------------------------------------------------------------- revisión del Grupo 5


def test_dos_errores_simultaneos_descuentan_dos_vidas(
    client: TestClient, user: tuple[str, str]
) -> None:
    """La fila del usuario se bloquea y se relee: dos errores a la vez no pierden un descuento."""
    from concurrent.futures import ThreadPoolExecutor

    token, user_id = user
    approve_lessons_before(user_id, L2)
    session = start(client, token, L2)
    sid = session_id_of(session)
    first, second = scored_ids(session)[:2]

    def wrong(exercise_id: str) -> int:
        body = wrong_answer(sid, exercise_id)
        assert body is not None
        with TestClient(client.app) as other:
            response = other.post(
                f"/api/lesson-sessions/{sid}/answers",
                json={"exerciseId": exercise_id, "answer": body},
                headers=auth(token),
            )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(wrong, [first, second]))
    assert codes == [200, 200]
    assert db_user(user_id).hearts == 3
    assert db_session(sid).hearts_lost == 2


def test_respuesta_con_campos_enormes_es_422(client: TestClient, user: tuple[str, str]) -> None:
    token, _ = user
    session = start(client, token, L1)
    sid = session_id_of(session)
    exercise_id = ids_of_type(session, "VIDEO_TO_MEANING")[0]
    response = post_answer(client, token, sid, exercise_id, {"optionToken": "x" * 5000})
    assert response.status_code == 422


def test_bloque_final_de_l1_no_tiene_grupo(client: TestClient, user: tuple[str, str]) -> None:
    """Después de observar, las preguntas mezcladas repasan todas las señas: sin grupo (D-021)."""
    token, _ = user
    groups = [exercise["group"] for exercise in exercises_of(start(client, token, L1))]
    assert groups[3:] == [None] * 9
