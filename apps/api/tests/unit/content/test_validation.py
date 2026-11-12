"""Tarea 2.4 — `alas content check`: reglas de §6.6, D-007 y D-008 (R9.4, R9.5, R9.6, R8.3a).

Cada prueba parte de una copia del contenido REAL en `tmp_path`, la modifica en un solo punto y
comprueba el error (o la advertencia) correspondiente. `check_content` nunca lanza por contenido
inválido: todo se acumula en el reporte.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from app.content import validation
from app.content.csv_reader import ENCODING_MESSAGE
from app.content.media import MANIFEST_NAME, ManifestEntry
from app.content.validation import (
    MAX_VIDEO_SECONDS,
    MIN_SCORED_EXERCISES,
    MIN_SPELLING_WORDS,
    MIN_SPELLING_WORDS_L2,
    NODE_SIZE,
    Report,
    check_content,
)
from tests.unit.content.real_content import (
    CONTENT_DIR,
    Row,
    copy_content,
    edit_rows,
    entry_for,
    make_media,
    make_row,
    media_file,
    read_rows,
    real_slugs,
    row_of,
)

M1_SIGNS = 45
M2_SIGNS = 30
M3_SIGNS = 27
M1_N3_SPELLING = "spelling: [CADA, BEBE, HADA, FE, DEBE, DIGA, CAMA, LIMA, MALA, DAME]"


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    return copy_content(tmp_path / "content")


@pytest.fixture
def media_dir(tmp_path: Path) -> Path:
    return tmp_path / "media"


def _check(
    content_dir: Path,
    media_dir: Path,
    *,
    overrides: dict[str, ManifestEntry] | None = None,
    omit: frozenset[str] = frozenset(),
    skip_raw: bool = True,
    labels_path: Path | None = None,
) -> Report:
    """Manifiesto completo para el CSV actual de `content_dir` y luego `check_content`."""
    make_media(media_dir, content_dir, overrides=overrides, omit=omit)
    return check_content(content_dir, media_dir, skip_raw=skip_raw, labels_path=labels_path)


def _matching(report: Report, *parts: str) -> list[str]:
    return [e for e in report.errors if all(p in e for p in parts)]


def _assert_error(report: Report, *parts: str) -> None:
    assert _matching(report, *parts), (parts, report.errors)


def _edit_yaml(content_dir: Path, old: str, new: str) -> None:
    path = content_dir / "conversations.yaml"
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def _edit_json(content_dir: Path, name: str, edit: Callable[[dict[str, object]], None]) -> None:
    path = content_dir / name
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    edit(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _fill_how_to(rows: list[Row]) -> None:
    for row in rows:
        row["how_to"] = f"Cómo se hace «{row['word']}»."


def _to_dictionary(rows: list[Row], *slugs: str) -> None:
    for slug in slugs:
        row = row_of(rows, slug)
        row["node"] = ""
        row["order"] = "0"


# ---------- Constantes del contrato -----------------------------------------------------------


def test_constantes_de_6_6() -> None:
    assert NODE_SIZE == {"STANDARD": (5, 9), "NUMBERS": (5, 10), "ALPHABET": (12, 16)}
    assert MIN_SCORED_EXERCISES == 4
    assert MIN_SPELLING_WORDS == 6
    assert MIN_SPELLING_WORDS_L2 == 4
    assert MAX_VIDEO_SECONDS == 8


# ---------- Contenido real --------------------------------------------------------------------


def test_contenido_real_pasa_sin_errores(media_dir: Path) -> None:
    make_media(media_dir, CONTENT_DIR)
    report = check_content(CONTENT_DIR, media_dir, skip_raw=True)
    assert report.errors == []
    assert report.ok


def test_contenido_real_resumen_por_modulo_publicado(media_dir: Path) -> None:
    make_media(media_dir, CONTENT_DIR)
    report = check_content(CONTENT_DIR, media_dir, skip_raw=True)
    assert report.media_by_module == {
        "M1": (M1_SIGNS, 0),
        "M2": (M2_SIGNS, 0),
        "M3": (M3_SIGNS, 0),
    }


def test_contenido_real_lista_todas_las_senas_sin_how_to(media_dir: Path) -> None:
    make_media(media_dir, CONTENT_DIR)
    report = check_content(CONTENT_DIR, media_dir, skip_raw=True)
    assert set(report.missing_how_to) == set(real_slugs())
    assert len(report.missing_how_to) == 109
    assert report.ok  # how_to vacío es advertencia, no error


def test_copia_del_contenido_real_tambien_pasa(content_dir: Path, media_dir: Path) -> None:
    """Las ayudas de copia no alteran el contenido (base de todas las pruebas siguientes)."""
    edit_rows(content_dir, lambda rows: None)
    report = _check(content_dir, media_dir)
    assert report.errors == []


def test_contenido_completo_no_tiene_advertencias(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, _fill_how_to)
    report = _check(content_dir, media_dir)
    assert report.errors == []
    assert report.warnings == []
    assert report.missing_how_to == []


# ---------- Codificación ----------------------------------------------------------------------


def test_csv_con_mojibake_es_error_con_el_mensaje_de_codificacion(
    content_dir: Path, media_dir: Path
) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "gracias").update(word="GrÃ¡cias"))
    report = _check(content_dir, media_dir)
    assert ENCODING_MESSAGE.format(sample="Ã¡") in report.errors
    assert not report.ok


def test_csv_en_latin1_es_error_y_no_lanza(content_dir: Path, media_dir: Path) -> None:
    make_media(media_dir, content_dir)
    path = content_dir / "signs.csv"
    path.write_bytes(path.read_text(encoding="utf-8").encode("latin-1", errors="replace"))
    report = check_content(content_dir, media_dir, skip_raw=True)
    _assert_error(report, 'Guárdalo como "CSV UTF-8"')


# ---------- Slugs -----------------------------------------------------------------------------


def test_slug_repetido_con_las_filas_reales(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: [*rows, make_row("gracias", "Gracias", "cortesia")])
    assert len(read_rows(content_dir)) == 110  # la fila nueva es la 111 del archivo
    report = _check(content_dir, media_dir)
    assert 'Slug repetido: "gracias" (filas 8 y 111).' in report.errors


@pytest.mark.parametrize(
    "bad", ["pez_azul", "Pez", "pez--azul", "pez-", "-pez", "pez azul", "pez!"]
)
def test_slug_con_formato_invalido(content_dir: Path, media_dir: Path, bad: str) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "pez").update(slug=bad))
    report = _check(content_dir, media_dir)
    _assert_error(report, bad)


def test_slug_con_numeros_y_guiones_es_valido(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: [*rows, make_row("pez-2", "Pez dos", "animales")])
    report = _check(content_dir, media_dir)
    assert report.errors == []


# ---------- Categorías y nodos ----------------------------------------------------------------


def test_categoria_inexistente_con_sugerencia(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "hola").update(category="saludo"))
    report = _check(content_dir, media_dir)
    assert 'Categoría "saludo" no existe. ¿Quisiste decir "saludos"?' in report.errors


def test_categoria_inexistente_sin_sugerencia(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "perro").update(category="xyzqwvk"))
    report = _check(content_dir, media_dir)
    found = _matching(report, 'Categoría "xyzqwvk" no existe.')
    assert found, report.errors
    assert all("¿Quisiste decir" not in e for e in found)


def test_nodo_inexistente(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "perro").update(node="M9-N9", order="1"))
    report = _check(content_dir, media_dir)
    _assert_error(report, "M9-N9")


# ---------- Tamaño de los nodos ---------------------------------------------------------------


def test_nodo_standard_con_menos_de_5(content_dir: Path, media_dir: Path) -> None:
    edit_rows(
        content_dir,
        lambda rows: _to_dictionary(rows, "mucho-gusto", "sordo", "oyente", "si", "no"),
    )
    report = _check(content_dir, media_dir)
    assert "M1-N2 tiene 4 señas; mínimo 5." in report.errors


def test_nodo_standard_con_mas_de_9(content_dir: Path, media_dir: Path) -> None:
    edit_rows(
        content_dir,
        lambda rows: row_of(rows, "con-permiso").update(node="M1-N1", order="10"),
    )
    report = _check(content_dir, media_dir)
    assert "M1-N1 tiene 10 señas; máximo 9." in report.errors


def test_nodo_numbers_con_mas_de_10(content_dir: Path, media_dir: Path) -> None:
    edit_rows(
        content_dir,
        lambda rows: [*rows, make_row("numero-11", "Once", "numeros", "M2-N3", "11")],
    )
    report = _check(content_dir, media_dir)
    assert "M2-N3 tiene 11 señas; máximo 10." in report.errors


def _letter_row(slug: str, word: str, node: str, order: str) -> Row:
    row = make_row(slug, word, "alfabeto", node, order)
    row["motion"] = "static"
    return row


def test_nodo_alphabet_con_menos_de_12(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: _to_dictionary(rows, "letra-k", "letra-l"))
    report = _check(content_dir, media_dir)
    assert "M1-N3 tiene 11 señas; mínimo 12." in report.errors


def test_nodo_alphabet_con_12_es_valido(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: _to_dictionary(rows, "letra-k"))
    report = _check(content_dir, media_dir)
    assert report.errors == []


def test_nodo_alphabet_con_mas_de_16(content_dir: Path, media_dir: Path) -> None:
    edit_rows(
        content_dir,
        lambda rows: [
            *rows,
            _letter_row("letra-ch", "CH", "M1-N4", "15"),
            _letter_row("letra-ll", "LL", "M1-N4", "16"),
            _letter_row("letra-rr", "RR", "M1-N4", "17"),
        ],
    )
    report = _check(content_dir, media_dir)
    assert "M1-N4 tiene 17 señas; máximo 16." in report.errors


def test_nodo_alphabet_con_16_y_digrafos_es_valido(content_dir: Path, media_dir: Path) -> None:
    """R9.11: los dígrafos se soportan sin cambiar código."""
    edit_rows(
        content_dir,
        lambda rows: [
            *rows,
            _letter_row("letra-ch", "CH", "M1-N4", "15"),
            _letter_row("letra-ll", "LL", "M1-N4", "16"),
        ],
    )
    report = _check(content_dir, media_dir)
    assert report.errors == []


# ---------- motion y labels.json --------------------------------------------------------------


def test_letra_sin_motion(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "letra-j").update(motion=""))
    report = _check(content_dir, media_dir)
    assert "letra-j: falta la columna motion (static o dynamic)." in report.errors


def test_letra_con_motion_desconocido(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "letra-a").update(motion="quieta"))
    report = _check(content_dir, media_dir)
    _assert_error(report, "letra-a", "motion")


def test_motion_en_una_sena_que_no_es_letra(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "hola").update(motion="static"))
    report = _check(content_dir, media_dir)
    _assert_error(report, "hola", "motion")


def _labels(tmp_path: Path, labels: list[str]) -> Path:
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(labels), encoding="utf-8")
    return path


def test_labels_con_letra_dynamic(content_dir: Path, media_dir: Path, tmp_path: Path) -> None:
    labels = _labels(tmp_path, ["letra-a", "letra-b", "letra-z"])
    report = _check(content_dir, media_dir, labels_path=labels)
    assert (
        "El modelo del alfabeto incluye letra-z, que tiene movimiento: el modelo estático no "
        "puede reconocerla."
    ) in report.errors


def test_labels_con_etiqueta_que_no_es_slug(
    content_dir: Path, media_dir: Path, tmp_path: Path
) -> None:
    labels = _labels(tmp_path, ["letra-a", "letra-zz"])
    report = _check(content_dir, media_dir, labels_path=labels)
    _assert_error(report, "letra-zz")


def test_labels_de_letras_estaticas_es_valido(
    content_dir: Path, media_dir: Path, tmp_path: Path
) -> None:
    labels = _labels(tmp_path, ["letra-a", "letra-b", "letra-c", "letra-y"])
    report = _check(content_dir, media_dir, labels_path=labels)
    assert report.errors == []


def test_labels_inexistente_no_se_valida(
    content_dir: Path, media_dir: Path, tmp_path: Path
) -> None:
    report = _check(content_dir, media_dir, labels_path=tmp_path / "no-existe" / "labels.json")
    assert report.errors == []


def test_labels_ve_el_motion_del_csv(content_dir: Path, media_dir: Path, tmp_path: Path) -> None:
    """Si el intérprete marca la B como dinámica, el modelo ya no puede incluirla."""
    edit_rows(content_dir, lambda rows: row_of(rows, "letra-b").update(motion="dynamic"))
    labels = _labels(tmp_path, ["letra-a", "letra-b"])
    report = _check(content_dir, media_dir, labels_path=labels)
    assert (
        "El modelo del alfabeto incluye letra-b, que tiene movimiento: el modelo estático no "
        "puede reconocerla."
    ) in report.errors


# ---------- Módulos publicados y no publicados ------------------------------------------------


def test_modulo_publicado_con_nodo_sin_senas(content_dir: Path, media_dir: Path) -> None:
    edit_rows(
        content_dir,
        lambda rows: _to_dictionary(
            rows, "ayuda", "hambre", "sed", "dolor", "medico", "emergencia"
        ),
    )
    report = _check(content_dir, media_dir)
    _assert_error(report, "M3-N4")


def test_modulo_no_publicado_sin_senas_no_es_error(content_dir: Path, media_dir: Path) -> None:
    report = _check(content_dir, media_dir)
    assert report.errors == []
    assert all("M4" not in e for e in report.errors)
    assert "M4" not in report.media_by_module


def test_publicar_m4_sin_senas_es_error(content_dir: Path, media_dir: Path) -> None:
    def publish_m4(data: dict[str, object]) -> None:
        modules = data["modules"]
        assert isinstance(modules, list)
        for module in modules:
            assert isinstance(module, dict)
            if module["id"] == "M4":
                module["published"] = True

    _edit_json(content_dir, "curriculum.json", publish_m4)
    report = _check(content_dir, media_dir)
    _assert_error(report, "M4-N1")


# ---------- Filas -----------------------------------------------------------------------------


def test_order_repetido_en_el_nodo(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "buenos-dias").update(order="1"))
    report = _check(content_dir, media_dir)
    found = [e for e in _matching(report, "M1-N1") if "hola" in e or "buenos-dias" in e]
    assert found, report.errors


def test_order_repetido_en_nodos_distintos_es_valido(content_dir: Path, media_dir: Path) -> None:
    rows = read_rows(content_dir)
    assert row_of(rows, "hola")["order"] == row_of(rows, "nombre")["order"] == "1"
    report = _check(content_dir, media_dir)
    assert report.errors == []


@pytest.mark.parametrize("column", ["word", "meaning", "usage_example"])
def test_campos_obligatorios_vacios(content_dir: Path, media_dir: Path, column: str) -> None:
    edit_rows(content_dir, lambda rows: row_of(rows, "gracias").update({column: "   "}))
    report = _check(content_dir, media_dir)
    found = [e for e in report.errors if ("gracias" in e or "fila 8" in e) and column in e]
    assert found, report.errors


# ---------- Conversaciones (§6.5, D-008) ------------------------------------------------------


def test_conversacion_con_slug_inexistente(content_dir: Path, media_dir: Path) -> None:
    _edit_yaml(content_dir, "answer: mucho-gusto", "answer: saludar")
    report = _check(content_dir, media_dir)
    _assert_error(report, "saludar")


def test_conversacion_con_sena_no_aprendida(content_dir: Path, media_dir: Path) -> None:
    _edit_yaml(
        content_dir,
        "answer: buenas-noches\n        distractors: [hola, como-estas]",
        "answer: familia\n        distractors: [hola, como-estas]",
    )
    report = _check(content_dir, media_dir)
    _assert_error(report, "familia", "M1-N1")


def test_conversacion_con_sena_de_diccionario(content_dir: Path, media_dir: Path) -> None:
    _edit_yaml(
        content_dir,
        "answer: buenas-noches\n        distractors: [hola, como-estas]",
        "answer: perro\n        distractors: [hola, como-estas]",
    )
    report = _check(content_dir, media_dir)
    _assert_error(report, "perro")


def test_conversacion_hola_responde_hola_es_error(content_dir: Path, media_dir: Path) -> None:
    """D-008: el estímulo no puede aparecer entre sus propias opciones."""
    _edit_yaml(
        content_dir,
        "answer: buenos-dias\n        distractors: [adios, buenas-noches]",
        "answer: hola\n        distractors: [adios, buenas-noches]",
    )
    report = _check(content_dir, media_dir)
    _assert_error(report, "M1-N1", "«hola»")


def test_conversacion_con_estimulo_como_distractor_es_error(
    content_dir: Path, media_dir: Path
) -> None:
    _edit_yaml(
        content_dir,
        "answer: buenos-dias\n        distractors: [adios, buenas-noches]",
        "answer: buenos-dias\n        distractors: [hola, buenas-noches]",
    )
    report = _check(content_dir, media_dir)
    _assert_error(report, "M1-N1", "«hola»")


def test_conversacion_con_opciones_repetidas_es_error(content_dir: Path, media_dir: Path) -> None:
    _edit_yaml(
        content_dir,
        "answer: buenos-dias\n        distractors: [adios, buenas-noches]",
        "answer: buenos-dias\n        distractors: [adios, adios]",
    )
    report = _check(content_dir, media_dir)
    _assert_error(report, "M1-N1")


def test_sin_conversacion_valida_para_l2(content_dir: Path, media_dir: Path) -> None:
    _edit_yaml(
        content_dir,
        "answer: oyente\n        distractors: [yo, tu]",
        "answer: si\n        distractors: [yo, tu]",
    )
    report = _check(content_dir, media_dir)
    assert (
        "M1-N2 necesita una conversación que use solo señas de L1–L2 o de nodos anteriores."  # noqa: RUF001 — texto exacto de §6.5
    ) in report.errors


def test_menos_de_4_ejercicios_con_puntaje(
    content_dir: Path, media_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con el contenido real no ocurre: se sube el mínimo para comprobar que la regla se aplica
    a cada lección generada con el mensaje de §6.6."""
    monkeypatch.setattr(validation, "MIN_SCORED_EXERCISES", 1000)
    report = _check(content_dir, media_dir)
    pattern = re.compile(r"^M1-N1-L1 tiene \d+ ejercicios con puntaje; mínimo 1000\.$")
    assert any(pattern.match(e) for e in report.errors), report.errors
    lessons = {e.split(" ", 1)[0] for e in report.errors if "ejercicios con puntaje" in e}
    assert len(lessons) == 48  # todas las lecciones de M1 a M3


