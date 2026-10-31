"""Tarea 2.4 (carga) — `content/` a estructuras del dominio (§6.1, §6.2, §6.3, §6.5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.content.csv_reader import SignRow
from app.content.errors import ContentError
from app.content.loader import (
    CATEGORIES,
    ContentBundle,
    IntroSpec,
    load_content,
    load_conversations,
    load_curriculum,
    load_intro,
    to_sign_specs,
)
from app.domain.content.models import ConversationTurnSpec, SignSpec
from app.domain.enums import Motion, NodeKind
from tests.unit.content.real_content import CONTENT_DIR

STANDARD_PUBLISHED_NODES = (
    "M1-N1",
    "M1-N2",
    "M2-N1",
    "M2-N2",
    "M2-N3",
    "M2-N4",
    "M3-N1",
    "M3-N2",
    "M3-N3",
    "M3-N4",
)


# ---------- Categorías -------------------------------------------------------------------------


def test_categories_son_las_13_de_6_2_en_orden() -> None:
    assert CATEGORIES == (
        ("saludos", "Saludos"),
        ("presentaciones", "Presentaciones"),
        ("cortesia", "Cortesía"),
        ("alfabeto", "Alfabeto"),
        ("familia", "Familia"),
        ("emociones", "Emociones"),
        ("numeros", "Números"),
        ("actividades", "Actividades"),
        ("alimentos", "Alimentos"),
        ("lugares", "Lugares"),
        ("transporte", "Transporte y objetos"),
        ("necesidades", "Necesidades"),
        ("animales", "Animales"),
    )


# ---------- curriculum.json --------------------------------------------------------------------


def test_curriculum_real_tiene_4_modulos_y_m4_no_publicado() -> None:
    modules = load_curriculum(CONTENT_DIR / "curriculum.json")
    assert [m.spec.id for m in modules] == ["M1", "M2", "M3", "M4"]
    assert [m.spec.order for m in modules] == [1, 2, 3, 4]
    assert [m.spec.published for m in modules] == [True, True, True, False]
    assert modules[0].spec.title == "Fundamentos de la LSC"
    assert modules[0].description == "Saludos, cortesía, presentaciones y alfabeto manual."
    assert modules[3].spec.title == "Primeras conversaciones"
    assert all(len(m.spec.nodes) == 4 for m in modules)


def test_curriculum_real_nodos_con_su_tipo() -> None:
    modules = load_curriculum(CONTENT_DIR / "curriculum.json")
    nodes = {n.id: n for m in modules for n in m.spec.nodes}
    assert len(nodes) == 16
    assert nodes["M1-N1"].kind is NodeKind.STANDARD
    assert nodes["M1-N1"].title == "Saludos y cortesía"
    assert nodes["M1-N3"].kind is NodeKind.ALPHABET
    assert nodes["M1-N4"].kind is NodeKind.ALPHABET
    assert nodes["M2-N3"].kind is NodeKind.NUMBERS
    assert nodes["M2-N3"].order == 3
    assert nodes["M4-N4"].title == "Comprensión visual"
    kinds = [n.kind for n in nodes.values()]
    assert kinds.count(NodeKind.ALPHABET) == 2
    assert kinds.count(NodeKind.NUMBERS) == 1


def test_curriculum_json_invalido_es_content_error(tmp_path: Path) -> None:
    path = tmp_path / "curriculum.json"
    path.write_text('{"modules": [', encoding="utf-8")
    with pytest.raises(ContentError) as info:
        load_curriculum(path)
    assert "curriculum.json" in str(info.value)


def test_curriculum_incompleto_es_content_error(tmp_path: Path) -> None:
    data = {"modules": [{"id": "M1", "order": 1, "title": "Fundamentos", "published": True}]}
    path = tmp_path / "curriculum.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContentError):
        load_curriculum(path)


def test_curriculum_con_tipo_de_nodo_desconocido_es_content_error(tmp_path: Path) -> None:
    data = {
        "modules": [
            {
                "id": "M1",
                "order": 1,
                "title": "Fundamentos",
                "description": "Saludos.",
                "published": True,
                "nodes": [{"id": "M1-N1", "order": 1, "title": "Saludos", "kind": "VIDEO"}],
            }
        ]
    }
    path = tmp_path / "curriculum.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContentError) as info:
        load_curriculum(path)
    assert "M1-N1" in str(info.value)


# ---------- conversations.yaml -----------------------------------------------------------------


def test_conversaciones_reales_alfabeto_solo_con_deletreo() -> None:
    conversations = load_conversations(CONTENT_DIR / "conversations.yaml")
    m1n3 = conversations["M1-N3"]
    assert m1n3.conversations == ()
    assert m1n3.spelling == (
        "CADA", "BEBE", "HADA", "FE", "DEBE", "DIGA", "CAMA", "LIMA", "MALA", "DAME",
    )  # fmt: skip
    m1n4 = conversations["M1-N4"]
    assert m1n4.conversations == ()
    assert m1n4.spelling == (
        "SOL", "LUNA", "NIDO", "OSO", "PAN", "NIÑO", "SAPO", "VASO", "TAXI", "ZAPATO",
    )  # fmt: skip


def test_conversaciones_reales_nodos_standard_y_numbers() -> None:
    conversations = load_conversations(CONTENT_DIR / "conversations.yaml")
    assert set(conversations) == {"M1-N3", "M1-N4", *STANDARD_PUBLISHED_NODES}
    for node_id in STANDARD_PUBLISHED_NODES:
        node = conversations[node_id]
        assert node.spelling == (), node_id
        assert len(node.conversations) >= 2, node_id
        assert any(len(c.turns) == 3 for c in node.conversations), node_id


def test_conversacion_real_de_m1_n1_se_lee_completa() -> None:
    first = load_conversations(CONTENT_DIR / "conversations.yaml")["M1-N1"].conversations[0]
    assert first.turns == (
        ConversationTurnSpec(
            prompt="hola", answer="buenos-dias", distractors=("adios", "buenas-noches")
        ),
        ConversationTurnSpec(
            prompt="adios", answer="buenas-noches", distractors=("hola", "como-estas")
        ),
    )


@pytest.mark.parametrize("text", ["", "\n", "# solo un comentario\n"])
def test_yaml_vacio_da_diccionario_vacio(tmp_path: Path, text: str) -> None:
    path = tmp_path / "conversations.yaml"
    path.write_text(text, encoding="utf-8")
    assert load_conversations(path) == {}


def test_yaml_inexistente_da_diccionario_vacio(tmp_path: Path) -> None:
    assert load_conversations(tmp_path / "no-existe.yaml") == {}


@pytest.mark.parametrize(
    "text",
    [
        "M1-N1:\n  - turns: hola\n",
        "M1-N1:\n  - turns:\n      - prompt: hola\n        distractors: [adios]\n",
        "M1-N1:\n  - turns:\n      - prompt: hola\n        answer: adios\n        distractors: x\n",
        "M1-N1: 42\n",
        "M1-N1:\n  spelling: CADA\n",
    ],
)
def test_estructura_invalida_nombra_el_nodo(tmp_path: Path, text: str) -> None:
    path = tmp_path / "conversations.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ContentError) as info:
        load_conversations(path)
    assert "M1-N1" in str(info.value)


def test_yaml_que_no_es_un_mapa_es_content_error(tmp_path: Path) -> None:
    path = tmp_path / "conversations.yaml"
    path.write_text("- M1-N1\n- M1-N2\n", encoding="utf-8")
    with pytest.raises(ContentError):
        load_conversations(path)


def test_yaml_con_sintaxis_rota_es_content_error(tmp_path: Path) -> None:
    path = tmp_path / "conversations.yaml"
    path.write_text("M1-N1:\n  - turns: [\n", encoding="utf-8")
    with pytest.raises(ContentError):
        load_conversations(path)


def test_yaml_no_ejecuta_etiquetas_de_python(tmp_path: Path) -> None:
    """`yaml.safe_load`: una etiqueta `!!python/object` no se ejecuta, se rechaza."""
    path = tmp_path / "conversations.yaml"
    path.write_text("M1-N1: !!python/object/apply:os.system ['echo hola']\n", encoding="utf-8")
    with pytest.raises(ContentError):
        load_conversations(path)


# ---------- intro.json -------------------------------------------------------------------------


def test_intro_real() -> None:
    intro = load_intro(CONTENT_DIR / "intro.json")
    assert intro == IntroSpec(
        cards=("hola", "gracias", "por-favor", "si", "no", "adios"),
        quiz=("gracias", "hola", "no"),
    )


def test_intro_invalido_es_content_error(tmp_path: Path) -> None:
    path = tmp_path / "intro.json"
    path.write_text('{"cards": ["hola"]}', encoding="utf-8")
    with pytest.raises(ContentError):
        load_intro(path)


# ---------- to_sign_specs ----------------------------------------------------------------------


def _row(slug: str, motion: str | None, node: str | None = "M1-N3", order: int = 1) -> SignRow:
    return SignRow(
        slug=slug,
        word=slug.upper(),
        meaning="Significado.",
        how_to=None,
        usage_example="Ejemplo.",
        category="alfabeto",
        node=node,
        order=order,
        motion=motion,
        line=2,
    )


def test_to_sign_specs_convierte_motion_y_campos() -> None:
    rows = [
        _row("letra-a", "static", order=1),
        _row("letra-j", "dynamic", order=10),
        _row("letra-k", None, order=11),
        _row("letra-l", "moving", order=12),
        _row("perro", None, node=None, order=0),
    ]
    specs = to_sign_specs(rows)
    assert specs == [
        SignSpec(
            id="letra-a",
            word="LETRA-A",
            category="alfabeto",
            node_id="M1-N3",
            order=1,
            motion=Motion.STATIC,
        ),
        SignSpec(
            id="letra-j",
            word="LETRA-J",
            category="alfabeto",
            node_id="M1-N3",
            order=10,
            motion=Motion.DYNAMIC,
        ),
        SignSpec(id="letra-k", word="LETRA-K", category="alfabeto", node_id="M1-N3", order=11),
        SignSpec(id="letra-l", word="LETRA-L", category="alfabeto", node_id="M1-N3", order=12),
        SignSpec(id="perro", word="PERRO", category="alfabeto", node_id=None, order=0),
    ]


# ---------- load_content -----------------------------------------------------------------------


def test_load_content_del_directorio_real() -> None:
    bundle = load_content(CONTENT_DIR)
    assert isinstance(bundle, ContentBundle)
    assert [m.spec.id for m in bundle.modules] == ["M1", "M2", "M3", "M4"]
    assert len(bundle.signs) == 109
    assert len({s.slug for s in bundle.signs}) == 109
    assert sum(1 for s in bundle.signs if s.category == "alfabeto") == 27
    assert sum(1 for s in bundle.signs if s.node is None) == 7
    assert "M1-N1" in bundle.conversations
    assert bundle.intro.quiz == ("gracias", "hola", "no")
    specs = {s.id: s for s in to_sign_specs(bundle.signs)}
    assert specs["letra-j"].motion is Motion.DYNAMIC
    assert specs["letra-n-tilde"].motion is Motion.DYNAMIC
    assert specs["letra-z"].motion is Motion.DYNAMIC
    assert specs["letra-a"].motion is Motion.STATIC
    assert specs["hola"].motion is None


def test_load_content_sin_conversaciones_da_diccionario_vacio(tmp_path: Path) -> None:
    for name in ("curriculum.json", "signs.csv", "intro.json"):
        (tmp_path / name).write_bytes((CONTENT_DIR / name).read_bytes())
    bundle = load_content(tmp_path)
    assert bundle.conversations == {}


def test_load_content_con_csv_faltante_es_content_error(tmp_path: Path) -> None:
    for name in ("curriculum.json", "conversations.yaml", "intro.json"):
        (tmp_path / name).write_bytes((CONTENT_DIR / name).read_bytes())
    with pytest.raises(ContentError) as info:
        load_content(tmp_path)
    assert "signs.csv" in str(info.value)
