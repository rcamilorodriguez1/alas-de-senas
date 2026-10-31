"""Tarea 1.2 — normalización de texto y Levenshtein (§7.8, R7.1)."""

from __future__ import annotations

import pytest

from app.domain.text import levenshtein, normalize_text

# --- normalize_text: casos obligatorios de §7.8 ------------------------------------------------


def test_normalize_quita_espacios_mayusculas_y_tildes() -> None:
    assert normalize_text("  GRACÍAS ") == "gracias"


def test_normalize_quita_signos_de_interrogacion_y_tildes() -> None:
    assert normalize_text("¿Cómo estás?") == "como estas"


def test_normalize_conserva_la_enie_en_ano() -> None:
    assert normalize_text("Año") == "año"


def test_normalize_conserva_la_enie_mayuscula() -> None:
    assert normalize_text("BAÑO") == "baño"


# --- normalize_text: casos límite --------------------------------------------------------------


def test_normalize_ano_con_enie_y_sin_enie_son_distintos() -> None:
    assert normalize_text("año") != normalize_text("ano")


def test_normalize_enie_descompuesta_nfd_se_conserva() -> None:
    # "n" + tilde combinable (U+0303), como llega a veces al copiar de otras fuentes.
    assert normalize_text("año") == "año"


def test_normalize_quita_exclamaciones_y_puntuacion() -> None:
    assert normalize_text("¡Hola, amigo! ¿Bien; sí: no.") == "hola amigo bien si no"


def test_normalize_colapsa_espacios_internos() -> None:
    assert normalize_text("buenos   \t días") == "buenos dias"


def test_normalize_quita_dieresis() -> None:
    assert normalize_text("Pingüino") == "pinguino"


def test_normalize_cadena_vacia() -> None:
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""


def test_normalize_solo_signos_queda_vacio() -> None:
    assert normalize_text("¿?¡!") == ""


def test_normalize_es_idempotente() -> None:
    once = normalize_text("  ¿Cómo  ESTÁS, Señor? ")
    assert once == "como estas señor"
    assert normalize_text(once) == once


# --- levenshtein -------------------------------------------------------------------------------


def test_levenshtein_vacia_contra_abc_es_3() -> None:
    assert levenshtein("", "abc") == 3


def test_levenshtein_es_simetrica() -> None:
    assert levenshtein("abc", "") == 3
    assert levenshtein("gracias", "grasias") == levenshtein("grasias", "gracias")
    assert levenshtein("kitten", "sitting") == levenshtein("sitting", "kitten")


def test_levenshtein_gracias_grasias_es_1() -> None:
    assert levenshtein("gracias", "grasias") == 1


def test_levenshtein_iguales_es_cero() -> None:
    assert levenshtein("hola", "hola") == 0


def test_levenshtein_ambas_vacias_es_cero() -> None:
    assert levenshtein("", "") == 0


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("kitten", "sitting", 3),
        ("hola", "ola", 1),  # eliminación
        ("ola", "hola", 1),  # inserción
        ("año", "ano", 1),  # la ñ es un carácter distinto de la n
        ("casa", "cosa", 1),
        ("abc", "xyz", 3),
        ("flaw", "lawn", 2),
    ],
)
def test_levenshtein_casos_conocidos(a: str, b: str, expected: int) -> None:
    assert levenshtein(a, b) == expected
