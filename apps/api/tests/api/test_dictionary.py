"""Tarea 8.1 — diccionario: búsqueda, sugerencias, categorías, ficha y favoritos (R7.1 a R7.7;
§7.8; filas `/dictionary` de §8.2).

- `GET /api/dictionary/signs?q=&category=&page=` (token opcional) → `{ items:[{slug, word,
  category:{id, name}, video}], page, pageSize, total, suggestions:[{slug, word}] }`. 24 por
  página; `page` ≥ 1 y `q` ≤ 80 caracteres (si no, 422 VALIDATION_ERROR). La búsqueda compara
  `normalize_text(q)` contenido en `signs.normalized_word` (sin mayúsculas, tildes ni signos,
  conservando la ñ); `%`, `_` y `\\` son literales. Orden por `normalized_word` y luego slug.
  `suggestions` solo si `total == 0` y `q` no está vacío: Levenshtein ≤ 2, por distancia y luego
  palabra, máx. 5.
- `GET /api/dictionary/signs/{slug}` (token opcional) → ficha con `relatedLesson` (lección de
  `introduced_in_lesson_id` si su módulo está publicado; `status` derivado de la ruta con token,
  `null` sin token) e `isFavorite`. Slug inexistente → 404 SIGN_NOT_FOUND.
- `GET /api/dictionary/categories` (público) → `[{id, name, count}]` solo con señas, por `order`.
- Favoritos (requieren token): GET (recientes primero), POST y DELETE idempotentes (204);
  `favorites.created_at` lo fija el `Clock` (D22).

Las expectativas se calculan con consultas propias a la BD (contenido real sembrado) y con las
funciones puras `normalize_text` y `levenshtein` del dominio.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.rate_limit import reset_rate_limits
from app.domain.text import levenshtein, normalize_text
from app.infra.db import get_engine
from app.infra.models import Category, Favorite, Lesson, Module, Node, Sign
from tests.api.helpers import auth, complete_lesson, register_user
from tests.fakes import FakeClock

pytestmark = pytest.mark.usefixtures("seeded_content")

JsonObject = dict[str, object]

EMAIL = "ana@ejemplo.com"
OTHER_EMAIL = "beto@ejemplo.com"

SIGNS_URL = "/api/dictionary/signs"
CATEGORIES_URL = "/api/dictionary/categories"
FAVORITES_URL = "/api/dictionary/favorites"

PAGE_SIZE = 24
MAX_Q = 80
MAX_SUGGESTIONS = 5

LIST_KEYS = {"items", "page", "pageSize", "total", "suggestions"}
ITEM_KEYS = {"slug", "word", "category", "video"}
CATEGORY_REF_KEYS = {"id", "name"}
VIDEO_KEYS = {"src", "poster", "placeholder", "source"}
SUGGESTION_KEYS = {"slug", "word"}
DETAIL_KEYS = {
    "slug",
    "word",
    "meaning",
    "category",
    "howTo",
    "usageExample",
    "video",
    "relatedLesson",
    "isFavorite",
}
RELATED_LESSON_KEYS = {"id", "title", "status"}
CATEGORY_KEYS = {"id", "name", "count"}

# Hora fija cercana a la real (los tokens se emiten con el reloj inyectado).
T0 = datetime.now(UTC).replace(microsecond=0)

EMPTY_CATEGORY_ID = "zz-vacia-prueba"


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


@pytest.fixture
def user(client: TestClient) -> tuple[str, str]:
    return register_user(client, EMAIL)


@pytest.fixture
def token(user: tuple[str, str]) -> str:
    return user[0]


@pytest.fixture
def empty_category() -> Iterator[str]:
    """Categoría temporal sin señas (el contenido real no tiene ninguna vacía)."""
    with Session(get_engine()) as db:
        max_order = db.execute(select(func.max(Category.order))).scalar_one()
        db.add(Category(id=EMPTY_CATEGORY_ID, name="Vacía de prueba", order=(max_order or 0) + 1))
        db.commit()
    try:
        yield EMPTY_CATEGORY_ID
    finally:
        with Session(get_engine()) as db:
            db.execute(delete(Category).where(Category.id == EMPTY_CATEGORY_ID))
            db.commit()


@pytest.fixture
def unpublished_m3() -> Iterator[str]:
    """Despublica M3 durante la prueba y lo restaura al final."""
    with Session(get_engine()) as db:
        db.execute(update(Module).where(Module.id == "M3").values(published=False))
        db.commit()
    try:
        yield "M3"
    finally:
        with Session(get_engine()) as db:
            db.execute(update(Module).where(Module.id == "M3").values(published=True))
            db.commit()


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


def assert_error(response: Response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = json_of(response)
    assert body["statusCode"] == status
    assert body["code"] == code
    assert isinstance(body["message"], str)
    assert body["message"]


# ---------------------------------------------------------------- ayudas HTTP


def search(
    client: TestClient,
    *,
    q: str | None = None,
    category: str | None = None,
    page: int | None = None,
    token: str | None = None,
) -> JsonObject:
    params: dict[str, str | int] = {}
    if q is not None:
        params["q"] = q
    if category is not None:
        params["category"] = category
    if page is not None:
        params["page"] = page
    headers = auth(token) if token else {}
    response = client.get(SIGNS_URL, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return json_of(response)


def search_all(
    client: TestClient, *, q: str | None = None, category: str | None = None
) -> list[str]:
    """Recorre todas las páginas y devuelve los slugs en orden."""
    first = search(client, q=q, category=category, page=1)
    total = as_int(first["total"])
    slugs = [as_str(i["slug"]) for i in as_list(first["items"])]
    page = 2
    while len(slugs) < total:
        body = search(client, q=q, category=category, page=page)
        items = as_list(body["items"])
        assert items, f"La página {page} vino vacía con total={total}"
        slugs += [as_str(i["slug"]) for i in items]
        page += 1
    return slugs


def slugs_of(body: JsonObject) -> list[str]:
    return [as_str(i["slug"]) for i in as_list(body["items"])]


def get_detail(client: TestClient, slug: str, token: str | None = None) -> JsonObject:
    headers = auth(token) if token else {}
    response = client.get(f"{SIGNS_URL}/{slug}", headers=headers)
    assert response.status_code == 200, response.text
    return json_of(response)


def add_favorite(client: TestClient, token: str, slug: str) -> None:
    response = client.post(f"{FAVORITES_URL}/{slug}", headers=auth(token))
    assert response.status_code == 204, response.text


def remove_favorite(client: TestClient, token: str, slug: str) -> None:
    response = client.delete(f"{FAVORITES_URL}/{slug}", headers=auth(token))
    assert response.status_code == 204, response.text


def get_favorites(client: TestClient, token: str) -> list[JsonObject]:
    response = client.get(FAVORITES_URL, headers=auth(token))
    assert response.status_code == 200, response.text
    return as_list(response.json())


def lesson_status_in_path(client: TestClient, token: str, lesson_id: str) -> str:
    response = client.get("/api/learning-path", headers=auth(token))
    assert response.status_code == 200, response.text
    for module in as_list(json_of(response)["modules"]):
        for node in as_list(module["nodes"]):
            for lesson in as_list(node["lessons"]):
                if lesson["id"] == lesson_id:
                    return as_str(lesson["status"])
    raise AssertionError(f"La lección {lesson_id} no aparece en la ruta")


# ---------------------------------------------------------------- oráculos (BD)


def all_signs_ordered() -> list[Sign]:
    with Session(get_engine()) as db:
        return list(db.execute(select(Sign).order_by(Sign.normalized_word, Sign.id)).scalars())


def sign_row(slug: str) -> Sign:
    with Session(get_engine()) as db:
        return db.execute(select(Sign).where(Sign.id == slug)).scalar_one()


def category_row(category_id: str) -> Category:
    with Session(get_engine()) as db:
        return db.execute(select(Category).where(Category.id == category_id)).scalar_one()


def lesson_row(lesson_id: str) -> Lesson:
    with Session(get_engine()) as db:
        return db.execute(select(Lesson).where(Lesson.id == lesson_id)).scalar_one()


def expected_slugs(q: str = "", category: str | None = None) -> list[str]:
    term = normalize_text(q)
    return [
        s.id
        for s in all_signs_ordered()
        if term in s.normalized_word and (category is None or s.category_id == category)
    ]


def expected_suggestions(q: str) -> list[str]:
    term = normalize_text(q)
    scored = [(levenshtein(term, s.normalized_word), s.word, s.id) for s in all_signs_ordered()]
    close = sorted(c for c in scored if c[0] <= 2)
    return [slug for _, _, slug in close[:MAX_SUGGESTIONS]]


def expected_video(sign: Sign) -> JsonObject:
    source = sign.media_source if sign.media_source in {"images", "placeholder"} else "video"
    return {
        "src": sign.video_path,
        "poster": sign.poster_path,
        "placeholder": sign.is_placeholder,
        "source": source,
    }


def expected_item(slug: str) -> JsonObject:
    sign = sign_row(slug)
    category = category_row(sign.category_id)
    return {
        "slug": sign.id,
        "word": sign.word,
        "category": {"id": category.id, "name": category.name},
        "video": expected_video(sign),
    }


def sign_introduced_in(lesson_id: str) -> str:
    with Session(get_engine()) as db:
        slug = db.execute(
            select(Sign.id)
            .where(Sign.introduced_in_lesson_id == lesson_id)
            .order_by(Sign.order, Sign.id)
            .limit(1)
        ).scalar_one_or_none()
    assert slug is not None, f"Ninguna seña se introduce en {lesson_id}"
    return slug


def favorite_rows(user_id: str) -> list[Favorite]:
    with Session(get_engine()) as db:
        return list(
            db.execute(
                select(Favorite)
                .where(Favorite.user_id == uuid.UUID(user_id))
                .order_by(Favorite.sign_id)
            ).scalars()
        )


# ================================================================ búsqueda: forma y paginación


def test_listado_sin_token_responde_200_con_la_forma_del_contrato(client: TestClient) -> None:
    body = search(client)
    assert set(body) == LIST_KEYS
    assert body["page"] == 1
    assert body["pageSize"] == PAGE_SIZE
    assert as_int(body["total"]) == len(all_signs_ordered())
    assert body["suggestions"] == []
    items = as_list(body["items"])
    assert len(items) == PAGE_SIZE
    for item in items:
        assert set(item) == ITEM_KEYS
        assert set(as_obj(item["category"])) == CATEGORY_REF_KEYS
        assert set(as_obj(item["video"])) == VIDEO_KEYS


def test_listado_con_token_tambien_responde_200(client: TestClient, token: str) -> None:
    body = search(client, token=token)
    assert as_int(body["total"]) == len(all_signs_ordered())


def test_cada_item_trae_palabra_categoria_y_video_de_la_bd(client: TestClient) -> None:
    body = search(client, q="gracias")
    assert as_list(body["items"]) == [expected_item("gracias")]


def test_item_de_categoria_cortesia_trae_id_y_nombre(client: TestClient) -> None:
    item = as_list(search(client, q="gracias")["items"])[0]
    assert item["category"] == {"id": "cortesia", "name": "Cortesía"}


def test_listado_ordenado_por_palabra_normalizada_y_slug(client: TestClient) -> None:
    assert search_all(client) == [s.id for s in all_signs_ordered()]


def test_paginacion_estable_sin_duplicados_ni_huecos(client: TestClient) -> None:
    total = len(all_signs_ordered())
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    seen: list[str] = []
    for page in range(1, pages + 1):
        body = search(client, page=page)
        assert body["page"] == page
        assert body["pageSize"] == PAGE_SIZE
        assert body["total"] == total
        items = slugs_of(body)
        expected_len = PAGE_SIZE if page < pages else total - PAGE_SIZE * (pages - 1)
        assert len(items) == expected_len
        seen += items
    assert len(seen) == len(set(seen)) == total
    # Pedir la misma página dos veces da lo mismo.
    assert slugs_of(search(client, page=2)) == slugs_of(search(client, page=2))


def test_pagina_posterior_a_la_ultima_devuelve_items_vacios(client: TestClient) -> None:
    total = len(all_signs_ordered())
    beyond = (total + PAGE_SIZE - 1) // PAGE_SIZE + 1
    body = search(client, page=beyond)
    assert body["items"] == []
    assert body["total"] == total


@pytest.mark.parametrize("page", ["0", "-1", "abc"])
def test_pagina_invalida_responde_422(client: TestClient, page: str) -> None:
    response = client.get(SIGNS_URL, params={"page": page})
    assert_error(response, 422, "VALIDATION_ERROR")


def test_q_de_80_caracteres_se_acepta(client: TestClient) -> None:
    body = search(client, q="a" * MAX_Q)
    assert body["items"] == []


def test_q_de_81_caracteres_responde_422(client: TestClient) -> None:
    response = client.get(SIGNS_URL, params={"q": "a" * (MAX_Q + 1)})
    assert_error(response, 422, "VALIDATION_ERROR")


# ================================================================ búsqueda: normalización


@pytest.mark.parametrize("q", ["GRACÍAS", "  gracias ", "Gracias", "gracias", "¡Gracias!"])
def test_gracias_se_encuentra_sin_importar_mayusculas_tildes_ni_signos(
    client: TestClient, q: str
) -> None:
    body = search(client, q=q)
    assert slugs_of(body) == ["gracias"]
    assert body["total"] == 1
    assert body["suggestions"] == []


def test_como_estas_con_signos_y_tildes_encuentra_la_sena(client: TestClient) -> None:
    assert "como-estas" in slugs_of(search(client, q="¿Cómo estás?"))


def test_busqueda_por_subcadena(client: TestClient) -> None:
    assert search_all(client, q="buen") == expected_slugs("buen")
    assert set(search_all(client, q="buen")) >= {"buenos-dias", "buenas-tardes", "buenas-noches"}


def test_busqueda_devuelve_lo_mismo_que_el_oraculo_en_todas_las_paginas(
    client: TestClient,
) -> None:
    for q in ["a", "o", "letra", "ma"]:
        assert search_all(client, q=q) == expected_slugs(q), q


def test_bano_con_n_no_encuentra_bano_con_enie(client: TestClient) -> None:
    """La ñ se conserva: «bano» no es «baño» (pero sí aparece como sugerencia)."""
    body = search(client, q="bano")
    assert body["items"] == []
    assert body["total"] == 0
    assert "bano" in [as_str(s["slug"]) for s in as_list(body["suggestions"])]


@pytest.mark.parametrize("q", ["baño", "BAÑO", "Baño"])
def test_bano_con_enie_encuentra_la_sena_bano(client: TestClient, q: str) -> None:
    assert slugs_of(search(client, q=q)) == ["bano"]


def test_enie_sola_encuentra_las_palabras_con_enie_y_no_la_n(client: TestClient) -> None:
    slugs = search_all(client, q="ñ")
    assert {"letra-n-tilde", "bano", "banarse"} <= set(slugs)
    assert "letra-n" not in slugs


def test_n_no_encuentra_la_letra_enie(client: TestClient) -> None:
    slugs = search_all(client, q="n")
    assert "letra-n" in slugs
    assert "letra-n-tilde" not in slugs


@pytest.mark.parametrize("q", ["%", "_", "\\", "a%", "%a", "a_a", "%%"])
def test_comodines_sql_se_tratan_como_literales(client: TestClient, q: str) -> None:
    body = search(client, q=q)
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.parametrize("q", ["", "   "])
def test_q_vacio_o_solo_espacios_devuelve_todas_las_senas(client: TestClient, q: str) -> None:
    body = search(client, q=q)
    assert body["total"] == len(all_signs_ordered())
    assert body["suggestions"] == []
    assert search_all(client, q=q) == [s.id for s in all_signs_ordered()]


# ================================================================ búsqueda: categoría


def test_filtro_por_categoria_animales(client: TestClient) -> None:
    slugs = search_all(client, category="animales")
    assert slugs == expected_slugs(category="animales")
    assert set(slugs) == {"perro", "gato", "pajaro", "vaca", "caballo", "pez"}
    for item in as_list(search(client, category="animales")["items"]):
        assert as_obj(item["category"])["id"] == "animales"


def test_filtro_por_categoria_y_texto_a_la_vez(client: TestClient) -> None:
    slugs = search_all(client, q="o", category="animales")
    assert slugs == expected_slugs("o", "animales")
    assert "pez" not in slugs
    assert "perro" in slugs


def test_filtro_de_categoria_es_exacto(client: TestClient) -> None:
    """«cortes» no es «cortesia»: el filtro compara el id completo."""
    body = search(client, category="cortes")
    assert body["items"] == []
    assert body["total"] == 0


def test_categoria_inexistente_devuelve_items_vacios(client: TestClient) -> None:
    body = search(client, category="no-existe")
    assert body["items"] == []
    assert body["total"] == 0
    assert body["suggestions"] == []


# ================================================================ sugerencias


def test_grasias_sugiere_gracias(client: TestClient) -> None:
    body = search(client, q="grasias")
    assert body["items"] == []
    assert body["total"] == 0
    suggestions = as_list(body["suggestions"])
    assert suggestions[0] == {"slug": "gracias", "word": "Gracias"}
    for s in suggestions:
        assert set(s) == SUGGESTION_KEYS
    assert [as_str(s["slug"]) for s in suggestions] == expected_suggestions("grasias")


def test_sugerencias_con_mayusculas_y_tildes_usan_el_termino_normalizado(
    client: TestClient,
) -> None:
    body = search(client, q="  GRÁSIAS ")
    assert body["items"] == []
    assert as_list(body["suggestions"])[0] == {"slug": "gracias", "word": "Gracias"}


def test_sugerencias_maximo_cinco_ordenadas_por_distancia(client: TestClient) -> None:
    # «x9» no está contenido en ninguna palabra; «x» (letra X) está a distancia 1 y muchas
    # palabras cortas (letras, «yo», «tu», «si», «no») a distancia 2.
    body = search(client, q="x9")
    assert body["items"] == []
    suggestions = as_list(body["suggestions"])
    assert len(suggestions) == MAX_SUGGESTIONS
    assert suggestions[0] == {"slug": "letra-x", "word": "X"}
    distances = [levenshtein("x9", normalize_text(as_str(s["word"]))) for s in suggestions]
    assert all(d <= 2 for d in distances)
    assert distances == sorted(distances)


def test_sin_palabras_cercanas_no_hay_sugerencias(client: TestClient) -> None:
    body = search(client, q="zzzzzzzzzz")
    assert body["items"] == []
    assert body["total"] == 0
    assert body["suggestions"] == []


def test_sugerencias_solo_hasta_distancia_dos(client: TestClient) -> None:
    # «graciasxyz» está a distancia 3 de «gracias»: no se sugiere.
    body = search(client, q="graciasxyz")
    assert body["items"] == []
    assert "gracias" not in [as_str(s["slug"]) for s in as_list(body["suggestions"])]


def test_con_resultados_no_hay_sugerencias(client: TestClient) -> None:
    body = search(client, q="gato")
    assert slugs_of(body) == ["gato"]
    assert body["suggestions"] == []


# ================================================================ ficha


def test_ficha_sin_token_tiene_la_forma_del_contrato(client: TestClient) -> None:
    body = get_detail(client, "gracias")
    assert set(body) == DETAIL_KEYS
    sign = sign_row("gracias")
    assert body["slug"] == "gracias"
    assert body["word"] == "Gracias"
    assert body["meaning"] == sign.meaning
    assert body["usageExample"] == sign.usage_example
    assert body["category"] == {"id": "cortesia", "name": "Cortesía"}
    assert body["video"] == expected_video(sign)
    assert body["isFavorite"] is False


def test_ficha_how_to_vacio_se_devuelve_null(client: TestClient) -> None:
    # En content/signs.csv `how_to` está vacío hasta que el intérprete lo describa.
    assert sign_row("gracias").how_to in (None, "")
    assert get_detail(client, "gracias")["howTo"] is None


def test_ficha_leccion_relacionada_sin_token_tiene_status_null(client: TestClient) -> None:
    sign = sign_row("gracias")
    assert sign.introduced_in_lesson_id is not None
    lesson = lesson_row(sign.introduced_in_lesson_id)
    related = as_obj(get_detail(client, "gracias")["relatedLesson"])
    assert set(related) == RELATED_LESSON_KEYS
    assert related == {"id": lesson.id, "title": lesson.title, "status": None}


def test_ficha_de_sena_de_m1_n1_l1_con_usuario_nuevo_esta_disponible(
    client: TestClient, token: str
) -> None:
    slug = sign_introduced_in("M1-N1-L1")
    related = as_obj(get_detail(client, slug, token)["relatedLesson"])
    assert related["id"] == "M1-N1-L1"
    assert related["status"] == "AVAILABLE"
    assert related["status"] == lesson_status_in_path(client, token, "M1-N1-L1")


def test_ficha_de_sena_de_un_nodo_posterior_esta_bloqueada(client: TestClient, token: str) -> None:
    slug = sign_introduced_in("M1-N2-L1")
    related = as_obj(get_detail(client, slug, token)["relatedLesson"])
    assert related["id"] == "M1-N2-L1"
    assert related["status"] == "LOCKED"


def test_ficha_status_sigue_la_ruta_tras_aprobar_la_leccion(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    complete_lesson(user_id, "M1-N1-L1", 100, True)
    slug_l1 = sign_introduced_in("M1-N1-L1")
    slug_l2 = sign_introduced_in("M1-N1-L2")
    status_l1 = as_obj(get_detail(client, slug_l1, token)["relatedLesson"])["status"]
    status_l2 = as_obj(get_detail(client, slug_l2, token)["relatedLesson"])["status"]
    assert status_l1 == lesson_status_in_path(client, token, "M1-N1-L1")
    assert status_l1 == "COMPLETED"
    assert status_l2 == lesson_status_in_path(client, token, "M1-N1-L2")
    assert status_l2 == "AVAILABLE"


@pytest.mark.parametrize("slug", ["con-permiso", "perro", "pez"])
def test_ficha_de_sena_solo_de_diccionario_no_tiene_leccion(
    client: TestClient, token: str, slug: str
) -> None:
    assert sign_row(slug).introduced_in_lesson_id is None
    assert get_detail(client, slug)["relatedLesson"] is None
    assert get_detail(client, slug, token)["relatedLesson"] is None


@pytest.mark.usefixtures("unpublished_m3")
def test_ficha_de_sena_de_modulo_no_publicado_no_tiene_leccion(
    client: TestClient, token: str
) -> None:
    sign = sign_row("agua")
    assert sign.introduced_in_lesson_id is not None
    with Session(get_engine()) as db:
        module_id = db.execute(
            select(Node.module_id)
            .join(Lesson, Lesson.node_id == Node.id)
            .where(Lesson.id == sign.introduced_in_lesson_id)
        ).scalar_one()
    assert module_id == "M3"
    assert get_detail(client, "agua")["relatedLesson"] is None
    assert get_detail(client, "agua", token)["relatedLesson"] is None


def test_ficha_de_sena_de_modulo_publicado_si_tiene_leccion(client: TestClient) -> None:
    sign = sign_row("agua")
    related = as_obj(get_detail(client, "agua")["relatedLesson"])
    assert related["id"] == sign.introduced_in_lesson_id


def test_ficha_con_enie_en_el_slug_codificado(client: TestClient) -> None:
    body = get_detail(client, "letra-n-tilde")
    assert body["word"] == "Ñ"
    assert body["category"] == {"id": "alfabeto", "name": category_row("alfabeto").name}


def test_ficha_inexistente_responde_404_sign_not_found(client: TestClient) -> None:
    assert_error(client.get(f"{SIGNS_URL}/no-existe"), 404, "SIGN_NOT_FOUND")


def test_ficha_inexistente_con_token_responde_404(client: TestClient, token: str) -> None:
    assert_error(client.get(f"{SIGNS_URL}/no-existe", headers=auth(token)), 404, "SIGN_NOT_FOUND")


# ================================================================ categorías


def test_categorias_publicas_con_conteo_y_orden(client: TestClient) -> None:
    response = client.get(CATEGORIES_URL)
    assert response.status_code == 200, response.text
    body = as_list(response.json())
    with Session(get_engine()) as db:
        rows = db.execute(
            select(Category.id, Category.name, func.count(Sign.id))
            .join(Sign, Sign.category_id == Category.id)
            .group_by(Category.id, Category.name, Category.order)
            .order_by(Category.order)
        ).all()
    assert body == [{"id": cid, "name": name, "count": count} for cid, name, count in rows]
    for item in body:
        assert set(item) == CATEGORY_KEYS


def test_categorias_conteos_conocidos(client: TestClient) -> None:
    body = as_list(client.get(CATEGORIES_URL).json())
    counts = {as_str(c["id"]): as_int(c["count"]) for c in body}
    assert counts["animales"] == 6
    assert counts["cortesia"] == 5  # gracias, por favor, de nada, perdón, con permiso
    assert counts["alfabeto"] == 27


def test_categorias_empiezan_por_saludos(client: TestClient) -> None:
    body = as_list(client.get(CATEGORIES_URL).json())
    assert [c["id"] for c in body][:4] == ["saludos", "presentaciones", "cortesia", "alfabeto"]


def test_categorias_omiten_las_que_no_tienen_senas(client: TestClient, empty_category: str) -> None:
    body = as_list(client.get(CATEGORIES_URL).json())
    assert empty_category not in [c["id"] for c in body]
    assert all(as_int(c["count"]) > 0 for c in body)


def test_categorias_con_token_igual_que_sin_token(client: TestClient, token: str) -> None:
    assert (
        client.get(CATEGORIES_URL, headers=auth(token)).json() == client.get(CATEGORIES_URL).json()
    )


# ================================================================ favoritos


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", FAVORITES_URL),
        ("POST", f"{FAVORITES_URL}/gracias"),
        ("DELETE", f"{FAVORITES_URL}/gracias"),
    ],
)
def test_favoritos_sin_token_401(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


def test_favoritos_con_token_invalido_401(client: TestClient) -> None:
    response = client.get(FAVORITES_URL, headers=auth("no-es-un-token"))
    assert response.status_code == 401


def test_favoritos_de_usuario_nuevo_estan_vacios(client: TestClient, token: str) -> None:
    assert get_favorites(client, token) == []


def test_agregar_favorito_responde_204_y_aparece_en_la_lista(
    client: TestClient, token: str
) -> None:
    response = client.post(f"{FAVORITES_URL}/gracias", headers=auth(token))
    assert response.status_code == 204, response.text
    assert response.content == b""
    favorites = get_favorites(client, token)
    assert favorites == [expected_item("gracias")]
    for item in favorites:
        assert set(item) == ITEM_KEYS


def test_agregar_favorito_dos_veces_deja_una_sola_fila(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    add_favorite(client, token, "gracias")
    clock.advance(minutes=1)
    add_favorite(client, token, "gracias")
    rows = favorite_rows(user_id)
    assert [r.sign_id for r in rows] == ["gracias"]
    assert [as_str(f["slug"]) for f in get_favorites(client, token)] == ["gracias"]


def test_created_at_del_favorito_lo_fija_el_reloj(
    client: TestClient, user: tuple[str, str], clock: FakeClock
) -> None:
    token, user_id = user
    clock.advance(minutes=3, seconds=7)
    moment = clock.now()
    assert moment != T0
    add_favorite(client, token, "hola")
    rows = favorite_rows(user_id)
    assert len(rows) == 1
    assert rows[0].created_at == moment


def test_favoritos_mas_recientes_primero(client: TestClient, token: str, clock: FakeClock) -> None:
    add_favorite(client, token, "hola")
    clock.advance(minutes=1)
    add_favorite(client, token, "perro")
    clock.advance(minutes=1)
    add_favorite(client, token, "gracias")
    assert [as_str(f["slug"]) for f in get_favorites(client, token)] == [
        "gracias",
        "perro",
        "hola",
    ]


def test_favoritos_con_la_misma_hora_se_ordenan_por_slug(client: TestClient, token: str) -> None:
    add_favorite(client, token, "perro")
    add_favorite(client, token, "gato")
    add_favorite(client, token, "vaca")
    assert [as_str(f["slug"]) for f in get_favorites(client, token)] == [
        "gato",
        "perro",
        "vaca",
    ]


def test_agregar_favorito_de_slug_inexistente_responde_404(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    response = client.post(f"{FAVORITES_URL}/no-existe", headers=auth(token))
    assert_error(response, 404, "SIGN_NOT_FOUND")
    assert favorite_rows(user_id) == []


def test_quitar_favorito_responde_204_y_desaparece(
    client: TestClient, user: tuple[str, str]
) -> None:
    token, user_id = user
    add_favorite(client, token, "gracias")
    add_favorite(client, token, "hola")
    response = client.delete(f"{FAVORITES_URL}/gracias", headers=auth(token))
    assert response.status_code == 204, response.text
    assert [as_str(f["slug"]) for f in get_favorites(client, token)] == ["hola"]
    assert [r.sign_id for r in favorite_rows(user_id)] == ["hola"]


def test_quitar_favorito_que_no_esta_responde_204(client: TestClient, token: str) -> None:
    remove_favorite(client, token, "gracias")
    add_favorite(client, token, "gracias")
    remove_favorite(client, token, "gracias")
    remove_favorite(client, token, "gracias")
    assert get_favorites(client, token) == []


def test_ficha_marca_is_favorite_solo_para_su_usuario(client: TestClient, token: str) -> None:
    other_token, _ = register_user(client, OTHER_EMAIL)
    add_favorite(client, token, "gracias")
    assert get_detail(client, "gracias", token)["isFavorite"] is True
    assert get_detail(client, "gracias", other_token)["isFavorite"] is False
    assert get_detail(client, "gracias")["isFavorite"] is False
    assert get_detail(client, "hola", token)["isFavorite"] is False


def test_ficha_is_favorite_vuelve_a_false_al_quitarlo(client: TestClient, token: str) -> None:
    add_favorite(client, token, "gracias")
    remove_favorite(client, token, "gracias")
    assert get_detail(client, "gracias", token)["isFavorite"] is False


def test_favoritos_de_un_usuario_no_se_ven_en_otro(client: TestClient, token: str) -> None:
    other_token, _ = register_user(client, OTHER_EMAIL)
    add_favorite(client, token, "gracias")
    add_favorite(client, other_token, "perro")
    assert [as_str(f["slug"]) for f in get_favorites(client, token)] == ["gracias"]
    assert [as_str(f["slug"]) for f in get_favorites(client, other_token)] == ["perro"]


def test_quitar_favorito_no_afecta_al_otro_usuario(client: TestClient, token: str) -> None:
    other_token, _ = register_user(client, OTHER_EMAIL)
    add_favorite(client, token, "gracias")
    add_favorite(client, other_token, "gracias")
    remove_favorite(client, token, "gracias")
    assert get_favorites(client, token) == []
    assert [as_str(f["slug"]) for f in get_favorites(client, other_token)] == ["gracias"]


def test_ficha_con_token_invalido_responde_401(client: TestClient) -> None:
    """D-015.2: sin cabecera es anónimo; un token inválido no se trata como anónimo."""
    response = client.get(
        "/api/dictionary/signs/gracias", headers={"Authorization": "Bearer no-es-un-token"}
    )
    assert response.status_code == 401
