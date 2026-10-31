"""Tarea 2.3 — lector de `signs.csv` (§6.2, §6.6, R9.5, B12)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.content.csv_reader import (
    COLUMNS,
    ENCODING_MESSAGE,
    MOJIBAKE_MARKERS,
    SignRow,
    read_signs_csv,
)
from app.content.errors import ContentError
from tests.unit.content.real_content import CONTENT_DIR

HEADER = "slug,word,meaning,how_to,usage_example,category,node,order,motion"
HOLA = "hola,Hola,Saludo informal.,,Al llegar dices «Hola».,saludos,M1-N1,1,"
GRACIAS = "gracias,Gracias,Para agradecer.,Mano en el mentón.,Dices «Gracias».,cortesia,M1-N1,7,"
LETRA_J = "letra-j,J,Letra J.,,Para deletrear «jugar».,alfabeto,M1-N3,10,dynamic"
PERRO = "perro,Perro,Animal doméstico.,,Mi perro se llama Max.,animales,,,"

ENCODING_PATTERN = re.compile(
    r'^signs\.csv parece guardado con codificación incorrecta \(se ve "(?P<sample>.+)"\)\. '
    r'Guárdalo como "CSV UTF-8" o expórtalo desde Google Sheets\.$'
)


def _write_bytes(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / "signs.csv"
    path.write_bytes(data)
    return path


def _write_lines(tmp_path: Path, *lines: str, bom: bool = False, newline: str = "\n") -> Path:
    data = (newline.join(lines) + newline).encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    return _write_bytes(tmp_path, data)


def _read_error(path: Path) -> str:
    with pytest.raises(ContentError) as info:
        read_signs_csv(path)
    return str(info.value)


# ---------- Lectura correcta ------------------------------------------------------------------


def test_constantes_del_contrato() -> None:
    assert tuple(HEADER.split(",")) == COLUMNS
    assert MOJIBAKE_MARKERS == ("Ã", "Â", "�")


def test_lee_una_fila_con_todos_los_campos(tmp_path: Path) -> None:
    rows = read_signs_csv(_write_lines(tmp_path, HEADER, GRACIAS))
    assert rows == [
        SignRow(
            slug="gracias",
            word="Gracias",
            meaning="Para agradecer.",
            how_to="Mano en el mentón.",
            usage_example="Dices «Gracias».",
            category="cortesia",
            node="M1-N1",
            order=7,
            motion=None,
            line=2,
        )
    ]


def test_bom_utf8_se_elimina_y_la_primera_columna_es_slug(tmp_path: Path) -> None:
    rows = read_signs_csv(_write_lines(tmp_path, HEADER, HOLA, bom=True))
    assert len(rows) == 1
    assert rows[0].slug == "hola"
    assert not rows[0].slug.startswith("﻿")


def test_celdas_se_recortan(tmp_path: Path) -> None:
    line = "  hola , Hola  ,  Saludo informal. ,   ,  Dices «Hola». , saludos , M1-N1 , 1 ,  "
    rows = read_signs_csv(_write_lines(tmp_path, HEADER, line))
    row = rows[0]
    assert row.slug == "hola"
    assert row.word == "Hola"
    assert row.meaning == "Saludo informal."
    assert row.how_to is None  # solo espacios = vacío
    assert row.usage_example == "Dices «Hola»."
    assert row.category == "saludos"
    assert row.node == "M1-N1"
    assert row.order == 1
    assert row.motion is None


def test_vacios_se_convierten_en_none_y_order_vacio_en_cero(tmp_path: Path) -> None:
    rows = read_signs_csv(_write_lines(tmp_path, HEADER, PERRO))
    row = rows[0]
    assert row.how_to is None
    assert row.node is None
    assert row.motion is None
    assert row.order == 0


def test_motion_se_lee_tal_cual(tmp_path: Path) -> None:
    rows = read_signs_csv(_write_lines(tmp_path, HEADER, LETRA_J))
    assert rows[0].motion == "dynamic"
    assert rows[0].order == 10


def test_line_es_el_numero_de_fila_en_el_archivo(tmp_path: Path) -> None:
    rows = read_signs_csv(_write_lines(tmp_path, HEADER, HOLA, GRACIAS, LETRA_J, PERRO))
    assert [(r.slug, r.line) for r in rows] == [
        ("hola", 2),
        ("gracias", 3),
        ("letra-j", 4),
        ("perro", 5),
    ]


def test_finales_de_linea_crlf_de_excel(tmp_path: Path) -> None:
    rows = read_signs_csv(_write_lines(tmp_path, HEADER, HOLA, GRACIAS, bom=True, newline="\r\n"))
    assert [(r.slug, r.line, r.motion) for r in rows] == [
        ("hola", 2, None),
        ("gracias", 3, None),
    ]


def test_la_enie_y_las_tildes_se_leen_bien(tmp_path: Path) -> None:
    lines = (
        HEADER,
        "letra-n-tilde,Ñ,Letra Ñ.,,Como en «niño».,alfabeto,M1-N4,2,dynamic",
        "banarse,Bañarse,Lavarse el cuerpo.,,Me baño en la mañana.,actividades,M2-N4,7,",
        "como-estas,¿Cómo estás?,Pregunta por el ánimo.,,«¿Cómo estás?»,saludos,M1-N1,5,",
    )
    rows = read_signs_csv(_write_lines(tmp_path, *lines))
    assert [r.word for r in rows] == ["Ñ", "Bañarse", "¿Cómo estás?"]
    assert rows[0].usage_example == "Como en «niño»."
    assert rows[1].usage_example == "Me baño en la mañana."
    assert rows[2].meaning == "Pregunta por el ánimo."


def test_celdas_con_comas_entre_comillas(tmp_path: Path) -> None:
    line = 'agua,Agua,Líquido.,,"Tengo sed, ¿me das un vaso de agua?",alimentos,M3-N1,1,'
    rows = read_signs_csv(_write_lines(tmp_path, HEADER, line))
    assert rows[0].usage_example == "Tengo sed, ¿me das un vaso de agua?"
    assert rows[0].category == "alimentos"


def test_lee_el_csv_real() -> None:
    rows = read_signs_csv(CONTENT_DIR / "signs.csv")
    assert len(rows) == 109
    by_slug = {r.slug: r for r in rows}
    assert by_slug["hola"].line == 2
    assert by_slug["gracias"].line == 8
    assert by_slug["letra-j"].motion == "dynamic"
    assert by_slug["letra-a"].motion == "static"
    assert by_slug["letra-n-tilde"].word == "Ñ"
    assert by_slug["como-estas"].word == "¿Cómo estás?"
    assert by_slug["perro"].node is None
    assert by_slug["perro"].order == 0
    assert by_slug["hola"].how_to is None


# ---------- Codificación incorrecta (B12) -----------------------------------------------------


def test_mojibake_de_tilde_da_el_mensaje_exacto(tmp_path: Path) -> None:
    line = "gracias,GrÃ¡cias,Para agradecer.,,Dices «Gracias».,cortesia,M1-N1,7,"
    message = _read_error(_write_lines(tmp_path, HEADER, line))
    assert message == ENCODING_MESSAGE.format(sample="Ã¡")
    assert message == (
        'signs.csv parece guardado con codificación incorrecta (se ve "Ã¡"). '
        'Guárdalo como "CSV UTF-8" o expórtalo desde Google Sheets.'
    )


@pytest.mark.parametrize(
    ("cell", "marker"),
    [
        ("CÃ³mo estÃ¡s", "Ã"),
        ("Â¿Como estas?", "Â"),
        ("Gr�cias", "�"),
    ],
)
def test_cualquier_marcador_de_mojibake_es_error(tmp_path: Path, cell: str, marker: str) -> None:
    line = f"como-estas,{cell},Pregunta.,,Ejemplo.,saludos,M1-N1,5,"
    message = _read_error(_write_lines(tmp_path, HEADER, line))
    match = ENCODING_PATTERN.match(message)
    assert match is not None, message
    assert marker in match.group("sample")
    assert match.group("sample") in cell


def test_mojibake_en_otra_columna_tambien_es_error(tmp_path: Path) -> None:
    line = "hola,Hola,Saludo para empezar una conversaciÃ³n.,,Ejemplo.,saludos,M1-N1,1,"
    message = _read_error(_write_lines(tmp_path, HEADER, line))
    assert ENCODING_PATTERN.match(message) is not None, message


def test_archivo_latin1_es_error_con_instrucciones_de_utf8(tmp_path: Path) -> None:
    text = HEADER + "\n" + "banarse,Bañarse,Lavarse.,,Me baño.,actividades,M2-N4,7,\n"
    data = text.encode("latin-1")
    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8")  # precondición: bytes no UTF-8
    message = _read_error(_write_bytes(tmp_path, data))
    assert message.startswith("signs.csv parece guardado con codificación incorrecta")
    assert 'Guárdalo como "CSV UTF-8" o expórtalo desde Google Sheets.' in message


def test_archivo_cp1252_de_excel_es_error(tmp_path: Path) -> None:
    text = HEADER + "\n" + "como-estas,¿Cómo estás?,Pregunta.,,«Ejemplo».,saludos,M1-N1,5,\n"
    message = _read_error(_write_bytes(tmp_path, text.encode("cp1252")))
    assert 'Guárdalo como "CSV UTF-8"' in message


# ---------- Estructura -----------------------------------------------------------------------


def test_columna_faltante(tmp_path: Path) -> None:
    header = "slug,word,meaning,how_to,usage_example,category,node,order"
    line = "hola,Hola,Saludo.,,Ejemplo.,saludos,M1-N1,1"
    message = _read_error(_write_lines(tmp_path, header, line))
    assert message == 'signs.csv no tiene la columna "motion".'


def test_columna_faltante_nombra_la_que_falta(tmp_path: Path) -> None:
    header = "slug,word,how_to,usage_example,category,node,order,motion"
    line = "hola,Hola,,Ejemplo.,saludos,M1-N1,1,"
    message = _read_error(_write_lines(tmp_path, header, line))
    assert message == 'signs.csv no tiene la columna "meaning".'


def test_order_no_entero(tmp_path: Path) -> None:
    line = "gracias,Gracias,Para agradecer.,,Ejemplo.,cortesia,M1-N1,siete,"
    message = _read_error(_write_lines(tmp_path, HEADER, HOLA, line))
    assert message == 'signs.csv fila 3: "order" debe ser un número entero.'


@pytest.mark.parametrize("value", ["1.5", "uno", "2a"])
def test_order_con_decimales_o_texto_es_error(tmp_path: Path, value: str) -> None:
    line = f"hola,Hola,Saludo.,,Ejemplo.,saludos,M1-N1,{value},"
    message = _read_error(_write_lines(tmp_path, HEADER, line))
    assert message == 'signs.csv fila 2: "order" debe ser un número entero.'


def test_archivo_solo_con_cabecera_no_tiene_filas(tmp_path: Path) -> None:
    assert read_signs_csv(_write_lines(tmp_path, HEADER)) == []