# ---------- Deletreo (§6.5, D-007.4) ----------------------------------------------------------


def _set_m1_n3_spelling(content_dir: Path, words: str) -> None:
    _edit_yaml(content_dir, M1_N3_SPELLING, f"spelling: [{words}]")


def test_palabra_de_deletreo_con_letra_no_ensenada(content_dir: Path, media_dir: Path) -> None:
    """La S se enseña en M1-N4: «SAL» no es válida en ninguna lección de M1-N3."""
    _set_m1_n3_spelling(content_dir, "CADA, BEBE, HADA, FE, DEBE, DIGA, CAMA, LIMA, MALA, SAL")
    report = _check(content_dir, media_dir)
    _assert_error(report, "«SAL»", "letra S", "M1-N3")


def test_palabra_de_deletreo_con_letra_inexistente(content_dir: Path, media_dir: Path) -> None:
    _set_m1_n3_spelling(content_dir, "CADA, BEBE, HADA, FE, DEBE, DIGA, CAMA, LIMA, MALA, Ç")
    report = _check(content_dir, media_dir)
    _assert_error(report, "«Ç»")


def test_palabra_de_deletreo_en_minusculas(content_dir: Path, media_dir: Path) -> None:
    _set_m1_n3_spelling(content_dir, "cada, BEBE, HADA, FE, DEBE, DIGA, CAMA, LIMA, MALA, DAME")
    report = _check(content_dir, media_dir)
    _assert_error(report, "«cada»", "mayúsculas")


