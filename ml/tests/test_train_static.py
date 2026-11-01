# ruff: noqa: S101 — son pruebas de pytest; ml/ queda fuera de la configuración de pruebas de la raíz
"""Validación de datos de `train_static.py` (tarea 10.6, §10.5). No necesita TensorFlow.

Ejecutar:  uv run --no-project --with pytest pytest ml/tests
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from train_static import (
    FEATURE_SIZE,
    DatasetError,
    expand_paths,
    label_order,
    load_datasets,
    static_labels,
)

ROOT = Path(__file__).resolve().parent.parent.parent
SIGNS = ROOT / "content" / "signs.csv"


def write(path: Path, samples: list[dict[str, object]], **overrides: object) -> Path:
    data = {
        "featureVersion": "hand-v1",
        "featureSize": FEATURE_SIZE,
        "collector": "ana",
        "tasksVision": "1.1.0",
        "createdAt": "2026-11-03T15:00:00Z",
        "samples": samples,
        **overrides,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def vector(value: float = 0.1) -> list[float]:
    return [value] * FEATURE_SIZE


def test_signs_csv_marca_letras_estaticas_y_con_movimiento() -> None:
    static, dynamic = static_labels(SIGNS)
    assert "letra-a" in static
    assert {"letra-j", "letra-z"} <= dynamic
    assert not static & dynamic


def test_carga_muestras_validas(tmp_path: Path) -> None:
    path = write(
        tmp_path / "a.json",
        [
            {"label": "letra-a", "features": vector()},
            {"label": "NINGUNA", "features": vector(0)},
        ],
    )
    samples = load_datasets([path], SIGNS)
    assert samples.labels == ["letra-a", "NINGUNA"]
    assert samples.collectors == ["ana", "ana"]
    assert len(samples.features[0]) == FEATURE_SIZE


def test_descarta_las_letras_con_movimiento_sin_perder_el_resto(tmp_path: Path) -> None:
    path = write(
        tmp_path / "a.json",
        [
            {"label": "letra-j", "features": vector()},
            {"label": "letra-a", "features": vector()},
            {"label": "NINGUNA", "features": vector()},
        ],
    )
    samples = load_datasets([path], SIGNS)
    assert samples.labels == ["letra-a", "NINGUNA"]
    assert samples.skipped_dynamic == {"letra-j": 1}


def test_rechaza_booleanos_como_numeros(tmp_path: Path) -> None:
    path = write(tmp_path / "a.json", [{"label": "letra-a", "features": [True] * FEATURE_SIZE}])
    with pytest.raises(DatasetError, match="números finitos"):
        load_datasets([path], SIGNS)


def test_json_mal_formado_da_un_error_claro(tmp_path: Path) -> None:
    path = tmp_path / "roto.json"
    path.write_text("{no es json", encoding="utf-8")
    with pytest.raises(DatasetError, match="no es un JSON válido"):
        load_datasets([path], SIGNS)


def test_rechaza_etiquetas_desconocidas(tmp_path: Path) -> None:
    path = write(tmp_path / "a.json", [{"label": "hola", "features": vector()}])
    with pytest.raises(DatasetError, match="no es una letra estática"):
        load_datasets([path], SIGNS)


@pytest.mark.parametrize("overrides", [{"featureVersion": "hand-v0"}, {"featureSize": 42}])
def test_rechaza_otra_version_de_rasgos(tmp_path: Path, overrides: dict[str, object]) -> None:
    path = write(tmp_path / "a.json", [{"label": "NINGUNA", "features": vector()}], **overrides)
    with pytest.raises(DatasetError, match="featureVersion"):
        load_datasets([path], SIGNS)


@pytest.mark.parametrize(
    "features", [[0.1] * 62, ["x"] * FEATURE_SIZE, [float("nan")] * FEATURE_SIZE]
)
def test_rechaza_vectores_invalidos(tmp_path: Path, features: list[object]) -> None:
    path = write(tmp_path / "a.json", [{"label": "letra-a", "features": features}])
    with pytest.raises(DatasetError, match="números finitos"):
        load_datasets([path], SIGNS)


def test_exige_alias_de_quien_grabo(tmp_path: Path) -> None:
    path = write(tmp_path / "a.json", [{"label": "NINGUNA", "features": vector()}], collector=" ")
    with pytest.raises(DatasetError, match="alias"):
        load_datasets([path], SIGNS)


def test_exige_al_menos_dos_clases(tmp_path: Path) -> None:
    path = write(tmp_path / "a.json", [{"label": "letra-a", "features": vector()}])
    with pytest.raises(DatasetError, match="2 clases"):
        load_datasets([path], SIGNS)


def test_sin_archivos_explica_como_pasarlos() -> None:
    with pytest.raises(DatasetError, match="--data"):
        load_datasets([], SIGNS)


def test_expande_comodines_en_windows(tmp_path: Path) -> None:
    write(tmp_path / "a.json", [])
    write(tmp_path / "b.json", [])
    assert [p.name for p in expand_paths([str(tmp_path / "*.json")])] == ["a.json", "b.json"]


def test_orden_de_etiquetas_estable() -> None:
    assert label_order(["letra-b", "NINGUNA", "letra-a", "letra-b"]) == [
        "NINGUNA",
        "letra-a",
        "letra-b",
    ]


def test_acepta_numeros_estaticos_y_descarta_los_de_movimiento(tmp_path: Path) -> None:
    """D-019: numero-1 a numero-5 son static en signs.csv; del 6 al 10, dynamic."""
    path = write(
        tmp_path / "n.json",
        [
            {"label": "numero-3", "features": vector()},
            {"label": "numero-8", "features": vector()},
            {"label": "NINGUNA", "features": vector()},
        ],
    )
    samples = load_datasets([path], SIGNS)
    assert samples.labels == ["numero-3", "NINGUNA"]
    assert samples.skipped_dynamic == {"numero-8": 1}


def test_persona_por_muestra_para_videos_de_varias_personas(tmp_path: Path) -> None:
    path = write(
        tmp_path / "v.json",
        [
            {"label": "numero-1", "features": vector(), "collector": "p1"},
            {"label": "NINGUNA", "features": vector(), "collector": "p17"},
        ],
        collector="",
    )
    samples = load_datasets([path], SIGNS)
    assert samples.collectors == ["p1", "p17"]
