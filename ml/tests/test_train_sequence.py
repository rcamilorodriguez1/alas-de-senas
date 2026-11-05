# ruff: noqa: S101 — son pruebas de pytest; ml/ queda fuera de la configuración de pruebas de la raíz
"""Datos, aumentos y paridad de `train_sequence.py` (tarea 10B.7, anexo A.8). Sin TensorFlow.

Ejecutar:  uv run --no-project --with pytest --with numpy pytest ml/tests
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from train_sequence import (
    BLENDSHAPES,
    BLENDSHAPES_AT,
    DOMINANT,
    FEATURE_SIZE,
    FRAMES,
    HAND_FACE,
    NON_DOMINANT,
    PRESENCE,
    SHAPE,
    DatasetError,
    augment,
    change_speed,
    label_order,
    load_datasets,
    mask_face,
    mirror_frames,
    normalize,
    person_folds,
    rotate_scale,
    select_labels,
    summarize,
)

ML = Path(__file__).resolve().parent.parent
SIGNS = ML.parent / "content" / "signs.csv"
CASES = ML / "fixtures" / "holistic_v2_cases.json"


def frames(value: float = 0.1) -> list[list[float]]:
    row = [value] * FEATURE_SIZE
    row[DOMINANT + PRESENCE] = 1
    row[NON_DOMINANT + PRESENCE] = 1
    return [row[:] for _ in range(FRAMES)]


def sample(label: str = "hola", collector: str = "p1", **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "x",
        "label": label,
        "collector": collector,
        "dominantHand": "right",
        "source": "LSC-54",
        "license": "CC BY-NC 4.0",
        "quality": {"faceRatio": 1, "domHandRatio": 1, "poseRatio": 1},
        "data": frames(),
    }
    base.update(overrides)
    return base


def write(path: Path, samples: list[dict[str, object]], **overrides: object) -> Path:
    content: dict[str, object] = {
        "format": "alas-dataset",
        "featureVersion": "holistic-v2",
        "featureSize": 159,
        "frames": 30,
        "durationSec": 2.0,
        "faceFeatures": True,
        "createdWith": {"tasksVision": "1.1.0", "app": "test"},
        "samples": samples,
    }
    content.update(overrides)
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


# ---------- Paridad Python ↔ TypeScript (H11) ----------


def test_los_casos_de_paridad_coinciden_con_python() -> None:
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    assert payload["featureSize"] == FEATURE_SIZE
    assert len(payload["cases"]) >= 3
    for case in payload["cases"]:
        frame = np.array(case["frame"], dtype=np.float32)
        mean = np.array(case["mean"], dtype=np.float32).astype(np.float64)
        std = np.array(case["std"], dtype=np.float32).astype(np.float64)
        np.testing.assert_array_equal(
            mirror_frames(frame), np.array(case["mirror"], dtype=np.float32)
        )
        np.testing.assert_array_equal(
            mask_face(frame), np.array(case["maskFace"], dtype=np.float32)
        )
        np.testing.assert_allclose(
            normalize(frame, mean, std), case["normalize"], rtol=1e-6, atol=1e-6
        )


def test_reflejo_dos_veces_es_el_original_e_intercambia_blendshapes() -> None:
    x = np.random.default_rng(1).normal(size=(FRAMES, FEATURE_SIZE)).astype(np.float32)
    np.testing.assert_array_equal(mirror_frames(mirror_frames(x)), x)
    left, right = BLENDSHAPES.index("browDownLeft"), BLENDSHAPES.index("browDownRight")
    assert mirror_frames(x)[0, BLENDSHAPES_AT + left] == x[0, BLENDSHAPES_AT + right]
    assert mirror_frames(x)[0, DOMINANT + SHAPE] == -x[0, DOMINANT + SHAPE]


def test_normalizar_trata_desviaciones_nulas_como_1() -> None:
    mean, std = np.zeros(FEATURE_SIZE), np.zeros(FEATURE_SIZE)
    np.testing.assert_allclose(normalize(np.full(FEATURE_SIZE, 3.0), mean, std), 3.0)


# ---------- Carga y validación (H5) ----------


def test_carga_un_dataset_valido(tmp_path: Path) -> None:
    path = write(tmp_path / "a.json", [sample(), sample("NINGUNA", "p2")])
    seqs = load_datasets([path], SIGNS)
    assert seqs.data.shape == (2, FRAMES, FEATURE_SIZE)
    assert seqs.labels == ["hola", "NINGUNA"]
    assert seqs.collectors == ["LSC-54:p1", "LSC-54:p2"]
    assert seqs.face_features is True


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"featureVersion": "hand-v1"}, "featureVersion"),
        ({"featureSize": 63}, "cuadros"),
        ({"frames": 20}, "cuadros"),
        ({"format": "otro"}, "no es un dataset"),
    ],
)
def test_rechaza_otra_version_u_otro_tamano(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(DatasetError, match=message):
        load_datasets([write(tmp_path / "a.json", [sample()], **overrides)], SIGNS)


def test_no_mezcla_versiones_mayores_de_tasks_vision(tmp_path: Path) -> None:
    a = write(tmp_path / "a.json", [sample()])
    b = write(tmp_path / "b.json", [sample()], createdWith={"tasksVision": "2.0.0", "app": "x"})
    with pytest.raises(DatasetError, match="versión mayor"):
        load_datasets([a, b], SIGNS)


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ({"label": "no-existe"}, "signs.csv"),
        ({"source": ""}, "source"),
        ({"license": " "}, "license"),
        ({"collector": ""}, "collector"),
        ({"data": [[0.0] * 159] * 29}, "números"),
        ({"data": "x"}, "números"),
    ],
)
def test_rechaza_muestras_invalidas(tmp_path: Path, bad: dict[str, object], message: str) -> None:
    with pytest.raises(DatasetError, match=message):
        load_datasets([write(tmp_path / "a.json", [sample(**bad)])], SIGNS)


def test_sin_expresion_facial_se_enmascaran_los_blendshapes(tmp_path: Path) -> None:
    seqs = load_datasets([write(tmp_path / "a.json", [sample()], faceFeatures=False)], SIGNS)
    assert seqs.face_features is False
    # Todo lo que depende de la cara: mano-cara (6), blendshapes (18) y presencia (1).
    assert not seqs.data[..., HAND_FACE:].any()
    assert seqs.data[..., :HAND_FACE].any()


def test_seleccion_de_senas_y_orden_de_etiquetas(tmp_path: Path) -> None:
    path = write(tmp_path / "a.json", [sample("hola"), sample("adios"), sample("NINGUNA")])
    seqs = load_datasets([path], SIGNS)
    assert select_labels(seqs, ["hola"], others_as_none=False).labels == ["hola", "NINGUNA"]
    assert select_labels(seqs, ["hola"], others_as_none=True).labels == [
        "hola",
        "NINGUNA",
        "NINGUNA",
    ]
    assert label_order(["hola", "NINGUNA", "adios"]) == ["NINGUNA", "adios", "hola"]


# ---------- Aumentos y separación por persona ----------


def test_aumentos_conservan_forma_y_presencias_binarias() -> None:
    x = np.array(frames(0.3), dtype=np.float32)
    x[10:, NON_DOMINANT : NON_DOMINANT + PRESENCE + 1] = 0  # la otra mano se va
    out = augment(x, np.random.default_rng(3), face_features=False)
    assert out.shape == (FRAMES, FEATURE_SIZE)
    assert set(np.unique(out[:, DOMINANT + PRESENCE])) <= {0.0, 1.0}
    absent = out[:, NON_DOMINANT + PRESENCE] == 0
    assert not out[absent, NON_DOMINANT : NON_DOMINANT + PRESENCE].any()
    assert not out[..., BLENDSHAPES_AT : BLENDSHAPES_AT + len(BLENDSHAPES)].any()


def test_velocidad_1_y_rotacion_0_no_cambian_nada() -> None:
    x = np.random.default_rng(4).normal(size=(FRAMES, FEATURE_SIZE)).astype(np.float32)
    x[:, DOMINANT + PRESENCE] = 1
    x[:, NON_DOMINANT + PRESENCE] = 1
    x[:, -1] = 1
    np.testing.assert_allclose(change_speed(x, 1.0), x, atol=1e-6)
    np.testing.assert_allclose(rotate_scale(x, 0.0, 1.0), x, atol=1e-6)
    turned = rotate_scale(x, np.pi / 2, 1.0)
    np.testing.assert_allclose(turned[:, HAND_FACE], -x[:, HAND_FACE + 1], atol=1e-6)


def test_pliegues_por_persona_sin_repetir() -> None:
    people = [f"p{i}" for i in range(18)]
    folds = person_folds(people * 3, 6)
    assert len(folds) == 6
    assert set().union(*folds) == set(people)
    assert sum(len(f) for f in folds) == 18


def test_resumen_para_tomi() -> None:
    x = np.zeros((2, FEATURE_SIZE), dtype=np.float32)
    assert summarize(x) is None
    x[:, DOMINANT + PRESENCE] = 1
    x[:, HAND_FACE : HAND_FACE + 2] = [3, 4]
    summary = summarize(x)
    assert summary is not None
    assert summary["handFace"] == pytest.approx(5)