def test_menos_de_6_palabras_de_deletreo(content_dir: Path, media_dir: Path) -> None:
    _set_m1_n3_spelling(content_dir, "CADA, BEBE, HADA, FE, DEBE")
    report = _check(content_dir, media_dir)
    _assert_error(report, "M1-N3", "6")


def test_menos_de_4_palabras_validas_para_l2(content_dir: Path, media_dir: Path) -> None:
    """L2 de M1-N3 solo tiene de la A a la I: CAMA, LIMA, MALA y DAME no sirven ahí."""
    _set_m1_n3_spelling(content_dir, "CADA, BEBE, HADA, CAMA, LIMA, MALA, DAME")
    report = _check(content_dir, media_dir)
    _assert_error(report, "M1-N3", "4")


def test_deletreo_en_el_limite_es_valido(content_dir: Path, media_dir: Path) -> None:
    _set_m1_n3_spelling(content_dir, "CADA, BEBE, HADA, FE, CAMA, LIMA")
    report = _check(content_dir, media_dir)
    assert report.errors == []


# ---------- Manifiesto de medios --------------------------------------------------------------


def test_manifiesto_sin_entrada_para_una_sena(content_dir: Path, media_dir: Path) -> None:
    report = _check(content_dir, media_dir, omit=frozenset({"gracias"}))
    assert "Falta el video de «gracias». Ejecuta alas content all." in report.errors
    assert len(_matching(report, "Falta el video")) == 1


