"""Contenido de prueba realista (§6.1, §6.2, §6.5), sin E/S, reutilizable en grupos futuros.

- M1 publicado: M1-N1 (9 señas), M1-N2 (9), M1-N3 (A-M, ALPHABET), M1-N4 (N-Z con Ñ, ALPHABET).
- M2 publicado: M2-N1 Familia (7) y M2-N3 Números (10, NUMBERS).
- M4 no publicado: un nodo sin señas.
- 2 señas solo de diccionario.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Sequence

from app.domain.content.models import (
    ConversationSpec,
    ConversationTurnSpec,
    GeneratedContent,
    ModuleSpec,
    NodeConversations,
    NodeSpec,
    SignSpec,
)
from app.domain.content.review_builder import ReviewSign
from app.domain.enums import Motion, NodeKind
from app.domain.exercises.models import CatalogSign, Tokenize, VideoRef, dump_payload

# ---------- Señas por nodo (slug, palabra, categoría) -----------------------------------------

M1_N1_SIGNS: tuple[tuple[str, str, str], ...] = (
    ("hola", "Hola", "saludos"),
    ("buenos-dias", "Buenos días", "saludos"),
    ("buenas-tardes", "Buenas tardes", "saludos"),
    ("buenas-noches", "Buenas noches", "saludos"),
    ("como-estas", "¿Cómo estás?", "saludos"),
    ("adios", "Adiós", "saludos"),
    ("gracias", "Gracias", "cortesia"),
    ("por-favor", "Por favor", "cortesia"),
    ("de-nada", "De nada", "cortesia"),
)

M1_N2_SIGNS: tuple[tuple[str, str, str], ...] = (
    ("nombre", "Nombre", "presentaciones"),
    ("yo", "Yo", "presentaciones"),
    ("tu", "Tú", "presentaciones"),
    ("mucho-gusto", "Mucho gusto", "presentaciones"),
    ("sordo", "Sordo", "presentaciones"),
    ("oyente", "Oyente", "presentaciones"),
    ("si", "Sí", "presentaciones"),
    ("no", "No", "presentaciones"),
    ("perdon", "Perdón", "cortesia"),
)

M2_N1_SIGNS: tuple[tuple[str, str, str], ...] = (
    ("familia", "Familia", "familia"),
    ("mama", "Mamá", "familia"),
    ("papa", "Papá", "familia"),
    ("hermano", "Hermano", "familia"),
    ("hermana", "Hermana", "familia"),
    ("hijo", "Hijo", "familia"),
    ("abuelo", "Abuelo", "familia"),
)

_NUMBER_WORDS = ("Uno", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Siete", "Ocho", "Nueve", "Diez")
M2_N3_SIGNS: tuple[tuple[str, str, str], ...] = tuple(
    (f"numero-{i}", word, "numeros") for i, word in enumerate(_NUMBER_WORDS, start=1)
)

LETTERS_A_M: tuple[str, ...] = tuple("ABCDEFGHIJKLM")
LETTERS_N_Z: tuple[str, ...] = (
    "N",
    "Ñ",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
)
DYNAMIC_LETTERS: frozenset[str] = frozenset({"J", "Ñ", "Z"})

DICTIONARY_SIGNS: tuple[tuple[str, str, str], ...] = (
    ("con-permiso", "Con permiso", "cortesia"),
    ("perro", "Perro", "animales"),
)


def letter_slug(letter: str) -> str:
    """«A» → letra-a · «Ñ» → letra-n-tilde · «LL» → letra-ll."""
    if letter == "Ñ":
        return "letra-n-tilde"
    return f"letra-{letter.lower()}"


NODE_SIGN_IDS: dict[str, tuple[str, ...]] = {
    "M1-N1": tuple(s for s, _, _ in M1_N1_SIGNS),
    "M1-N2": tuple(s for s, _, _ in M1_N2_SIGNS),
    "M1-N3": tuple(letter_slug(c) for c in LETTERS_A_M),
    "M1-N4": tuple(letter_slug(c) for c in LETTERS_N_Z),
    "M2-N1": tuple(s for s, _, _ in M2_N1_SIGNS),
    "M2-N3": tuple(s for s, _, _ in M2_N3_SIGNS),
}

# Nodos con lecciones, en el orden global (módulo → nodo).
PUBLISHED_NODE_IDS: tuple[str, ...] = ("M1-N1", "M1-N2", "M1-N3", "M1-N4", "M2-N1", "M2-N3")
ALPHABET_NODE_IDS: frozenset[str] = frozenset({"M1-N3", "M1-N4"})
DICTIONARY_SIGN_IDS: tuple[str, ...] = tuple(s for s, _, _ in DICTIONARY_SIGNS)


def build_modules() -> tuple[ModuleSpec, ...]:
    return (
        ModuleSpec(
            id="M1",
            order=1,
            title="Fundamentos de la LSC",
            published=True,
            nodes=(
                NodeSpec(id="M1-N1", order=1, title="Saludos y cortesía", kind=NodeKind.STANDARD),
                NodeSpec(id="M1-N2", order=2, title="Presentaciones", kind=NodeKind.STANDARD),
                NodeSpec(id="M1-N3", order=3, title="Alfabeto A-M", kind=NodeKind.ALPHABET),
                NodeSpec(id="M1-N4", order=4, title="Alfabeto N-Z", kind=NodeKind.ALPHABET),
            ),
        ),
        ModuleSpec(
            id="M2",
            order=2,
            title="Personas y vida cotidiana",
            published=True,
            nodes=(
                NodeSpec(id="M2-N1", order=1, title="Familia", kind=NodeKind.STANDARD),
                NodeSpec(id="M2-N3", order=3, title="Números", kind=NodeKind.NUMBERS),
            ),
        ),
        ModuleSpec(
            id="M4",
            order=4,
            title="Primeras conversaciones",
            published=False,
            nodes=(
                NodeSpec(id="M4-N1", order=1, title="Preguntas frecuentes", kind=NodeKind.STANDARD),
            ),
        ),
    )


def _word_signs(node_id: str, rows: Sequence[tuple[str, str, str]]) -> list[SignSpec]:
    return [
        SignSpec(id=slug, word=word, category=category, node_id=node_id, order=i)
        for i, (slug, word, category) in enumerate(rows, start=1)
    ]


def letter_sign(letter: str, node_id: str, order: int) -> SignSpec:
    motion = Motion.DYNAMIC if letter in DYNAMIC_LETTERS else Motion.STATIC
    return SignSpec(
        id=letter_slug(letter),
        word=letter,
        category="alfabeto",
        node_id=node_id,
        order=order,
        motion=motion,
    )


def build_signs() -> tuple[SignSpec, ...]:
    signs: list[SignSpec] = []
    signs += _word_signs("M1-N1", M1_N1_SIGNS)
    signs += _word_signs("M1-N2", M1_N2_SIGNS)
    signs += [letter_sign(c, "M1-N3", i) for i, c in enumerate(LETTERS_A_M, start=1)]
    signs += [letter_sign(c, "M1-N4", i) for i, c in enumerate(LETTERS_N_Z, start=1)]
    signs += _word_signs("M2-N1", M2_N1_SIGNS)
    signs += _word_signs("M2-N3", M2_N3_SIGNS)
    signs += [
        SignSpec(id=slug, word=word, category=category, node_id=None, order=i)
        for i, (slug, word, category) in enumerate(DICTIONARY_SIGNS, start=1)
    ]
    return tuple(signs)


# ---------- Conversaciones y deletreo (§6.5) --------------------------------------------------


def turn(prompt: str, answer: str, *distractors: str) -> ConversationTurnSpec:
    return ConversationTurnSpec(prompt=prompt, answer=answer, distractors=tuple(distractors))


def conversation(*turns: ConversationTurnSpec) -> ConversationSpec:
    return ConversationSpec(turns=tuple(turns))


# M1-N1 (L1: hola, buenos-dias, buenas-tardes · L2: buenas-noches, como-estas, adios ·
# L3: gracias, por-favor, de-nada). La primera usa una seña de L3: no sirve para L2 pero sí para L3.
M1_N1_CONV_L3_ONLY = conversation(
    turn("gracias", "de-nada", "por-favor", "adios"),
    turn("hola", "buenos-dias", "adios", "buenas-noches"),
)
M1_N1_CONV_L2 = conversation(
    turn("hola", "buenos-dias", "adios", "buenas-noches"),
    turn("como-estas", "buenos-dias", "adios", "buenas-noches"),
)
M1_N1_CONV_3 = conversation(
    turn("hola", "buenos-dias", "adios", "gracias"),
    turn("como-estas", "buenos-dias", "buenas-noches", "de-nada"),
    turn("gracias", "de-nada", "por-favor", "adios"),
)

# M1-N2 (L1: nombre, yo, tu · L2: mucho-gusto, sordo, oyente · L3: si, no, perdon).
M1_N2_CONV_L2 = conversation(
    turn("hola", "mucho-gusto", "adios", "tu"),
    turn("nombre", "yo", "sordo", "oyente"),
)
M1_N2_CONV_3 = conversation(
    turn("nombre", "yo", "tu", "sordo"),
    turn("sordo", "si", "no", "oyente"),
    turn("gracias", "de-nada", "perdon", "adios"),
)

# M2-N1 (L1: familia, mama, papa · L2: hermano, hermana, hijo · L3: abuelo).
M2_N1_CONV_L2 = conversation(
    turn("familia", "mama", "papa", "hermano"),
    turn("hola", "familia", "adios", "hijo"),
)
M2_N1_CONV_3 = conversation(
    turn("familia", "papa", "mama", "abuelo"),
    turn("hermano", "hermana", "hijo", "abuelo"),
    turn("gracias", "de-nada", "por-favor", "adios"),
)

# M2-N3 (L1: 1-3 · L2: 4-6 · L3: 7-10).
M2_N3_CONV_L2 = conversation(
    turn("numero-1", "numero-2", "numero-3", "numero-4"),
    turn("numero-5", "numero-6", "numero-4", "numero-1"),
)
M2_N3_CONV_3 = conversation(
    turn("numero-7", "numero-8", "numero-9", "numero-10"),
    turn("numero-2", "numero-3", "numero-1", "numero-5"),
    turn("gracias", "de-nada", "adios", "hola"),
)

SPELLING_M1_N3: tuple[str, ...] = (
    "CADA", "BEBE", "HADA", "FE", "DEBE", "DIGA", "CAMA", "LIMA", "MALA", "DAME",
)  # fmt: skip
SPELLING_M1_N4: tuple[str, ...] = (
    "SOL", "LUNA", "NIDO", "OSO", "PAN", "NIÑO", "SAPO", "VASO", "TAXI", "ZAPATO",
)  # fmt: skip


def build_conversations() -> dict[str, NodeConversations]:
    return {
        "M1-N1": NodeConversations(conversations=(M1_N1_CONV_L3_ONLY, M1_N1_CONV_L2, M1_N1_CONV_3)),
        "M1-N2": NodeConversations(conversations=(M1_N2_CONV_L2, M1_N2_CONV_3)),
        "M1-N3": NodeConversations(spelling=SPELLING_M1_N3),
        "M1-N4": NodeConversations(spelling=SPELLING_M1_N4),
        "M2-N1": NodeConversations(conversations=(M2_N1_CONV_L2, M2_N1_CONV_3)),
        "M2-N3": NodeConversations(conversations=(M2_N3_CONV_L2, M2_N3_CONV_3)),
    }


# ---------- Catálogo, tokens y ayudas ---------------------------------------------------------


def video_for(slug: str) -> VideoRef:
    """Rutas por contenido (D19): nunca contienen el slug."""
    digest = hashlib.sha256(slug.encode("utf-8")).hexdigest()[:16]
    return VideoRef(src=f"/media/v/{digest}.mp4", poster=f"/media/p/{digest}.jpg")


def build_catalog(signs: Sequence[SignSpec] | None = None) -> dict[str, CatalogSign]:
    source = build_signs() if signs is None else signs
    catalog: dict[str, CatalogSign] = {}
    for i, sign in enumerate(source):
        how_to = None if i % 2 == 0 else f"Mueve la mano para decir «{sign.word}»."
        catalog[sign.id] = CatalogSign(
            id=sign.id,
            word=sign.word,
            how_to=how_to,
            usage_example=f"Ejemplo de uso: «{sign.word}».",
            video=video_for(sign.id),
        )
    return catalog


_TOKEN_KEY = hashlib.sha256(b"option-tokens:clave-de-pruebas").digest()


def fake_tokenize(session_id: str, exercise_id: str) -> Tokenize:
    """Equivalente de prueba de D20: HMAC-SHA256 truncado a 10 hex (nunca `hash()`)."""

    def tokenize(side: str, value: str) -> str:
        message = f"{session_id}:{exercise_id}:{side}:{value}".encode()
        return hmac.new(_TOKEN_KEY, message, hashlib.sha256).hexdigest()[:10]

    return tokenize


def all_slugs(signs: Sequence[SignSpec] | None = None) -> frozenset[str]:
    source = build_signs() if signs is None else signs
    return frozenset(s.id for s in source)


def build_review_signs(signs: Sequence[SignSpec] | None = None) -> tuple[ReviewSign, ...]:
    """Señas del fixture como ReviewSign (node_order = posición global; 0 = diccionario)."""
    source = build_signs() if signs is None else signs
    positions = {node_id: i for i, node_id in enumerate(PUBLISHED_NODE_IDS, start=1)}
    return tuple(
        ReviewSign(
            id=s.id,
            word=s.word,
            category=s.category,
            node_id=s.node_id,
            node_order=0 if s.node_id is None else positions.get(s.node_id, 0),
        )
        for s in source
    )


def serialize_content(content: GeneratedContent) -> str:
    """JSON estable del resultado del generador (para comparar entre procesos)."""
    data = {
        "lessons": [
            {
                "id": lesson.id,
                "nodeId": lesson.node_id,
                "order": lesson.order,
                "type": str(lesson.type),
                "title": lesson.title,
                "signIds": list(lesson.sign_ids),
            }
            for lesson in content.lessons
        ],
        "exercises": [
            {
                "id": ex.id,
                "lessonId": ex.lesson_id,
                "order": ex.order,
                "activity": ex.activity,
                "type": str(ex.type),
                "signId": ex.sign_id,
                "scored": ex.scored,
                "payload": dump_payload(ex.payload),
            }
            for ex in content.exercises
        ],
    }
    return json.dumps(data, sort_keys=True, ensure_ascii=True)
