"""Tarea 1.5 — desbloqueo derivado de lecciones, nodos y módulos (§7.4, D3, R3.2-3.7)."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

import pytest

from app.domain.enums import LessonType, ProgressStatus
from app.domain.policies.progress import (
    CurriculumLesson,
    CurriculumModule,
    CurriculumNode,
    ProgressFacts,
    ProgressMap,
    compute_progress,
)

LOCKED = ProgressStatus.LOCKED
AVAILABLE = ProgressStatus.AVAILABLE
IN_PROGRESS = ProgressStatus.IN_PROGRESS
COMPLETED = ProgressStatus.COMPLETED
GOLDEN = ProgressStatus.GOLDEN
COMING_SOON = ProgressStatus.COMING_SOON

LESSON_TYPES = (
    LessonType.LEARN,
    LessonType.RECOGNIZE,
    LessonType.PRACTICE,
    LessonType.CHALLENGE,
)


# --- helpers del currículo de prueba -----------------------------------------------------------


def make_node(node_id: str, order: int, *, reverse_lessons: bool = False) -> CurriculumNode:
    lessons = tuple(
        CurriculumLesson(id=f"{node_id}-L{i}", order=i, type=LESSON_TYPES[i - 1])
        for i in range(1, 5)
    )
    if reverse_lessons:
        lessons = tuple(reversed(lessons))
    return CurriculumNode(id=node_id, order=order, lessons=lessons)


def make_module(
    module_id: str,
    order: int,
    n_nodes: int,
    *,
    published: bool = True,
    reverse: bool = False,
) -> CurriculumModule:
    nodes = tuple(
        make_node(f"{module_id}-N{i}", i, reverse_lessons=reverse) for i in range(1, n_nodes + 1)
    )
    if reverse:
        nodes = tuple(reversed(nodes))
    return CurriculumModule(id=module_id, order=order, published=published, nodes=nodes)


def lesson_ids(module_id: str, n_nodes: int) -> list[str]:
    return [f"{module_id}-N{n}-L{i}" for n in range(1, n_nodes + 1) for i in range(1, 5)]


def node_lessons(node_id: str) -> list[str]:
    return [f"{node_id}-L{i}" for i in range(1, 5)]


def facts(
    passed: Collection[str] = (), best_scores: Mapping[str, int] | None = None
) -> ProgressFacts:
    scores: dict[str, int] = {lesson: 80 for lesson in passed}
    if best_scores is not None:
        scores.update(best_scores)
    return ProgressFacts(best_scores=scores, passed=frozenset(passed))


def curriculum() -> list[CurriculumModule]:
    """M1 (4 nodos, como el contenido real) y M2 (2 nodos), ambos publicados."""
    return [make_module("M1", 1, 4), make_module("M2", 2, 2)]


def run(modules: Sequence[CurriculumModule], progress_facts: ProgressFacts) -> ProgressMap:
    return compute_progress(modules, progress_facts)


# --- casos obligatorios de §7.4 ----------------------------------------------------------------


def test_usuario_nuevo_solo_tiene_disponible_m1_n1_l1() -> None:
    result = run(curriculum(), facts())

    assert result.lessons["M1-N1-L1"] is AVAILABLE
    available = [lid for lid, status in result.lessons.items() if status is not LOCKED]
    assert available == ["M1-N1-L1"]
    assert set(result.lessons) == set(lesson_ids("M1", 4) + lesson_ids("M2", 2))


def test_usuario_nuevo_estado_de_nodos_y_modulos() -> None:
    result = run(curriculum(), facts())

    assert result.nodes == {
        "M1-N1": IN_PROGRESS,
        "M1-N2": LOCKED,
        "M1-N3": LOCKED,
        "M1-N4": LOCKED,
        "M2-N1": LOCKED,
        "M2-N2": LOCKED,
    }
    assert result.modules == {"M1": IN_PROGRESS, "M2": LOCKED}


def test_aprobar_l4_de_m1_n4_desbloquea_m2_n1_l1() -> None:
    before = run(curriculum(), facts(passed=lesson_ids("M1", 4)[:-1]))
    assert before.lessons["M1-N4-L4"] is AVAILABLE
    assert before.lessons["M2-N1-L1"] is LOCKED
    assert before.modules["M2"] is LOCKED

    after = run(curriculum(), facts(passed=lesson_ids("M1", 4)))
    assert after.lessons["M1-N4-L4"] is COMPLETED
    assert after.lessons["M2-N1-L1"] is AVAILABLE
    assert after.lessons["M2-N1-L2"] is LOCKED
    assert after.nodes["M1-N4"] is COMPLETED
    assert after.nodes["M2-N1"] is IN_PROGRESS
    assert after.modules["M1"] is COMPLETED
    assert after.modules["M2"] is IN_PROGRESS


def test_agregar_un_modulo_nuevo_no_cambia_el_estado_de_lo_aprobado() -> None:
    passed = lesson_ids("M1", 4) + node_lessons("M2-N1")
    before = run(curriculum(), facts(passed=passed))

    extended = [*curriculum(), make_module("M3", 3, 2)]
    after = run(extended, facts(passed=passed))

    for lesson_id, status in before.lessons.items():
        assert after.lessons[lesson_id] is status
    for node_id, status in before.nodes.items():
        assert after.nodes[node_id] is status
    for module_id, status in before.modules.items():
        assert after.modules[module_id] is status
    assert after.lessons["M3-N1-L1"] is LOCKED
    assert after.modules["M3"] is LOCKED


def test_agregar_un_modulo_intermedio_no_quita_lo_ya_aprobado() -> None:
    # El contenido nuevo se intercala antes de M2: lo aprobado en M2 sigue COMPLETED.
    passed = lesson_ids("M1", 4) + node_lessons("M2-N1")
    modules = [
        make_module("M1", 1, 4),
        make_module("MX", 2, 1),
        make_module("M2", 3, 2),
    ]
    result = run(modules, facts(passed=passed))

    for lesson_id in passed:
        assert result.lessons[lesson_id] is COMPLETED
    assert result.nodes["M2-N1"] is COMPLETED
    assert result.lessons["MX-N1-L1"] is AVAILABLE


def test_agregar_un_modulo_despues_de_terminar_todo_lo_desbloquea() -> None:
    passed = lesson_ids("M1", 4) + lesson_ids("M2", 2)
    before = run(curriculum(), facts(passed=passed))
    assert before.modules == {"M1": COMPLETED, "M2": COMPLETED}

    after = run([*curriculum(), make_module("M3", 3, 1)], facts(passed=passed))
    assert after.lessons["M3-N1-L1"] is AVAILABLE
    assert after.modules["M3"] is IN_PROGRESS
    assert after.modules["M2"] is COMPLETED


def test_reprobar_no_desbloquea() -> None:
    result = run(curriculum(), facts(best_scores={"M1-N1-L1": 40}))

    assert result.lessons["M1-N1-L1"] is AVAILABLE
    assert result.lessons["M1-N1-L2"] is LOCKED


def test_reprobar_el_reto_no_desbloquea_el_siguiente_nodo() -> None:
    passed = node_lessons("M1-N1")[:3]
    result = run(curriculum(), facts(passed=passed, best_scores={"M1-N1-L4": 60}))

    assert result.lessons["M1-N1-L4"] is AVAILABLE
    assert result.nodes["M1-N1"] is IN_PROGRESS
    assert result.lessons["M1-N2-L1"] is LOCKED
    assert result.nodes["M1-N2"] is LOCKED


# --- cadena de desbloqueo ----------------------------------------------------------------------


def test_aprobar_cada_leccion_desbloquea_solo_la_siguiente() -> None:
    order = lesson_ids("M1", 4) + lesson_ids("M2", 2)
    for k in range(len(order)):
        result = run(curriculum(), facts(passed=order[:k]))
        for i, lesson_id in enumerate(order):
            expected = COMPLETED if i < k else AVAILABLE if i == k else LOCKED
            assert result.lessons[lesson_id] is expected, (k, lesson_id)


def test_aprobar_l4_de_un_nodo_desbloquea_l1_del_siguiente_nodo() -> None:
    result = run(curriculum(), facts(passed=node_lessons("M1-N1")))

    assert result.nodes["M1-N1"] is COMPLETED
    assert result.lessons["M1-N2-L1"] is AVAILABLE
    assert result.nodes["M1-N2"] is IN_PROGRESS
    assert result.nodes["M1-N3"] is LOCKED
    assert result.modules["M1"] is IN_PROGRESS


def test_nodo_en_progreso_con_algunas_lecciones_aprobadas() -> None:
    result = run(curriculum(), facts(passed=["M1-N1-L1", "M1-N1-L2"]))

    assert result.lessons["M1-N1-L3"] is AVAILABLE
    assert result.nodes["M1-N1"] is IN_PROGRESS


# --- dorado ------------------------------------------------------------------------------------


def test_reto_aprobado_con_100_es_dorado() -> None:
    passed = node_lessons("M1-N1")
    result = run(curriculum(), facts(passed=passed, best_scores={"M1-N1-L4": 100}))

    assert result.lessons["M1-N1-L4"] is GOLDEN
    assert result.nodes["M1-N1"] is GOLDEN
    assert result.lessons["M1-N2-L1"] is AVAILABLE


def test_reto_aprobado_con_menos_de_100_es_completado() -> None:
    passed = node_lessons("M1-N1")
    result = run(curriculum(), facts(passed=passed, best_scores={"M1-N1-L4": 99}))

    assert result.lessons["M1-N1-L4"] is COMPLETED
    assert result.nodes["M1-N1"] is COMPLETED


def test_leccion_normal_con_100_no_es_dorada() -> None:
    result = run(curriculum(), facts(passed=["M1-N1-L1"], best_scores={"M1-N1-L1": 100}))

    assert result.lessons["M1-N1-L1"] is COMPLETED


def test_modulo_completado_con_nodos_dorados_y_completados() -> None:
    passed = lesson_ids("M1", 4)
    golden = {"M1-N1-L4": 100, "M1-N3-L4": 100}
    result = run(curriculum(), facts(passed=passed, best_scores=golden))

    assert result.nodes["M1-N1"] is GOLDEN
    assert result.nodes["M1-N2"] is COMPLETED
    assert result.nodes["M1-N3"] is GOLDEN
    assert result.nodes["M1-N4"] is COMPLETED
    assert result.modules["M1"] is COMPLETED


def test_modulo_no_completado_si_falta_un_nodo() -> None:
    passed = lesson_ids("M1", 3)
    result = run(curriculum(), facts(passed=passed))

    assert result.nodes["M1-N4"] is IN_PROGRESS
    assert result.modules["M1"] is IN_PROGRESS


# --- módulos no publicados ---------------------------------------------------------------------


def test_modulo_no_publicado_es_proximamente_y_no_expone_lecciones() -> None:
    modules = [make_module("M1", 1, 4), make_module("M2", 2, 2, published=False)]
    result = run(modules, facts())

    assert result.modules["M2"] is COMING_SOON
    assert result.nodes["M2-N1"] is COMING_SOON
    assert result.nodes["M2-N2"] is COMING_SOON
    assert set(result.lessons) == set(lesson_ids("M1", 4))


def test_modulo_no_publicado_no_bloquea_al_siguiente_publicado() -> None:
    modules = [
        make_module("M1", 1, 4),
        make_module("M2", 2, 2, published=False),
        make_module("M3", 3, 1),
    ]
    before = run(modules, facts(passed=lesson_ids("M1", 4)[:-1]))
    assert before.lessons["M3-N1-L1"] is LOCKED
    assert before.modules["M3"] is LOCKED

    after = run(modules, facts(passed=lesson_ids("M1", 4)))
    assert after.lessons["M3-N1-L1"] is AVAILABLE
    assert after.nodes["M3-N1"] is IN_PROGRESS
    assert after.modules["M3"] is IN_PROGRESS
    assert after.modules["M2"] is COMING_SOON


def test_primer_modulo_no_publicado_deja_disponible_el_primer_publicado() -> None:
    modules = [make_module("M0", 1, 1, published=False), make_module("M1", 2, 4)]
    result = run(modules, facts())

    assert result.lessons["M1-N1-L1"] is AVAILABLE
    assert result.modules["M0"] is COMING_SOON


def test_aprobaciones_en_modulo_no_publicado_se_ignoran() -> None:
    modules = [make_module("M1", 1, 1), make_module("M2", 2, 1, published=False)]
    result = run(modules, facts(passed=node_lessons("M2-N1")))

    assert "M2-N1-L1" not in result.lessons
    assert result.nodes["M2-N1"] is COMING_SOON
    assert result.modules["M2"] is COMING_SOON


# --- orden de la entrada -----------------------------------------------------------------------


def test_ordena_por_order_aunque_la_entrada_venga_desordenada() -> None:
    passed = [*lesson_ids("M1", 4), "M2-N1-L1"]
    ordered = run(curriculum(), facts(passed=passed))

    shuffled_modules = [
        make_module("M2", 2, 2, reverse=True),
        make_module("M1", 1, 4, reverse=True),
    ]
    shuffled = run(shuffled_modules, facts(passed=passed))

    assert dict(shuffled.lessons) == dict(ordered.lessons)
    assert dict(shuffled.nodes) == dict(ordered.nodes)
    assert dict(shuffled.modules) == dict(ordered.modules)
    assert shuffled.lessons["M2-N1-L2"] is AVAILABLE


def test_usuario_nuevo_con_entrada_desordenada() -> None:
    shuffled_modules = [
        make_module("M2", 2, 2, reverse=True),
        make_module("M1", 1, 4, reverse=True),
    ]
    result = run(shuffled_modules, facts())

    available = [lid for lid, status in result.lessons.items() if status is not LOCKED]
    assert available == ["M1-N1-L1"]


def test_order_manda_sobre_el_id() -> None:
    # "B" tiene order 1 y va primero aunque su id sea mayor.
    modules = [make_module("A", 2, 1), make_module("B", 1, 1)]
    result = run(modules, facts())

    assert result.lessons["B-N1-L1"] is AVAILABLE
    assert result.lessons["A-N1-L1"] is LOCKED
    assert result.modules["A"] is LOCKED


def test_curriculo_vacio() -> None:
    result = run([], facts())

    assert dict(result.lessons) == {}
    assert dict(result.nodes) == {}
    assert dict(result.modules) == {}


def test_es_pura_y_no_modifica_la_entrada() -> None:
    modules = curriculum()
    progress_facts = facts(passed=["M1-N1-L1"])
    first = run(modules, progress_facts)
    second = run(modules, progress_facts)

    assert dict(first.lessons) == dict(second.lessons)
    assert modules == curriculum()


# ---------- % de avance de un módulo (revisión del Grupo 4) -----------------------------------


@pytest.mark.parametrize(
    ("approved", "total", "expected"),
    [(0, 16, 0), (1, 16, 6), (2, 16, 13), (4, 16, 25), (16, 16, 100), (0, 0, 0)],
)
def test_module_progress_percent(approved: int, total: int, expected: int) -> None:
    from app.domain.policies.progress import module_progress_percent

    lesson_ids = [f"L{i}" for i in range(total)]
    passed = set(lesson_ids[:approved]) | {"OTRA-LECCION"}
    assert module_progress_percent(lesson_ids, passed) == expected