def test_sin_manifiesto_faltan_todos_los_videos(content_dir: Path, media_dir: Path) -> None:
    media_dir.mkdir()
    report = check_content(content_dir, media_dir, skip_raw=True)
    assert "Falta el video de «hola». Ejecuta alas content all." in report.errors
    assert len(_matching(report, "Falta el video")) == 109


def test_video_del_manifiesto_inexistente(content_dir: Path, media_dir: Path) -> None:
    manifest = make_media(media_dir, content_dir)
    media_file(media_dir, manifest.signs["gracias"].video).unlink()
    report = check_content(content_dir, media_dir, skip_raw=True)
    _assert_error(report, "«gracias»")
    assert not report.ok


def test_poster_del_manifiesto_inexistente(content_dir: Path, media_dir: Path) -> None:
    manifest = make_media(media_dir, content_dir)
    media_file(media_dir, manifest.signs["gracias"].poster).unlink()
    report = check_content(content_dir, media_dir, skip_raw=True)
    _assert_error(report, "«gracias»")


def test_manifiesto_corrupto_es_error_y_no_lanza(content_dir: Path, media_dir: Path) -> None:
    make_media(media_dir, content_dir)
    (media_dir / MANIFEST_NAME).write_text("{ no es json", encoding="utf-8")
    report = check_content(content_dir, media_dir, skip_raw=True)
    assert not report.ok


