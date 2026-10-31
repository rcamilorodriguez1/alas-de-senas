"""Tareas 2.6/2.6b — emparejamiento de archivos de raw/ con slugs (§6.4, §6.4.1, B32, B90, B95)."""

from __future__ import annotations

from pathlib import Path

from app.content.raw_files import HEIC_MESSAGE, MAX_FRAMES, scan_raw, suggest_slug

SLUGS = frozenset(
    {
        "hola",
        "gracias",
        "buenos-dias",
        "numero-1",
        "numero-10",
        "letra-a",
        "letra-n-tilde",
        "banarse",
    }
)


def _touch(raw_dir: Path, *names: str) -> list[Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        path = raw_dir / name
        path.write_bytes(b"")
        paths.append(path)
    return paths


def _names(paths: tuple[Path, ...]) -> list[str]:
    return [p.name for p in paths]


# ---------- suggest_slug ----------


def test_suggest_slug_sugiere_el_slug_mas_parecido() -> None:
    assert suggest_slug("Gracia", SLUGS) == "gracias"


def test_suggest_slug_espacios_y_guion_bajo_se_vuelven_guion() -> None:
    assert suggest_slug("buenos dias", SLUGS) == "buenos-dias"
    assert suggest_slug("buenos_dias", SLUGS) == "buenos-dias"


def test_suggest_slug_ignora_mayusculas_y_tildes() -> None:
    assert suggest_slug("Buenos Días", SLUGS) == "buenos-dias"
    assert suggest_slug("Bañarse", SLUGS) == "banarse"


def test_suggest_slug_sin_parecido_devuelve_none() -> None:
    assert suggest_slug("xyz", SLUGS) is None
    assert suggest_slug("computador-portatil", SLUGS) is None


def test_suggest_slug_acepta_distancia_3_pero_no_4() -> None:
    assert suggest_slug("gra", {"gracias"}) is None  # distancia 4
    assert suggest_slug("grac", {"gracias"}) == "gracias"  # distancia 3


# ---------- scan_raw: nombres válidos ----------


def test_video_con_nombre_de_slug(tmp_path: Path) -> None:
    (video,) = _touch(tmp_path, "gracias.mp4")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert scan.warnings == []
    asset = scan.assets["gracias"]
    assert asset.slug == "gracias"
    assert asset.kind == "video"
    assert asset.paths == (video,)


def test_todas_las_extensiones_de_video_admitidas(tmp_path: Path) -> None:
    _touch(tmp_path, "hola.mov", "gracias.webm", "letra-a.m4v", "banarse.mp4")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert {slug: a.kind for slug, a in scan.assets.items()} == {
        "hola": "video",
        "gracias": "video",
        "letra-a": "video",
        "banarse": "video",
    }


def test_extension_en_mayusculas_se_acepta(tmp_path: Path) -> None:
    _touch(tmp_path, "gracias.MP4", "letra-a.JPG")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert scan.assets["gracias"].kind == "video"
    assert scan.assets["letra-a"].kind == "images"


def test_nombre_en_mayusculas_se_acepta(tmp_path: Path) -> None:
    (video,) = _touch(tmp_path, "GRACIAS.MP4")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert scan.assets["gracias"].kind == "video"
    assert scan.assets["gracias"].paths == (video,)


def test_una_imagen_con_nombre_de_slug(tmp_path: Path) -> None:
    (image,) = _touch(tmp_path, "letra-a.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert scan.assets["letra-a"].kind == "images"
    assert scan.assets["letra-a"].paths == (image,)


def test_todas_las_extensiones_de_imagen_admitidas(tmp_path: Path) -> None:
    _touch(tmp_path, "hola.jpeg", "gracias.png", "letra-a.webp", "banarse.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert all(a.kind == "images" for a in scan.assets.values())
    assert set(scan.assets) == {"hola", "gracias", "letra-a", "banarse"}


def test_numero_1_jpg_es_imagen_de_numero_1_b90(tmp_path: Path) -> None:
    (image,) = _touch(tmp_path, "numero-1.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert set(scan.assets) == {"numero-1"}
    assert scan.assets["numero-1"].kind == "images"
    assert scan.assets["numero-1"].paths == (image,)


def test_numero_10_jpg_no_se_confunde_con_numero_1(tmp_path: Path) -> None:
    _touch(tmp_path, "numero-1.jpg", "numero-10.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert _names(scan.assets["numero-1"].paths) == ["numero-1.jpg"]
    assert _names(scan.assets["numero-10"].paths) == ["numero-10.jpg"]


def test_secuencia_de_imagenes_en_orden(tmp_path: Path) -> None:
    _touch(tmp_path, "gracias__3.jpg", "gracias__1.jpg", "gracias__2.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert scan.assets["gracias"].kind == "images"
    assert _names(scan.assets["gracias"].paths) == [
        "gracias__1.jpg",
        "gracias__2.jpg",
        "gracias__3.jpg",
    ]


def test_secuencia_del_slug_numero_1_con_doble_guion_bajo(tmp_path: Path) -> None:
    _touch(tmp_path, "numero-1__1.jpg", "numero-1__2.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert _names(scan.assets["numero-1"].paths) == ["numero-1__1.jpg", "numero-1__2.jpg"]


def test_secuencia_de_cuatro_cuadros_es_el_maximo(tmp_path: Path) -> None:
    _touch(tmp_path, *(f"gracias__{n}.jpg" for n in range(1, MAX_FRAMES + 1)))

    scan = scan_raw(tmp_path, SLUGS)

    assert MAX_FRAMES == 4
    assert scan.errors == []
    assert len(scan.assets["gracias"].paths) == 4


# ---------- scan_raw: ignorados ----------


def test_gitkeep_y_archivos_ocultos_se_ignoran(tmp_path: Path) -> None:
    _touch(tmp_path, ".gitkeep", ".DS_Store", ".hola.mp4")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.assets == {}
    assert scan.errors == []
    assert scan.warnings == []


def test_subcarpetas_se_ignoran(tmp_path: Path) -> None:
    _touch(tmp_path / "viejos", "hola.mp4")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.assets == {}
    assert scan.errors == []


def test_carpeta_vacia(tmp_path: Path) -> None:
    scan = scan_raw(tmp_path, SLUGS)

    assert scan.assets == {}
    assert scan.errors == []
    assert scan.warnings == []


def test_extension_desconocida_se_ignora_con_advertencia(tmp_path: Path) -> None:
    _touch(tmp_path, "hola.txt")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.assets == {}
    assert scan.errors == []
    assert len(scan.warnings) == 1
    assert "hola.txt" in scan.warnings[0]


# ---------- scan_raw: errores ----------


def test_nombre_sin_slug_da_error_con_sugerencia_b32(tmp_path: Path) -> None:
    _touch(tmp_path, "Gracia.mp4")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.assets == {}
    assert scan.errors == [
        'raw/Gracia.mp4 no corresponde a ninguna seña. ¿Quisiste decir "gracias"?'
    ]


def test_nombre_sin_slug_ni_parecido_da_error_sin_sugerencia(tmp_path: Path) -> None:
    _touch(tmp_path, "xyz.mp4")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.assets == {}
    assert scan.errors == ["raw/xyz.mp4 no corresponde a ninguna seña."]


def test_nombre_con_espacio_sugiere_slug_con_guion(tmp_path: Path) -> None:
    _touch(tmp_path, "buenos dias.mp4")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.assets == {}
    assert scan.errors == [
        'raw/buenos dias.mp4 no corresponde a ninguna seña. ¿Quisiste decir "buenos-dias"?'
    ]


def test_nombre_con_guion_bajo_simple_sugiere_slug_con_guion(tmp_path: Path) -> None:
    _touch(tmp_path, "buenos_dias.mp4")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.assets == {}
    assert scan.errors == [
        'raw/buenos_dias.mp4 no corresponde a ninguna seña. ¿Quisiste decir "buenos-dias"?'
    ]


def test_numero__1_sin_slug_numero_es_error_b90(tmp_path: Path) -> None:
    _touch(tmp_path, "numero__1.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert "numero" not in scan.assets
    assert "numero-1" not in scan.assets
    assert len(scan.errors) == 1
    assert "numero__1.jpg" in scan.errors[0]
    assert "no corresponde a ninguna seña" in scan.errors[0]


def test_secuencia_con_hueco_da_error_exacto(tmp_path: Path) -> None:
    _touch(tmp_path, "gracias__1.jpg", "gracias__3.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert "gracias" not in scan.assets
    assert scan.errors == [
        "Faltan imágenes en la secuencia de «gracias»: hay __1 y __3, falta __2."
    ]


def test_secuencia_que_no_empieza_en_1_da_error(tmp_path: Path) -> None:
    _touch(tmp_path, "gracias__2.jpg", "gracias__3.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert "gracias" not in scan.assets
    assert len(scan.errors) == 1
    assert "gracias" in scan.errors[0]


def test_mas_de_cuatro_cuadros_da_error(tmp_path: Path) -> None:
    _touch(tmp_path, *(f"gracias__{n}.jpg" for n in range(1, 6)))

    scan = scan_raw(tmp_path, SLUGS)

    assert "gracias" not in scan.assets
    assert len(scan.errors) == 1
    assert "gracias" in scan.errors[0]


def test_imagen_sola_y_secuencia_a_la_vez_da_error(tmp_path: Path) -> None:
    _touch(tmp_path, "gracias.jpg", "gracias__1.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert "gracias" not in scan.assets
    assert len(scan.errors) == 1
    assert "gracias" in scan.errors[0]


def test_heic_da_error_con_instrucciones_b94(tmp_path: Path) -> None:
    _touch(tmp_path, "gracias.heic")

    scan = scan_raw(tmp_path, SLUGS)

    assert "gracias" not in scan.assets
    assert len(scan.errors) == 1
    assert scan.errors[0] in {
        HEIC_MESSAGE.format(name="raw/gracias.heic"),
        HEIC_MESSAGE.format(name="gracias.heic"),
    }
    assert "Exporta la foto como JPG" in scan.errors[0]
    assert "Ajustes → Cámara → Formatos → Más compatible" in scan.errors[0]


def test_heif_en_mayusculas_tambien_da_error_heic(tmp_path: Path) -> None:
    _touch(tmp_path, "letra-a.HEIF")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.assets == {}
    assert len(scan.errors) == 1
    assert "el formato HEIC no es compatible" in scan.errors[0]


def test_dos_videos_de_la_misma_sena_da_error(tmp_path: Path) -> None:
    _touch(tmp_path, "hola.mp4", "hola.mov")

    scan = scan_raw(tmp_path, SLUGS)

    assert "hola" not in scan.assets
    assert len(scan.errors) == 1
    assert "hola" in scan.errors[0]


def test_un_error_no_impide_procesar_las_demas_senas(tmp_path: Path) -> None:
    _touch(tmp_path, "Gracia.mp4", "hola.mp4", "gracias.heic")

    scan = scan_raw(tmp_path, SLUGS)

    assert set(scan.assets) == {"hola"}
    assert len(scan.errors) == 2


# ---------- scan_raw: prioridad video > imágenes (B95) ----------


def test_video_e_imagen_de_la_misma_sena_usa_el_video_y_advierte(tmp_path: Path) -> None:
    video, _ = _touch(tmp_path, "hola.mp4", "hola.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert scan.assets["hola"].kind == "video"
    assert scan.assets["hola"].paths == (video,)
    assert len(scan.warnings) == 1
    assert "hola" in scan.warnings[0]


def test_video_y_secuencia_de_la_misma_sena_usa_el_video(tmp_path: Path) -> None:
    video, _, _ = _touch(tmp_path, "gracias.webm", "gracias__1.jpg", "gracias__2.jpg")

    scan = scan_raw(tmp_path, SLUGS)

    assert scan.errors == []
    assert scan.assets["gracias"].kind == "video"
    assert scan.assets["gracias"].paths == (video,)
    assert any("gracias" in w for w in scan.warnings)


def test_la_prioridad_no_depende_del_orden_de_creacion(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    _touch(first, "hola.jpg", "hola.mp4")
    _touch(second, "hola.mp4", "hola.jpg")

    assert scan_raw(first, SLUGS).assets["hola"].kind == "video"
    assert scan_raw(second, SLUGS).assets["hola"].kind == "video"
