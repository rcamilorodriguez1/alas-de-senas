"""Tareas 9.1 y 9.2 — módulo introductorio y logro «Primer aleteo» (R1.1 a R1.6; §6.3, fila
`/intro` de §8.2 y §7.9).

- `GET /api/intro` (público, sin sesión) → `{ cards:[{slug, word, video}], quiz:[{slug, video,
  options:[{word, correct}]}] }` construido desde `content/intro.json`. `video` es el mismo
  VideoRef `{src, poster, placeholder, source}` que entrega el diccionario para la seña. El intro
  incluye la respuesta correcta porque no da XP (§8.2).
  * `cards` en el orden de `intro.json` con la palabra de la BD.
  * `quiz` en el orden de `intro.json`: 3 opciones con palabras distintas, exactamente una
    correcta (la palabra de la seña de la pregunta) y 2 distractores tomados de las otras tarjetas
    del intro; opciones ordenadas por palabra (orden de `str` de Python). Respuesta estable.
- `POST /api/auth/register` con `introCompleted: true` → logro FIRST_FLAP (10 de néctar) una sola
  vez, con `unlocked_at = clock.now()` (D22). Sin el campo o con `false` → nada.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.rate_limit import reset_rate_limits
from app.infra.db import get_engine
from app.infra.models import Sign, User, UserAchievement
from tests.api.helpers import PASSWORD, auth, correct_answer, register_user
from tests.fakes import FakeClock
from tests.unit.content.real_content import CONTENT_DIR

pytestmark = pytest.mark.usefixtures("seeded_content")

JsonObject = dict[str, object]

INTRO_URL = "/api/intro"
REGISTER_URL = "/api/auth/register"
EMAIL = "ana@ejemplo.com"

EXPECTED_CARDS = ["hola", "gracias", "por-favor", "si", "no", "adios"]
EXPECTED_QUIZ = ["gracias", "hola", "no"]
OPTIONS_PER_QUESTION = 3

INTRO_KEYS = {"cards", "quiz"}
CARD_KEYS = {"slug", "word", "video"}
QUESTION_KEYS = {"slug", "video", "options"}
OPTION_KEYS = {"word", "correct"}
VIDEO_KEYS = {"src", "poster", "placeholder", "source"}
ACHIEVEMENT_KEYS = {"id", "title", "description", "icon", "nectar", "unlockedAt"}
NEW_ACHIEVEMENT_KEYS = {"id", "title", "nectar"}

FIRST_FLAP = "FIRST_FLAP"
FIRST_FLAP_NECTAR = 10
FIRST_LESSON = {"id": "FIRST_LESSON", "title": "Primeras alas", "nectar": 10}
L1 = "M1-N1-L1"

# Hora fija cercana a la real (los tokens se emiten con el reloj inyectado).
T0 = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)


# ---------------------------------------------------------------- fixtures


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


# ---------------------------------------------------------------- ayudas JSON


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


# ---------------------------------------------------------------- ayudas HTTP


def get_intro(client: TestClient, token: str | None = None) -> JsonObject:
    headers = auth(token) if token else {}
    response = client.get(INTRO_URL, headers=headers)
    assert response.status_code == 200, response.text
    body = json_of(response)
    assert set(body) == INTRO_KEYS
    return body


def cards_of(body: JsonObject) -> list[JsonObject]:
    cards = as_list(body["cards"])
    for card in cards:
        assert set(card) == CARD_KEYS, card
    return cards


def quiz_of(body: JsonObject) -> list[JsonObject]:
    quiz = as_list(body["quiz"])
    for question in quiz:
        assert set(question) == QUESTION_KEYS, question
        for option in as_list(question["options"]):
            assert set(option) == OPTION_KEYS, option
    return quiz


def options_of(question: JsonObject) -> list[JsonObject]:
    return as_list(question["options"])


def dictionary_video(client: TestClient, slug: str) -> JsonObject:
    response = client.get(f"/api/dictionary/signs/{slug}")
    assert response.status_code == 200, response.text
    return as_obj(json_of(response)["video"])


def register(client: TestClient, intro_completed: bool | None, email: str = EMAIL) -> Response:
    payload: dict[str, object] = {
        "name": "Ana",
        "email": email,
        "password": PASSWORD,
        "dailyGoalMinutes": 10,
        "acceptedDataPolicy": True,
    }
    if intro_completed is not None:
        payload["introCompleted"] = intro_completed
    response: Response = client.post(REGISTER_URL, json=payload)
    return response


def register_ok(
    client: TestClient, intro_completed: bool | None, email: str = EMAIL
) -> tuple[str, str]:
    response = register(client, intro_completed, email)
    assert response.status_code == 201, response.text
    body = json_of(response)
    return as_str(body["accessToken"]), as_str(as_obj(body["user"])["id"])


def get_achievements(client: TestClient, token: str) -> list[JsonObject]:
    response = client.get("/api/gamification/achievements", headers=auth(token))
    assert response.status_code == 200, response.text
    items = as_list(response.json())
    for item in items:
        assert set(item) == ACHIEVEMENT_KEYS, item
    return items


def unlocked_ids(client: TestClient, token: str) -> list[str]:
    return [
        as_str(item["id"])
        for item in get_achievements(client, token)
        if item["unlockedAt"] is not None
    ]


def stats_nectar(client: TestClient, token: str) -> int:
    response = client.get("/api/gamification/stats", headers=auth(token))
    assert response.status_code == 200, response.text
    return as_int(json_of(response)["nectar"])


def do_lesson(client: TestClient, token: str, lesson_id: str = L1) -> JsonObject:
    """Empieza la lección, responde todo bien y la completa."""
    started = client.post(f"/api/lessons/{lesson_id}/sessions", headers=auth(token))
    assert started.status_code == 201, started.text
    session = json_of(started)
    session_id = as_str(session["sessionId"])
    for exercise in as_list(session["exercises"]):
        exercise_id = as_str(exercise["id"])
        answered = client.post(
            f"/api/lesson-sessions/{session_id}/answers",
            headers=auth(token),
            json={"exerciseId": exercise_id, "answer": correct_answer(session_id, exercise_id)},
        )
        assert answered.status_code == 200, answered.text
    completed = client.post(f"/api/lesson-sessions/{session_id}/complete", headers=auth(token))
    assert completed.status_code == 200, completed.text
    return json_of(completed)


def new_achievements(result: JsonObject) -> list[JsonObject]:
    items = as_list(result["newAchievements"])
    for item in items:
        assert set(item) == NEW_ACHIEVEMENT_KEYS, item
    return items


# ---------------------------------------------------------------- ayudas de BD / contenido


def intro_file() -> JsonObject:
    raw = json.loads((CONTENT_DIR / "intro.json").read_text(encoding="utf-8"))
    return as_obj(raw)


def db_words(slugs: list[str]) -> dict[str, str]:
    with Session(get_engine()) as db:
        rows = db.execute(select(Sign.id, Sign.word).where(Sign.id.in_(slugs))).all()
    return {row.id: row.word for row in rows}


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


def db_nectar(user_id: str) -> int:
    with Session(get_engine()) as db:
        found = db.get(User, uuid.UUID(user_id))
        assert found is not None
        return found.nectar


# ================================================================ 9.1 · GET /api/intro


def test_intro_json_tiene_el_contenido_esperado() -> None:
    """§6.3: guarda de la prueba (si cambia el contenido, cambian las expectativas)."""
    data = intro_file()
    assert data["cards"] == EXPECTED_CARDS
    assert [as_str(q["sign"]) for q in as_list(data["quiz"])] == EXPECTED_QUIZ


def test_intro_es_publico_sin_token(client: TestClient) -> None:
    """R1.1: el contenido de /bienvenida sale de un endpoint público."""
    response = client.get(INTRO_URL)
    assert response.status_code == 200, response.text
    assert set(json_of(response)) == INTRO_KEYS


def test_intro_con_token_tambien_responde(client: TestClient) -> None:
    token, _ = register_user(client, EMAIL)
    assert get_intro(client, token) == get_intro(client)


def test_intro_tiene_seis_tarjetas_en_el_orden_del_archivo(client: TestClient) -> None:
    """R1.2: 6 tarjetas en el orden de `content/intro.json`."""
    cards = cards_of(get_intro(client))
    assert len(cards) == 6
    assert [as_str(card["slug"]) for card in cards] == EXPECTED_CARDS


def test_tarjetas_usan_la_palabra_de_la_bd(client: TestClient) -> None:
    words = db_words(EXPECTED_CARDS)
    assert set(words) == set(EXPECTED_CARDS), "Las señas del intro deben existir en la BD"
    for card in cards_of(get_intro(client)):
        slug = as_str(card["slug"])
        assert card["word"] == words[slug], slug


def test_tarjetas_reutilizan_el_video_de_la_sena(client: TestClient) -> None:
    """§6.3: el intro reutiliza los videos de las señas (mismo VideoRef que el diccionario)."""
    for card in cards_of(get_intro(client)):
        video = as_obj(card["video"])
        assert set(video) == VIDEO_KEYS
        assert as_str(video["src"])
        assert as_str(video["poster"])
        assert isinstance(video["placeholder"], bool)
        assert as_str(video["source"])
        assert video == dictionary_video(client, as_str(card["slug"]))


def test_quiz_tiene_tres_preguntas_en_el_orden_del_archivo(client: TestClient) -> None:
    """R1.3: mini-quiz de 3 preguntas (video → significado)."""
    quiz = quiz_of(get_intro(client))
    assert len(quiz) == 3
    assert [as_str(question["slug"]) for question in quiz] == EXPECTED_QUIZ


def test_preguntas_del_quiz_reutilizan_el_video_de_la_sena(client: TestClient) -> None:
    for question in quiz_of(get_intro(client)):
        video = as_obj(question["video"])
        assert set(video) == VIDEO_KEYS
        assert video == dictionary_video(client, as_str(question["slug"]))


def test_cada_pregunta_tiene_tres_opciones_con_palabras_distintas(client: TestClient) -> None:
    for question in quiz_of(get_intro(client)):
        words = [as_str(option["word"]) for option in options_of(question)]
        assert len(words) == OPTIONS_PER_QUESTION, question
        assert len(set(words)) == OPTIONS_PER_QUESTION, question


def test_cada_pregunta_tiene_exactamente_una_opcion_correcta(client: TestClient) -> None:
    """§8.2: el intro incluye la respuesta (no da XP); la correcta es la palabra de la seña."""
    words = db_words(EXPECTED_CARDS)
    for question in quiz_of(get_intro(client)):
        options = options_of(question)
        for option in options:
            assert isinstance(option["correct"], bool), option
        correct = [option for option in options if option["correct"] is True]
        assert len(correct) == 1, question
        assert correct[0]["word"] == words[as_str(question["slug"])]


def test_distractores_son_palabras_de_otras_tarjetas_del_intro(client: TestClient) -> None:
    words = db_words(EXPECTED_CARDS)
    for question in quiz_of(get_intro(client)):
        slug = as_str(question["slug"])
        others = {words[s] for s in EXPECTED_CARDS if s != slug}
        distractors = [
            as_str(option["word"]) for option in options_of(question) if option["correct"] is False
        ]
        assert len(distractors) == OPTIONS_PER_QUESTION - 1, question
        for word in distractors:
            assert word in others, (slug, word)


def test_opciones_ordenadas_por_palabra(client: TestClient) -> None:
    """La posición de la correcta no la delata: opciones en orden de palabra (orden de str)."""
    for question in quiz_of(get_intro(client)):
        words = [as_str(option["word"]) for option in options_of(question)]
        assert words == sorted(words), question


def test_intro_es_estable_entre_llamadas(client: TestClient) -> None:
    first = get_intro(client)
    second = get_intro(client)
    third = get_intro(client)
    assert first == second == third


# ================================================================ 9.2 · registro con intro


def test_registro_con_intro_completado_otorga_primer_aleteo(
    client: TestClient, clock: FakeClock
) -> None:
    """R1.6 / §7.9: FIRST_FLAP con 10 de néctar."""
    token, user_id = register_ok(client, True)

    assert unlocked_ids(client, token) == [FIRST_FLAP]
    assert stats_nectar(client, token) == FIRST_FLAP_NECTAR
    assert db_nectar(user_id) == FIRST_FLAP_NECTAR
    rows = db_user_achievements(user_id)
    assert [row.achievement_id for row in rows] == [FIRST_FLAP]


def test_primer_aleteo_tiene_la_fecha_del_clock(client: TestClient, clock: FakeClock) -> None:
    """D22: `unlocked_at` lo fija el servicio con `clock.now()`."""
    token, user_id = register_ok(client, True)
    clock.advance(minutes=1)

    rows = db_user_achievements(user_id)
    assert [row.unlocked_at for row in rows] == [T0]
    items = {as_str(item["id"]): item for item in get_achievements(client, token)}
    assert parse_iso(items[FIRST_FLAP]["unlockedAt"]) == T0
    for achievement_id, item in items.items():
        if achievement_id != FIRST_FLAP:
            assert item["unlockedAt"] is None, achievement_id


def test_primer_aleteo_aparece_en_el_catalogo_con_sus_datos(
    client: TestClient, clock: FakeClock
) -> None:
    token, _ = register_ok(client, True)
    items = {as_str(item["id"]): item for item in get_achievements(client, token)}
    assert items[FIRST_FLAP]["title"] == "Primer aleteo"
    assert items[FIRST_FLAP]["nectar"] == FIRST_FLAP_NECTAR


def test_registro_sin_intro_completado_no_otorga_logros(client: TestClient) -> None:
    token, user_id = register_ok(client, None)

    assert unlocked_ids(client, token) == []
    assert stats_nectar(client, token) == 0
    assert db_user_achievements(user_id) == []


def test_registro_con_intro_false_no_otorga_logros(client: TestClient) -> None:
    token, user_id = register_ok(client, False)

    assert unlocked_ids(client, token) == []
    assert stats_nectar(client, token) == 0
    assert db_user_achievements(user_id) == []


def test_primer_aleteo_solo_para_el_usuario_que_completo_el_intro(client: TestClient) -> None:
    with_intro, with_intro_id = register_ok(client, True, "ana@ejemplo.com")
    without_intro, without_intro_id = register_ok(client, False, "beto@ejemplo.com")

    assert unlocked_ids(client, with_intro) == [FIRST_FLAP]
    assert unlocked_ids(client, without_intro) == []
    assert db_nectar(with_intro_id) == FIRST_FLAP_NECTAR
    assert db_nectar(without_intro_id) == 0


def test_primer_aleteo_no_se_repite_al_completar_la_primera_leccion(
    client: TestClient, clock: FakeClock
) -> None:
    """R1.6 «una sola vez»: L1 da FIRST_LESSON pero no repite FIRST_FLAP ni su néctar."""
    token, user_id = register_ok(client, True)
    result = do_lesson(client, token)

    assert result["passed"] is True
    achievements = new_achievements(result)
    assert FIRST_FLAP not in [as_str(item["id"]) for item in achievements]
    assert achievements == [FIRST_LESSON]

    lesson_nectar = as_int(result["nectarEarned"])
    expected = FIRST_FLAP_NECTAR + lesson_nectar + as_int(FIRST_LESSON["nectar"])
    assert stats_nectar(client, token) == expected
    assert db_nectar(user_id) == expected
    assert [row.achievement_id for row in db_user_achievements(user_id)] == [
        FIRST_FLAP,
        "FIRST_LESSON",
    ]


def test_sin_intro_la_primera_leccion_no_otorga_primer_aleteo(
    client: TestClient, clock: FakeClock
) -> None:
    """FIRST_FLAP solo se evalúa al registrarse con el intro completo (§7.9)."""
    token, user_id = register_ok(client, False)
    result = do_lesson(client, token)

    assert FIRST_FLAP not in [as_str(item["id"]) for item in new_achievements(result)]
    assert FIRST_FLAP not in unlocked_ids(client, token)
    assert db_nectar(user_id) == as_int(result["nectarEarned"]) + as_int(FIRST_LESSON["nectar"])


def test_registro_duplicado_con_intro_no_duplica_el_logro(client: TestClient) -> None:
    """Un segundo registro con el mismo correo falla y no paga néctar doble."""
    token, user_id = register_ok(client, True)
    again = register(client, True)
    assert again.status_code == 409, again.text

    assert unlocked_ids(client, token) == [FIRST_FLAP]
    assert db_nectar(user_id) == FIRST_FLAP_NECTAR
    assert [row.achievement_id for row in db_user_achievements(user_id)] == [FIRST_FLAP]