# ---------- Advertencias ----------------------------------------------------------------------


def test_how_to_vacio_es_advertencia(content_dir: Path, media_dir: Path) -> None:
    def fill_all_but_gracias(rows: list[Row]) -> None:
        _fill_how_to(rows)
        row_of(rows, "gracias")["how_to"] = ""

    edit_rows(content_dir, fill_all_but_gracias)
    report = _check(content_dir, media_dir)
    assert report.errors == []
    assert report.missing_how_to == ["gracias"]


def test_video_de_relleno_es_advertencia(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, _fill_how_to)
    overrides = {"gracias": entry_for("gracias", placeholder=True)}
    report = _check(content_dir, media_dir, overrides=overrides)
    assert report.errors == []
    assert any("gracias" in w for w in report.warnings), report.warnings
    assert report.media_by_module == {
        "M1": (M1_SIGNS - 1, 1),
        "M2": (M2_SIGNS, 0),
        "M3": (M3_SIGNS, 0),
    }


def test_imagenes_cuentan_como_medio_real(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, _fill_how_to)
    images = entry_for("hola").model_copy(update={"source": "images", "frames": 2})
    report = _check(content_dir, media_dir, overrides={"hola": images})
    assert report.errors == []
    assert report.media_by_module["M1"] == (M1_SIGNS, 0)


