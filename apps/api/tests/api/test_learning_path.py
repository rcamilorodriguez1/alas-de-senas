"""Tarea 4.1 — `GET /api/learning-path` y `GET /api/nodes/{node_id}` (R3, §7.4, §8.1, §8.2, B6, B8,
D-007.9).

El progreso se deriva de las `LessonSession` completadas (no se guarda como estado, B6). Las
sesiones se insertan directamente en la BD con `complete_lesson` para aislar el cálculo de la
ruta del flujo de lecciones (Grupo 5).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Connection

from app.core.rate_limit import reset_rate_limits
from app.infra.db import get_engine
from tests.api.helpers import auth, complete_lesson, register_user

pytestmark = pytest.mark.usefixtures("seeded_content")

JsonObject = dict[str, object]

MODULE_KEYS = {"id", "order", "title", "description", "published", "status", "progress", "nodes"}
NODE_KEYS = {"id", "order", "title", "kind", "status", "lessons"}
LESSON_KEYS = {"id", "order", "type", "title", "status", "bestScore", "estimatedXp"}
NODE_DETAIL_KEYS = {"id", "title", "kind", "status", "moduleId", "moduleTitle", "lessons", "signs"}
SIGN_KEYS = {"slug", "word", "poster", "introducedInLessonId"}

PUBLISHED_MODULES = ("M1", "M2", "M3")
LESSON_TYPES = ["LEARN", "RECOGNIZE", "PRACTICE", "CHALLENGE"]
M1_N1_SIGNS = [
    "hola",
    "buenos-dias",
    "buenas-tardes",
    "buenas-noches",
    "como-estas",
    "adios",
    "gracias",
    "por-favor",
    "de-nada",
]
MAX_QUERIES = 8


@pytest.fixture(autouse=True)
def reset_limits() -> Iterator[None]:
    reset_rate_limits()
    yield
    reset_rate_limits()


# ---------------------------------------------------------------- ayudas


def lesson_ids(node_id: str) -> list[str]:
    return [f"{node_id}-L{n}" for n in range(1, 5)]


def module_lesson_ids(module_id: str) -> list[str]:
    return [lid for n in range(1, 5) for lid in lesson_ids(f"{module_id}-N{n}")]


def approve_node(user_id: str, node_id: str, challenge_score: int = 90) -> None:
    for lid in lesson_ids(node_id)[:3]:
        complete_lesson(user_id, lid, 100, True)
    complete_lesson(user_id, f"{node_id}-L4", challenge_score, True)


def approve_module(user_id: str, module_id: str) -> None:
    for n in range(1, 5):
        approve_node(user_id, f"{module_id}-N{n}")


def get_path(client: TestClient, token: str) -> JsonObject:
    response = client.get("/api/learning-path", headers=auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def as_list(value: object) -> list[JsonObject]:
    assert isinstance(value, list)
    for item in value:
        assert isinstance(item, dict)
    return value


def modules_of(path: JsonObject) -> list[JsonObject]:
    return as_list(path["modules"])


def module(path: JsonObject, module_id: str) -> JsonObject:
    for item in modules_of(path):
        if item["id"] == module_id:
            return item
    raise AssertionError(f"Falta el módulo {module_id}")


def node(path: JsonObject, node_id: str) -> JsonObject:
    for mod in modules_of(path):
        for item in as_list(mod["nodes"]):
            if item["id"] == node_id:
                return item
    raise AssertionError(f"Falta el nodo {node_id}")


def lesson(path: JsonObject, lesson_id: str) -> JsonObject:
    for mod in modules_of(path):
        for nd in as_list(mod["nodes"]):
            for item in as_list(nd["lessons"]):
                if item["id"] == lesson_id:
                    return item
    raise AssertionError(f"Falta la lección {lesson_id}")


def all_lessons(path: JsonObject) -> list[JsonObject]:
    return [
        item
        for mod in modules_of(path)
        for nd in as_list(mod["nodes"])
        for item in as_list(nd["lessons"])
    ]


def lesson_statuses(path: JsonObject) -> dict[str, object]:
    return {str(item["id"]): item["status"] for item in all_lessons(path)}


def get_node(client: TestClient, token: str, node_id: str) -> JsonObject:
    response = client.get(f"/api/nodes/{node_id}", headers=auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def count_queries(client: TestClient, token: str) -> int:
    statements: list[str] = []

    def before_cursor_execute(
        conn: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get("/api/learning-path", headers=auth(token))
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    assert response.status_code == 200, response.text
    return len(statements)


# ---------------------------------------------------------------- autenticación


def test_ruta_sin_token_da_401(client: TestClient) -> None:
    response = client.get("/api/learning-path")
    assert response.status_code == 401
    assert response.json()["statusCode"] == 401


def test_nodo_sin_token_da_401(client: TestClient) -> None:
    response = client.get("/api/nodes/M1-N1")
    assert response.status_code == 401


# ---------------------------------------------------------------- forma y orden (B8)


def test_ruta_forma_de_modulos_nodos_y_lecciones(client: TestClient) -> None:
    token, _ = register_user(client)
    path = get_path(client, token)

    assert set(path) == {"modules"}
    mods = modules_of(path)
    assert [m["id"] for m in mods] == ["M1", "M2", "M3", "M4"]
    for mod in mods:
        assert set(mod) == MODULE_KEYS
        assert isinstance(mod["title"], str)
        assert isinstance(mod["description"], str)
        nodes = as_list(mod["nodes"])
        assert len(nodes) == 4
        for nd in nodes:
            assert set(nd) == NODE_KEYS
            for ls in as_list(nd["lessons"]):
                assert set(ls) == LESSON_KEYS
                assert isinstance(ls["title"], str)

    m1 = module(path, "M1")
    assert m1["title"] == "Fundamentos de la LSC"
    assert m1["published"] is True
    assert module(path, "M4")["published"] is False
    assert node(path, "M1-N3")["kind"] == "ALPHABET"
    assert node(path, "M2-N3")["kind"] == "NUMBERS"
    assert node(path, "M1-N1")["kind"] == "STANDARD"


def test_ruta_ordenada_por_order_en_modulos_nodos_y_lecciones(client: TestClient) -> None:
    token, _ = register_user(client)
    mods = modules_of(get_path(client, token))

    assert [m["order"] for m in mods] == [1, 2, 3, 4]
    for mod in mods:
        nodes = as_list(mod["nodes"])
        assert [nd["order"] for nd in nodes] == [1, 2, 3, 4]
        assert [nd["id"] for nd in nodes] == [f"{mod['id']}-N{n}" for n in range(1, 5)]
        if mod["published"] is not True:
            continue
        for nd in nodes:
            lessons = as_list(nd["lessons"])
            assert [ls["order"] for ls in lessons] == [1, 2, 3, 4]
            assert [ls["id"] for ls in lessons] == lesson_ids(str(nd["id"]))
            assert [ls["type"] for ls in lessons] == LESSON_TYPES


def test_ruta_es_estable_entre_peticiones(client: TestClient) -> None:
    token, _ = register_user(client)
    assert get_path(client, token) == get_path(client, token)


# ---------------------------------------------------------------- usuario nuevo (R3.2)


def test_usuario_nuevo_solo_m1_n1_l1_disponible(client: TestClient) -> None:
    token, _ = register_user(client)
    statuses = lesson_statuses(get_path(client, token))

    assert len(statuses) == 48
    assert statuses.pop("M1-N1-L1") == "AVAILABLE"
    assert set(statuses.values()) == {"LOCKED"}


def test_usuario_nuevo_estados_de_modulos_y_nodos(client: TestClient) -> None:
    token, _ = register_user(client)
    path = get_path(client, token)

    m1 = module(path, "M1")
    assert m1["status"] == "IN_PROGRESS"
    assert m1["progress"] == 0
    for mid in ("M2", "M3"):
        assert module(path, mid)["status"] == "LOCKED"
        assert module(path, mid)["progress"] == 0

    assert node(path, "M1-N1")["status"] == "IN_PROGRESS"
    for nid in ("M1-N2", "M1-N3", "M1-N4", "M2-N1", "M3-N4"):
        assert node(path, nid)["status"] == "LOCKED"


def test_modulo_no_publicado_es_proximamente_con_nodos_sin_lecciones(client: TestClient) -> None:
    token, _ = register_user(client)
    m4 = module(get_path(client, token), "M4")

    assert m4["status"] == "COMING_SOON"
    assert m4["progress"] == 0
    nodes = as_list(m4["nodes"])
    assert len(nodes) == 4
    for nd in nodes:
        assert nd["status"] == "COMING_SOON"
        assert nd["lessons"] == []


def test_usuario_nuevo_best_score_nulo_y_xp_estimada(client: TestClient) -> None:
    token, _ = register_user(client)
    path = get_path(client, token)

    for ls in all_lessons(path):
        assert ls["bestScore"] is None
        expected = 30 if ls["type"] == "CHALLENGE" else 20
        assert ls["estimatedXp"] == expected, ls["id"]


# ---------------------------------------------------------------- desbloqueo (R3.3, R3.4)


def test_aprobar_l1_desbloquea_l2(client: TestClient) -> None:
    token, uid = register_user(client)
    complete_lesson(uid, "M1-N1-L1", 80, True)
    path = get_path(client, token)

    assert lesson(path, "M1-N1-L1")["status"] == "COMPLETED"
    assert lesson(path, "M1-N1-L2")["status"] == "AVAILABLE"
    assert lesson(path, "M1-N1-L3")["status"] == "LOCKED"
    assert node(path, "M1-N1")["status"] == "IN_PROGRESS"


def test_reprobar_no_desbloquea(client: TestClient) -> None:
    token, uid = register_user(client)
    complete_lesson(uid, "M1-N1-L1", 40, False)
    path = get_path(client, token)

    l1 = lesson(path, "M1-N1-L1")
    assert l1["status"] == "AVAILABLE"
    assert l1["bestScore"] == 40
    assert l1["estimatedXp"] == 20
    assert lesson(path, "M1-N1-L2")["status"] == "LOCKED"
    assert module(path, "M1")["progress"] == 0


def test_sesion_sin_completar_no_cuenta_ni_desbloquea(client: TestClient) -> None:
    token, uid = register_user(client)
    complete_lesson(uid, "M1-N1-L1", 100, True, completed_at=None)
    path = get_path(client, token)

    l1 = lesson(path, "M1-N1-L1")
    assert l1["status"] == "AVAILABLE"
    assert l1["bestScore"] is None
    assert lesson(path, "M1-N1-L2")["status"] == "LOCKED"


def test_desbloqueo_secuencial_dentro_del_nodo_hasta_el_siguiente_nodo(
    client: TestClient,
) -> None:
    token, uid = register_user(client)
    for lid in lesson_ids("M1-N1")[:3]:
        complete_lesson(uid, lid, 100, True)
    path = get_path(client, token)
    assert lesson(path, "M1-N1-L4")["status"] == "AVAILABLE"
    assert lesson(path, "M1-N2-L1")["status"] == "LOCKED"
    assert node(path, "M1-N2")["status"] == "LOCKED"

    complete_lesson(uid, "M1-N1-L4", 70, True)
    path = get_path(client, token)
    assert lesson(path, "M1-N2-L1")["status"] == "AVAILABLE"
    assert node(path, "M1-N2")["status"] == "IN_PROGRESS"


# ---------------------------------------------------------------- nodo dorado (R3.5)


def test_reto_con_100_deja_nodo_y_leccion_dorados(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_node(uid, "M1-N1", challenge_score=100)
    path = get_path(client, token)

    assert lesson(path, "M1-N1-L4")["status"] == "GOLDEN"
    assert node(path, "M1-N1")["status"] == "GOLDEN"
    for lid in lesson_ids("M1-N1")[:3]:
        assert lesson(path, lid)["status"] == "COMPLETED"


def test_reto_con_80_deja_nodo_completado(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_node(uid, "M1-N1", challenge_score=80)
    path = get_path(client, token)

    assert lesson(path, "M1-N1-L4")["status"] == "COMPLETED"
    assert node(path, "M1-N1")["status"] == "COMPLETED"


def test_dorado_si_alguna_sesion_del_reto_tuvo_100(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_node(uid, "M1-N1", challenge_score=80)
    complete_lesson(uid, "M1-N1-L4", 100, True)
    complete_lesson(uid, "M1-N1-L4", 75, True)
    path = get_path(client, token)

    assert lesson(path, "M1-N1-L4")["bestScore"] == 100
    assert lesson(path, "M1-N1-L4")["status"] == "GOLDEN"
    assert node(path, "M1-N1")["status"] == "GOLDEN"


# ---------------------------------------------------------------- progreso de módulo


def test_progreso_m1_con_4_de_16_aprobadas_es_25(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_node(uid, "M1-N1")
    path = get_path(client, token)

    m1 = module(path, "M1")
    assert m1["progress"] == 25
    assert m1["status"] == "IN_PROGRESS"


def test_progreso_redondea_hacia_arriba_la_mitad(client: TestClient) -> None:
    # 2/16 = 12,5 % → 13 (round_half_up; `round()` daría 12).
    token, uid = register_user(client)
    complete_lesson(uid, "M1-N1-L1", 100, True)
    complete_lesson(uid, "M1-N1-L2", 100, True)
    assert module(get_path(client, token), "M1")["progress"] == 13


def test_progreso_es_entero(client: TestClient) -> None:
    # 1/16 = 6,25 % → 6.
    token, uid = register_user(client)
    complete_lesson(uid, "M1-N1-L1", 100, True)
    progress = module(get_path(client, token), "M1")["progress"]
    assert isinstance(progress, int)
    assert progress == 6


def test_reprobaciones_repetidas_no_suman_progreso(client: TestClient) -> None:
    token, uid = register_user(client)
    for _ in range(3):
        complete_lesson(uid, "M1-N1-L1", 20, False)
    assert module(get_path(client, token), "M1")["progress"] == 0


def test_aprobar_dos_veces_cuenta_una_sola_leccion(client: TestClient) -> None:
    token, uid = register_user(client)
    complete_lesson(uid, "M1-N1-L1", 70, True)
    complete_lesson(uid, "M1-N1-L1", 100, True)
    assert module(get_path(client, token), "M1")["progress"] == 6


def test_aprobar_todo_m1_lo_completa_y_desbloquea_m2(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_module(uid, "M1")
    path = get_path(client, token)

    m1 = module(path, "M1")
    assert m1["status"] == "COMPLETED"
    assert m1["progress"] == 100
    for n in range(1, 5):
        assert node(path, f"M1-N{n}")["status"] == "COMPLETED"

    assert lesson(path, "M2-N1-L1")["status"] == "AVAILABLE"
    assert lesson(path, "M2-N1-L2")["status"] == "LOCKED"
    assert node(path, "M2-N1")["status"] == "IN_PROGRESS"
    m2 = module(path, "M2")
    assert m2["status"] == "IN_PROGRESS"
    assert m2["progress"] == 0
    assert module(path, "M3")["status"] == "LOCKED"
    assert module(path, "M4")["status"] == "COMING_SOON"


def test_modulo_completado_con_nodos_dorados_y_completados(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_node(uid, "M1-N1", challenge_score=100)
    for n in range(2, 5):
        approve_node(uid, f"M1-N{n}", challenge_score=80)
    path = get_path(client, token)

    assert node(path, "M1-N1")["status"] == "GOLDEN"
    assert module(path, "M1")["status"] == "COMPLETED"


def test_modulo_no_publicado_no_bloquea_ni_cuenta(client: TestClient) -> None:
    # M3 es el último publicado; después de él la ruta termina (M4 sigue COMING_SOON).
    token, uid = register_user(client)
    for mid in PUBLISHED_MODULES:
        approve_module(uid, mid)
    path = get_path(client, token)

    for mid in PUBLISHED_MODULES:
        assert module(path, mid)["status"] == "COMPLETED"
        assert module(path, mid)["progress"] == 100
    m4 = module(path, "M4")
    assert m4["status"] == "COMING_SOON"
    assert m4["progress"] == 0
    assert {ls["status"] for ls in all_lessons(path)} == {"COMPLETED"}


# ---------------------------------------------------------------- bestScore y estimatedXp


def test_best_score_es_el_maximo_de_sesiones_completadas(client: TestClient) -> None:
    token, uid = register_user(client)
    complete_lesson(uid, "M1-N1-L1", 60, True)
    complete_lesson(uid, "M1-N1-L1", 90, True)
    complete_lesson(uid, "M1-N1-L1", 100, True, completed_at=None)
    path = get_path(client, token)

    assert lesson(path, "M1-N1-L1")["bestScore"] == 90


def test_best_score_incluye_sesiones_reprobadas(client: TestClient) -> None:
    token, uid = register_user(client)
    complete_lesson(uid, "M1-N1-L1", 50, False)
    complete_lesson(uid, "M1-N1-L1", 30, False)
    assert lesson(get_path(client, token), "M1-N1-L1")["bestScore"] == 50


def test_xp_estimada_baja_a_la_mitad_tras_aprobar(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_node(uid, "M1-N1", challenge_score=80)
    path = get_path(client, token)

    for lid in lesson_ids("M1-N1")[:3]:
        assert lesson(path, lid)["estimatedXp"] == 10
    assert lesson(path, "M1-N1-L4")["estimatedXp"] == 15
    # Las lecciones aún no aprobadas conservan la XP de la primera vez.
    assert lesson(path, "M1-N2-L1")["estimatedXp"] == 20
    assert lesson(path, "M1-N2-L4")["estimatedXp"] == 30


def test_xp_estimada_no_cambia_si_solo_reprobo(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_node(uid, "M1-N1", challenge_score=80)
    complete_lesson(uid, "M1-N2-L1", 100, True)
    complete_lesson(uid, "M1-N2-L2", 100, True)
    complete_lesson(uid, "M1-N2-L3", 100, True)
    complete_lesson(uid, "M1-N2-L4", 60, False)
    path = get_path(client, token)

    l4 = lesson(path, "M1-N2-L4")
    assert l4["estimatedXp"] == 30
    assert l4["status"] == "AVAILABLE"
    assert l4["bestScore"] == 60


# ---------------------------------------------------------------- aislamiento por usuario


def test_progreso_de_otro_usuario_no_afecta(client: TestClient) -> None:
    _, other_id = register_user(client, email="otro@ejemplo.com")
    approve_module(other_id, "M1")
    complete_lesson(other_id, "M2-N1-L1", 100, True)

    token, _ = register_user(client, email="ana@ejemplo.com")
    path = get_path(client, token)

    statuses = lesson_statuses(path)
    assert statuses.pop("M1-N1-L1") == "AVAILABLE"
    assert set(statuses.values()) == {"LOCKED"}
    assert module(path, "M1")["progress"] == 0
    assert all(ls["bestScore"] is None for ls in all_lessons(path))
    assert get_node(client, token, "M1-N1")["status"] == "IN_PROGRESS"


# ---------------------------------------------------------------- contenido nuevo (R3.7, B6)


def test_estado_derivado_se_conserva_entre_peticiones(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_node(uid, "M1-N1")
    first = get_path(client, token)
    second = get_path(client, token)
    assert lesson_statuses(first) == lesson_statuses(second)
    assert node(second, "M1-N1")["status"] == "COMPLETED"


# ---------------------------------------------------------------- sin N+1 (§8.1)


def test_ruta_sin_n_mas_1(client: TestClient) -> None:
    token, uid = register_user(client)
    get_path(client, token)  # calentamiento (caché de metadatos, conexión)

    empty = count_queries(client, token)
    complete_lesson(uid, "M1-N1-L1", 100, True)
    one = count_queries(client, token)
    approve_module(uid, "M1")
    full = count_queries(client, token)

    assert empty == one == full
    assert full <= MAX_QUERIES


# ---------------------------------------------------------------- GET /nodes/{node_id}


def test_nodo_forma_y_datos(client: TestClient) -> None:
    token, _ = register_user(client)
    body = get_node(client, token, "M1-N1")

    assert set(body) == NODE_DETAIL_KEYS
    assert body["id"] == "M1-N1"
    assert body["title"] == "Saludos y cortesía"
    assert body["kind"] == "STANDARD"
    assert body["status"] == "IN_PROGRESS"
    assert body["moduleId"] == "M1"
    assert body["moduleTitle"] == "Fundamentos de la LSC"


def test_nodo_lecciones_iguales_que_en_la_ruta(client: TestClient) -> None:
    token, uid = register_user(client)
    complete_lesson(uid, "M1-N1-L1", 60, True)
    complete_lesson(uid, "M1-N1-L1", 90, True)
    body = get_node(client, token, "M1-N1")
    path = get_path(client, token)

    lessons = as_list(body["lessons"])
    assert [ls["id"] for ls in lessons] == lesson_ids("M1-N1")
    for ls in lessons:
        assert set(ls) == LESSON_KEYS
    assert lessons == node(path, "M1-N1")["lessons"]
    assert lessons[0]["status"] == "COMPLETED"
    assert lessons[0]["bestScore"] == 90
    assert lessons[0]["estimatedXp"] == 10
    assert lessons[1]["status"] == "AVAILABLE"
    assert lessons[2]["status"] == "LOCKED"


def test_nodo_senas_ordenadas(client: TestClient) -> None:
    token, _ = register_user(client)
    signs = as_list(get_node(client, token, "M1-N1")["signs"])

    assert [s["slug"] for s in signs] == M1_N1_SIGNS
    for s in signs:
        assert set(s) == SIGN_KEYS
        poster = s["poster"]
        assert isinstance(poster, str)
        assert poster.startswith("/media/p/")
        assert poster.endswith(".jpg")
    first = signs[0]
    assert first["slug"] == "hola"
    assert first["word"] == "Hola"
    assert first["introducedInLessonId"] == "M1-N1-L1"
    assert {s["introducedInLessonId"] for s in signs} <= set(lesson_ids("M1-N1"))


def test_nodo_con_enie_en_el_alfabeto(client: TestClient) -> None:
    token, _ = register_user(client)
    body = get_node(client, token, "M1-N4")
    signs = as_list(body["signs"])

    assert body["kind"] == "ALPHABET"
    assert [s["slug"] for s in signs][:2] == ["letra-n", "letra-n-tilde"]
    assert signs[1]["word"] == "Ñ"


def test_nodo_bloqueado_se_puede_consultar(client: TestClient) -> None:
    token, _ = register_user(client)
    body = get_node(client, token, "M2-N1")

    assert body["status"] == "LOCKED"
    assert body["moduleId"] == "M2"
    lessons = as_list(body["lessons"])
    assert len(lessons) == 4
    assert {ls["status"] for ls in lessons} == {"LOCKED"}
    assert len(as_list(body["signs"])) > 0


def test_nodo_dorado(client: TestClient) -> None:
    token, uid = register_user(client)
    approve_node(uid, "M1-N1", challenge_score=100)
    assert get_node(client, token, "M1-N1")["status"] == "GOLDEN"


@pytest.mark.parametrize("node_id", ["M9-N9", "M1-N5", "no-existe", "M4-N1"])
def test_nodo_inexistente_o_no_publicado_da_404(client: TestClient, node_id: str) -> None:
    token, _ = register_user(client)
    response = client.get(f"/api/nodes/{node_id}", headers=auth(token))

    assert response.status_code == 404, response.text
    assert response.json() == {
        "statusCode": 404,
        "code": "NODE_NOT_FOUND",
        "message": "No encontramos este nodo.",
    }
