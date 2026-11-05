"""Contenido REAL con el generador (pendiente del Grupo 1): R9.8, R9.9, §6.6, §6.7, D-008, D20.

loader → to_sign_specs → generate_content con `content/` tal como está en el repositorio.
"""

from __future__ import annotations

from collections import Counter
from functools import cache

from app.content.loader import ContentBundle, load_content, to_sign_specs
from app.domain.content.generator import generate_content
from app.domain.content.models import GeneratedContent, SignSpec
from app.domain.enums import ExerciseType, NodeKind
from app.domain.exercises.evaluators import get_evaluator
from app.domain.exercises.models import (
    PublicConversation,
    SignCatalog,
    SpellingPayload,
)
from tests.unit.content.real_content import CONTENT_DIR
from tests.unit.domain.content_fixture import build_catalog, fake_tokenize, serialize_content

FORBIDDEN_KEYS = frozenset(
    {"correctId", "signId", "optionIds", "signIds", "promptId", "letterIds", "optionWords"}
)
PUBLISHED_MODULES = ("M1", "M2", "M3")


@cache
def _bundle() -> ContentBundle:
    return load_content(CONTENT_DIR)


@cache
def _signs() -> tuple[SignSpec, ...]:
    return tuple(to_sign_specs(_bundle().signs))


@cache
def _generated() -> GeneratedContent:
    bundle = _bundle()
    return generate_content([m.spec for m in bundle.modules], _signs(), bundle.conversations)


def _catalog() -> SignCatalog:
    return build_catalog(_signs())


def _walk(value: object) -> tuple[list[str], list[str]]:
    """Todas las claves y todos los valores de texto de un JSON."""
    keys: list[str] = []
    strings: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            keys.append(str(k))
            sub_keys, sub_strings = _walk(v)
            keys += sub_keys
            strings += sub_strings
    elif isinstance(value, list):
        for item in value:
            sub_keys, sub_strings = _walk(item)
            keys += sub_keys
            strings += sub_strings
    elif isinstance(value, str):
        strings.append(value)
    return keys, strings


def test_contenido_real_tiene_109_senas() -> None:
    assert len(_signs()) == 109
    assert len({s.id for s in _signs()}) == 109


def test_todos_los_nodos_publicados_tienen_4_lecciones() -> None:
    bundle = _bundle()
    published = [n.id for m in bundle.modules if m.spec.published for n in m.spec.nodes]
    assert len(published) == 12
    lessons = _generated().lessons
    per_node = Counter(lesson.node_id for lesson in lessons)
    assert per_node == dict.fromkeys(published, 4)
    assert len(lessons) == 48
    for node_id in published:
        ids = [lesson.id for lesson in lessons if lesson.node_id == node_id]
        assert ids == [f"{node_id}-L{i}" for i in range(1, 5)]


def test_m4_no_publicado_no_genera_lecciones() -> None:
    generated = _generated()
    assert not [lesson for lesson in generated.lessons if lesson.id.startswith("M4")]
    assert not [ex for ex in generated.exercises if ex.lesson_id.startswith("M4")]


def test_cada_leccion_tiene_al_menos_4_ejercicios_con_puntaje() -> None:
    scored = Counter(ex.lesson_id for ex in _generated().exercises if ex.scored)
    for lesson in _generated().lessons:
        assert scored[lesson.id] >= 4, (lesson.id, scored[lesson.id])


def test_ids_de_ejercicios_estables_y_unicos() -> None:
    exercises = _generated().exercises
    ids = [ex.id for ex in exercises]
    assert len(ids) == len(set(ids))
    for ex in exercises:
        assert ex.id == f"{ex.lesson_id}-{ex.order:02d}"


def test_generacion_determinista_con_el_contenido_real() -> None:
    bundle = _bundle()
    again = generate_content(
        [m.spec for m in bundle.modules],
        to_sign_specs(load_content(CONTENT_DIR).signs),
        bundle.conversations,
    )
    assert serialize_content(again) == serialize_content(_generated())


def test_alfabeto_usa_deletreo_y_el_resto_conversaciones() -> None:
    bundle = _bundle()
    kinds = {n.id: n.kind for m in bundle.modules for n in m.spec.nodes}
    by_lesson: dict[str, set[ExerciseType]] = {}
    for ex in _generated().exercises:
        by_lesson.setdefault(ex.lesson_id, set()).add(ex.type)
    for lesson in _generated().lessons:
        if lesson.order == 1:
            continue
        types = by_lesson[lesson.id]
        if kinds[lesson.node_id] is NodeKind.ALPHABET:
            assert ExerciseType.SPELLING in types, lesson.id
            assert ExerciseType.CONVERSATION not in types, lesson.id
        else:
            assert ExerciseType.CONVERSATION in types, lesson.id
            assert ExerciseType.SPELLING not in types, lesson.id


def test_deletreo_solo_con_letras_ya_ensenadas() -> None:
    """R9.9: cada palabra usa letras enseñadas en esa lección o antes (incluidos nodos previos)."""
    taught: set[str] = set()
    taught_by_lesson: dict[str, frozenset[str]] = {}
    for lesson in _generated().lessons:
        if lesson.order <= 3:
            taught |= set(lesson.sign_ids)
        taught_by_lesson[lesson.id] = frozenset(taught)
    spelling = [ex for ex in _generated().exercises if ex.type is ExerciseType.SPELLING]
    assert spelling
    for ex in spelling:
        payload = ex.payload
        assert isinstance(payload, SpellingPayload)
        assert payload.word == payload.word.upper()
        assert set(payload.letter_ids) <= taught_by_lesson[ex.lesson_id], ex.id


def test_vista_publica_no_filtra_respuestas_ni_slugs() -> None:
    catalog = _catalog()
    slugs = {s.id for s in _signs()}
    for ex in _generated().exercises:
        public = get_evaluator(ex.type).to_public(
            ex.payload, catalog, fake_tokenize("sesion-de-prueba", ex.id)
        )
        dumped = public.model_dump(mode="json", by_alias=True)
        for field in ("cameraLabel", "gestureLabel"):
            if field in dumped:
                # D-007.8 / D-026: la etiqueta de los modelos de cámara es el slug de la seña; solo
                # existe en PRODUCE, que ya muestra la palabra y no tiene opciones que adivinar.
                assert ex.type is ExerciseType.PRODUCE, ex.id
                dumped.pop(field)
        keys, strings = _walk(dumped)
        assert not FORBIDDEN_KEYS & set(keys), (ex.id, FORBIDDEN_KEYS & set(keys))
        leaked = [s for s in strings if s in slugs]
        assert not leaked, (ex.id, leaked)
        assert all(not any(f"/{slug}." in s for slug in slugs) for s in strings), ex.id


def test_ningun_estimulo_de_conversacion_coincide_con_una_opcion() -> None:
    """D-008: el video del estímulo nunca es el de una opción (B54)."""
    catalog = _catalog()
    conversations = [ex for ex in _generated().exercises if ex.type is ExerciseType.CONVERSATION]
    assert conversations
    for ex in conversations:
        public = get_evaluator(ex.type).to_public(
            ex.payload, catalog, fake_tokenize("sesion-de-prueba", ex.id)
        )
        assert isinstance(public, PublicConversation)
        for turn in public.turns:
            assert turn.prompt.src not in {o.video.src for o in turn.options}, ex.id