def test_video_de_mas_de_8_segundos_es_advertencia(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, _fill_how_to)
    overrides = {"gracias": entry_for("gracias", duration=9.5)}
    report = _check(content_dir, media_dir, overrides=overrides)
    assert report.errors == []
    assert any("gracias" in w for w in report.warnings), report.warnings


def test_video_de_8_segundos_exactos_no_advierte(content_dir: Path, media_dir: Path) -> None:
    edit_rows(content_dir, _fill_how_to)
    overrides = {"gracias": entry_for("gracias", duration=8.0)}
    report = _check(content_dir, media_dir, overrides=overrides)
    assert report.errors == []
    assert report.warnings == []


# ---------- raw/ (skip_raw) -------------------------------------------------------------------


def _raw_file(content_dir: Path, name: str) -> Path:
    raw = content_dir / "videos" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    path = raw / name
    path.write_bytes(b"")
    return path


def test_raw_con_nombre_que_no_es_slug_sugiere(content_dir: Path, media_dir: Path) -> None:
    _raw_file(content_dir, "Gracia.mp4")
    report = _check(content_dir, media_dir, skip_raw=False)
    found = _matching(report, "Gracia.mp4 no corresponde a ninguna seña.")
    assert found, report.errors
    assert any('¿Quisiste decir "gracias"?' in e for e in found)


def test_skip_raw_no_revisa_raw(content_dir: Path, media_dir: Path) -> None:
    _raw_file(content_dir, "Gracia.mp4")
    report = _check(content_dir, media_dir, skip_raw=True)
    assert report.errors == []


def test_sin_carpeta_raw_no_es_error(content_dir: Path, media_dir: Path) -> None:
    report = _check(content_dir, media_dir, skip_raw=False)
    assert report.errors == []


def test_raw_heic_es_error(content_dir: Path, media_dir: Path) -> None:
    _raw_file(content_dir, "gracias.heic")
    report = _check(content_dir, media_dir, skip_raw=False)
    _assert_error(report, "HEIC")


# ---------- check_content nunca lanza ---------------------------------------------------------


def test_curriculum_roto_se_reporta(content_dir: Path, media_dir: Path) -> None:
    make_media(media_dir, content_dir)
    (content_dir / "curriculum.json").write_text("{ roto", encoding="utf-8")
    report = check_content(content_dir, media_dir, skip_raw=True)
    _assert_error(report, "curriculum.json")


def test_yaml_roto_se_reporta(content_dir: Path, media_dir: Path) -> None:
    make_media(media_dir, content_dir)
    (content_dir / "conversations.yaml").write_text("M1-N1:\n  - turns: hola\n", encoding="utf-8")
    report = check_content(content_dir, media_dir, skip_raw=True)
    _assert_error(report, "M1-N1")


def test_csv_inexistente_se_reporta(content_dir: Path, media_dir: Path) -> None:
    make_media(media_dir, content_dir)
    (content_dir / "signs.csv").unlink()
    report = check_content(content_dir, media_dir, skip_raw=True)
    _assert_error(report, "signs.csv")


def test_directorio_vacio_se_reporta(tmp_path: Path, media_dir: Path) -> None:
    empty = tmp_path / "vacio"
    empty.mkdir()
    media_dir.mkdir()
    report = check_content(empty, media_dir, skip_raw=True)
    assert not report.ok


# ---------- Report ----------------------------------------------------------------------------


def test_report_ok() -> None:
    assert Report().ok
    assert Report(warnings=["Aviso"]).ok
    assert not Report(errors=["Error"]).ok


def test_render_en_espanol_con_resumen_advertencias_y_errores() -> None:
    report = Report(
        errors=['Categoría "saludo" no existe. ¿Quisiste decir "saludos"?'],
        warnings=["«gracias» usa un video de relleno."],
        media_by_module={"M1": (40, 5), "M2": (30, 0)},
        missing_how_to=["gracias", "hola"],
    )
    text = report.render()
    assert 'Categoría "saludo" no existe. ¿Quisiste decir "saludos"?' in text
    assert "«gracias» usa un video de relleno." in text
    m1_lines = [line for line in text.splitlines() if "M1" in line]
    assert m1_lines, text
    assert any("40" in line and "5" in line for line in m1_lines), text
    assert any("M2" in line and "30" in line for line in text.splitlines()), text
    assert "hola" in text
    assert "relleno" in text.lower()
    assert "error" in text.lower()


def test_render_sin_errores_lo_indica() -> None:
    text = Report(media_by_module={"M1": (45, 0)}).render()
    assert "M1" in text
    assert "45" in text
    assert text.strip()


def test_labels_acepta_ninguna(content_dir: Path, media_dir: Path, tmp_path: Path) -> None:
    """§10.5: el modelo siempre incluye la clase «NINGUNA» (sin seña); no es un slug."""
    labels = _labels(tmp_path, ["NINGUNA", "letra-a", "letra-b"])
    report = _check(content_dir, media_dir, labels_path=labels)
    assert report.errors == []


# ---------- content/dataset-mapping.csv (anexo A.7, regla 3) ------------------------------------


DATASETS_HEADER = "fuente,licencia,enlace,cita\n"
LSC54_ROW = (
    'LSC-54,CC BY-NC 4.0,https://doi.org/10.57760/sciencedb.25639,"Mora-Zarate et al., 2025"\n'
)


def _datasets(content_dir: Path, text: str) -> None:
    (content_dir / "datasets.csv").write_text(text, encoding="utf-8", newline="\n")


def _mapping(content_dir: Path, text: str, *, datasets: str = DATASETS_HEADER + LSC54_ROW) -> None:
    """El mapeo siempre va con su registro de fuentes y licencias (`datasets.csv`, D-044)."""
    (content_dir / "dataset-mapping.csv").write_text(text, encoding="utf-8", newline="\n")
    _datasets(content_dir, datasets)


def test_mapeo_de_datasets_valido(content_dir: Path, media_dir: Path) -> None:
    _mapping(
        content_dir, "fuente,etiqueta_fuente,slug\n# nota\nLSC-54,Hola,hola\nLSC-54,Bien,NINGUNA\n"
    )
    assert _check(content_dir, media_dir).errors == []


def test_mapeo_con_slug_que_no_es_sena(content_dir: Path, media_dir: Path) -> None:
    _mapping(content_dir, "fuente,etiqueta_fuente,slug\nLSC-54,Hola,holaa\n")
    _assert_error(_check(content_dir, media_dir), "dataset-mapping.csv", "holaa")


def test_mapeo_con_cabecera_o_fila_invalida(content_dir: Path, media_dir: Path) -> None:
    _mapping(content_dir, "fuente,slug\nLSC-54,hola\n")
    _assert_error(_check(content_dir, media_dir), "dataset-mapping.csv", "cabecera")
    _mapping(content_dir, "fuente,etiqueta_fuente,slug\nLSC-54,,hola\n")
    _assert_error(_check(content_dir, media_dir), "dataset-mapping.csv", "línea 2")


def test_mapeo_con_etiqueta_repetida(content_dir: Path, media_dir: Path) -> None:
    _mapping(content_dir, "fuente,etiqueta_fuente,slug\nLSC-54,Hola,hola\nLSC-54,hola,adios\n")
    _assert_error(_check(content_dir, media_dir), "dataset-mapping.csv", "repetida")


# ---------- content/datasets.csv: fuente y licencia de cada dataset externo (D-044) ---------------


def test_cada_fuente_del_mapeo_debe_tener_licencia_registrada(
    content_dir: Path, media_dir: Path
) -> None:
    _mapping(
        content_dir,
        "fuente,etiqueta_fuente,slug\nLSC-54,Hola,hola\nLSC70,Hola,hola\n",
    )
    _assert_error(_check(content_dir, media_dir), "datasets.csv", "LSC70")


def test_mapeo_sin_datasets_csv_es_error(content_dir: Path, media_dir: Path) -> None:
    _mapping(content_dir, "fuente,etiqueta_fuente,slug\nLSC-54,Hola,hola\n")
    (content_dir / "datasets.csv").unlink()
    _assert_error(_check(content_dir, media_dir), "datasets.csv", "LSC-54")


def test_datasets_csv_valido_con_cita_entre_comillas(content_dir: Path, media_dir: Path) -> None:
    _mapping(
        content_dir,
        "fuente,etiqueta_fuente,slug\nLSC-54,Hola,hola\n",
        datasets=DATASETS_HEADER
        + LSC54_ROW
        + "LSC70,CC BY 4.0,https://data.mendeley.com/datasets/9ssyn8tff5/2,"
        + '"Muñoz Galindez, Villota Coral y Vargas-Canas, 2024"\n',
    )
    assert _check(content_dir, media_dir).errors == []


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("fuente,licencia\nLSC-54,CC BY-NC 4.0\n", "cabecera"),
        (DATASETS_HEADER + "LSC-54,,https://x.org,cita\n", "línea 2"),
        (DATASETS_HEADER + "LSC-54,CC BY-NC 4.0,ftp://x.org,cita\n", "https"),
        (DATASETS_HEADER + LSC54_ROW + LSC54_ROW, "repetida"),
    ],
)
def test_datasets_csv_invalido(
    content_dir: Path, media_dir: Path, text: str, fragment: str
) -> None:
    _mapping(content_dir, "fuente,etiqueta_fuente,slug\nLSC-54,Hola,hola\n", datasets=text)
    _assert_error(_check(content_dir, media_dir), "datasets.csv", fragment)


# ---------- content/camera-equivalences.csv (D-027) ---------------------------------------------


def _equivalences(content_dir: Path, rows: str) -> None:
    (content_dir / "camera-equivalences.csv").write_text(
        "slug,equivalente,nota\n" + rows, encoding="utf-8", newline="\n"
    )


def test_equivalencias_validas(content_dir: Path, media_dir: Path) -> None:
    _equivalences(content_dir, "# nota\nletra-b,numero-4,misma forma\n")
    assert _check(content_dir, media_dir).errors == []


def test_equivalencia_con_slug_inexistente(content_dir: Path, media_dir: Path) -> None:
    _equivalences(content_dir, "letra-b,numero-44,x\n")
    _assert_error(_check(content_dir, media_dir), "camera-equivalences.csv", "numero-44")


def test_equivalencia_consigo_misma_o_repetida(content_dir: Path, media_dir: Path) -> None:
    _equivalences(content_dir, "letra-b,letra-b,x\n")
    _assert_error(_check(content_dir, media_dir), "camera-equivalences.csv", "misma seña")
    _equivalences(content_dir, "letra-b,numero-4,x\nnumero-4,letra-b,y\n")
    _assert_error(_check(content_dir, media_dir), "camera-equivalences.csv", "repetido")


def test_equivalencia_con_cabecera_invalida(content_dir: Path, media_dir: Path) -> None:
    (content_dir / "camera-equivalences.csv").write_text(
        "a,b\nletra-b,numero-4\n", encoding="utf-8"
    )
    _assert_error(_check(content_dir, media_dir), "camera-equivalences.csv", "cabecera")
