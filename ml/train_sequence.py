"""Entrena el modelo de señas con movimiento `holistic-v2` (anexo A.8): secuencias [30, 159].

Uso:
    uv run --project ml python ml/train_sequence.py --data ml/data/holistic/*.json \\
        --out apps/web/public/models/lsc-gestos [--labels hola adios --cv 6]

Python NUNCA recalcula puntos (D11): entrena sobre los números que exportó el navegador con
`buildHolisticFrame` + `FrameSequencer`. Las únicas operaciones repetidas en TypeScript son el
reflejo, la máscara facial y la normalización; las dos implementaciones pasan los mismos casos de
`ml/fixtures/holistic_v2_cases.json` (H11). Las funciones de datos solo usan NumPy (se prueban sin
TensorFlow); TensorFlow se importa dentro de `train`.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from train_static import expand_paths, export_tfjs, save_confusion

FEATURE_VERSION = "holistic-v2"
FEATURE_SIZE = 159
FRAMES = 30
DURATION_SEC = 2.0
NONE_LABEL = "NINGUNA"
THRESHOLD = 0.7
SEED = 42
EPOCHS = 120
ROOT = Path(__file__).resolve().parent.parent

# Mismo diseño que apps/web/src/camera/holistic/frame.ts (A.3.3).
HAND_POINTS = 21
SHAPE = HAND_POINTS * 3  # 63
PRESENCE = SHAPE + 3  # 66: presencia dentro de un bloque de mano
HAND_BLOCK = PRESENCE + 1  # 67
DOMINANT = 0
NON_DOMINANT = HAND_BLOCK
HAND_FACE = 2 * HAND_BLOCK  # 134
BLENDSHAPES_AT = HAND_FACE + 6  # 140
BLENDSHAPES = [
    "browDownLeft",
    "browDownRight",
    "browInnerUp",
    "browOuterUpLeft",
    "browOuterUpRight",
    "eyeSquintLeft",
    "eyeSquintRight",
    "eyeWideLeft",
    "eyeWideRight",
    "jawOpen",
    "mouthFunnel",
    "mouthPucker",
    "mouthSmileLeft",
    "mouthSmileRight",
    "mouthFrownLeft",
    "mouthFrownRight",
    "mouthPressLeft",
    "cheekPuff",
]
FACE_PRESENCE = BLENDSHAPES_AT + len(BLENDSHAPES)  # 158
MIN_STD = 1e-6
BROW_UP = BLENDSHAPES_AT + BLENDSHAPES.index("browInnerUp")

MIRROR_PAIRS = [
    (i, BLENDSHAPES.index(name[: -len("Left")] + "Right"))
    for i, name in enumerate(BLENDSHAPES)
    if name.endswith("Left") and name[: -len("Left")] + "Right" in BLENDSHAPES
]
X_INDICES = [
    *(block + p * 3 for block in (DOMINANT, NON_DOMINANT) for p in range(HAND_POINTS)),
    DOMINANT + SHAPE,
    NON_DOMINANT + SHAPE,
    HAND_FACE,
    HAND_FACE + 3,
]
# Pares (x, y) que gira el aumento de rotación: forma de las manos, posiciones y mano-cara.
XY_PAIRS = [
    *(
        (block + p * 3, block + p * 3 + 1)
        for block in (DOMINANT, NON_DOMINANT)
        for p in range(HAND_POINTS)
    ),
    (DOMINANT + SHAPE, DOMINANT + SHAPE + 1),
    (NON_DOMINANT + SHAPE, NON_DOMINANT + SHAPE + 1),
    (HAND_FACE, HAND_FACE + 1),
    (HAND_FACE + 3, HAND_FACE + 4),
]
POSITION_INDICES = [
    *range(DOMINANT + SHAPE, DOMINANT + SHAPE + 3),
    *range(NON_DOMINANT + SHAPE, NON_DOMINANT + SHAPE + 3),
    *range(HAND_FACE, HAND_FACE + 6),
]


class DatasetError(ValueError):
    """Datos inválidos: se explica en español qué archivo y qué falla."""


@dataclass(frozen=True)
class Sequences:
    data: np.ndarray  # [N, 30, 159] float32
    labels: list[str]
    collectors: list[str]
    face_features: bool
    sources: dict[str, int]


# ---------- Operaciones compartidas con TypeScript (paridad H11) ----------


def mirror_frames(x: np.ndarray) -> np.ndarray:
    """x → -x en todos los bloques e intercambio de blendshapes L/R; dos veces = original (H2)."""
    out = np.array(x, dtype=np.float32, copy=True)
    out[..., X_INDICES] = -out[..., X_INDICES]
    out[..., X_INDICES] += 0.0  # -0 → 0, igual que en TypeScript
    for a, b in MIRROR_PAIRS:
        out[..., BLENDSHAPES_AT + a] = x[..., BLENDSHAPES_AT + b]
        out[..., BLENDSHAPES_AT + b] = x[..., BLENDSHAPES_AT + a]
    return out


def mask_face(x: np.ndarray) -> np.ndarray:
    """Sin rostro (caras pixeladas): mano-cara, 18 blendshapes y presencia de cara en 0."""
    out = np.array(x, dtype=np.float32, copy=True)
    out[..., HAND_FACE : FACE_PRESENCE + 1] = 0
    return out


def normalize(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """(x - media) / desviación; desviaciones casi nulas cuentan como 1."""
    safe = np.where(std > MIN_STD, std, 1.0)
    return ((np.asarray(x, dtype=np.float64) - mean) / safe).astype(np.float32)


def summarize(frames: np.ndarray) -> dict[str, float] | None:
    """Promedios para la retroalimentación de Tomi (misma fórmula que feedback.ts)."""
    present = frames[frames[:, DOMINANT + PRESENCE] >= 0.5]
    if len(present) == 0:
        return None
    return {
        "handFace": float(np.hypot(present[:, HAND_FACE], present[:, HAND_FACE + 1]).mean()),
        "handY": float(present[:, DOMINANT + SHAPE + 1].mean()),
        "browUp": float(present[:, BROW_UP].mean()),
    }


# ---------- Carga y validación (H5) ----------


def curriculum_slugs(signs_csv: Path) -> set[str]:
    with signs_csv.open(encoding="utf-8", newline="") as handle:
        return {row["slug"] for row in csv.DictReader(handle)}


def _major(version: object) -> str:
    return str(version).split(".", 1)[0] if version else ""


def load_datasets(paths: list[Path], signs_csv: Path) -> Sequences:
    """Rechaza otra featureVersion, otro tamaño, otra versión mayor de tasks-vision, muestras sin
    fuente o licencia y etiquetas fuera del currículo (avisa y no mezcla)."""
    if not paths:
        raise DatasetError("No se encontraron archivos dataset.json.")
    slugs = curriculum_slugs(signs_csv) | {NONE_LABEL}
    data: list[np.ndarray] = []
    labels: list[str] = []
    collectors: list[str] = []
    sources: Counter[str] = Counter()
    majors: set[str] = set()
    face_features = True
    for path in paths:
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DatasetError(f"{path.name}: no es un JSON válido ({exc}).") from exc
        if not isinstance(content, dict) or content.get("format") != "alas-dataset":
            raise DatasetError(f"{path.name}: no es un dataset de Alas de Señas.")
        if content.get("featureVersion") != FEATURE_VERSION:
            raise DatasetError(
                f"{path.name}: featureVersion «{content.get('featureVersion')}», "
                f"se esperaba «{FEATURE_VERSION}»."
            )
        if content.get("featureSize") != FEATURE_SIZE or content.get("frames") != FRAMES:
            raise DatasetError(
                f"{path.name}: se esperaban {FRAMES} cuadros de {FEATURE_SIZE} valores."
            )
        created = content.get("createdWith")
        majors.add(_major(created.get("tasksVision") if isinstance(created, dict) else None))
        if len(majors) > 1:
            raise DatasetError(
                f"{path.name}: otra versión mayor de MediaPipe tasks-vision "
                f"({sorted(majors)}); no se mezclan."
            )
        if content.get("faceFeatures") is False:
            face_features = False
        samples = content.get("samples")
        if not isinstance(samples, list):
            raise DatasetError(f"{path.name}: falta la lista «samples».")
        for i, sample in enumerate(samples):
            where = f"{path.name}, muestra {i + 1}"
            if not isinstance(sample, dict):
                raise DatasetError(f"{where}: no es un objeto.")
            label = sample.get("label")
            if label not in slugs:
                raise DatasetError(f"{where}: la etiqueta «{label}» no está en content/signs.csv.")
            source, license_ = sample.get("source"), sample.get("license")
            if (
                not isinstance(source, str)
                or not source.strip()
                or not isinstance(license_, str)
                or not license_.strip()
            ):
                raise DatasetError(f"{where}: «source» y «license» son obligatorios (A.6).")
            collector = sample.get("collector")
            if not isinstance(collector, str) or not collector.strip():
                raise DatasetError(f"{where}: falta el alias «collector».")
            try:
                frames = np.asarray(sample.get("data"), dtype=np.float32)
            except (TypeError, ValueError) as exc:
                raise DatasetError(f"{where}: «data» no son números.") from exc
            if frames.shape != (FRAMES, FEATURE_SIZE) or not np.isfinite(frames).all():
                raise DatasetError(
                    f"{where}: se esperaban {FRAMES} por {FEATURE_SIZE} números finitos."
                )
            data.append(frames)
            labels.append(str(label))
            collectors.append(f"{source}:{collector}")
            sources[str(source)] += 1
    stacked = np.stack(data)
    if not face_features:
        stacked = mask_face(stacked)
    return Sequences(stacked, labels, collectors, face_features, dict(sources))


def select_labels(seqs: Sequences, keep: list[str] | None, others_as_none: bool) -> Sequences:
    """Se queda con las señas pedidas (+ NINGUNA); las demás se descartan o pasan a NINGUNA."""
    if not keep:
        return seqs
    wanted = set(keep) | {NONE_LABEL}
    rows: list[int] = []
    labels: list[str] = []
    for i, label in enumerate(seqs.labels):
        if label in wanted:
            rows.append(i)
            labels.append(label)
        elif others_as_none:
            rows.append(i)
            labels.append(NONE_LABEL)
    return Sequences(
        seqs.data[rows],
        labels,
        [seqs.collectors[i] for i in rows],
        seqs.face_features,
        seqs.sources,
    )


def label_order(labels: list[str]) -> list[str]:
    """NINGUNA primero y luego orden alfabético: índice estable de cada salida."""
    rest = sorted(set(labels) - {NONE_LABEL})
    return [NONE_LABEL, *rest] if NONE_LABEL in labels else rest


# ---------- Aumentos (solo en entrenamiento, A.8) ----------


def _binarize(seq: np.ndarray) -> np.ndarray:
    for block in (DOMINANT, NON_DOMINANT):
        present = seq[:, block + PRESENCE] >= 0.5
        seq[~present, block : block + HAND_BLOCK] = 0
        seq[present, block + PRESENCE] = 1
    seq[:, FACE_PRESENCE] = (seq[:, FACE_PRESENCE] >= 0.5).astype(np.float32)
    return seq


def change_speed(seq: np.ndarray, factor: float) -> np.ndarray:
    """Reproduce la seña más rápido (>1) o más lento (<1) alrededor del centro, con 30 cuadros."""
    center = (FRAMES - 1) / 2
    src = np.clip((np.arange(FRAMES) - center) * factor + center, 0, FRAMES - 1)
    low = np.floor(src).astype(int)
    high = np.minimum(low + 1, FRAMES - 1)
    w = (src - low)[:, None]
    return _binarize((seq[low] * (1 - w) + seq[high] * w).astype(np.float32))


def rotate_scale(seq: np.ndarray, angle: float, scale: float) -> np.ndarray:
    """Gira el plano de la imagen (manos y posiciones) y escala las posiciones del cuerpo."""
    out = seq.copy()
    cos, sin = np.cos(angle), np.sin(angle)
    for ix, iy in XY_PAIRS:
        x, y = seq[:, ix], seq[:, iy]
        out[:, ix] = x * cos - y * sin
        out[:, iy] = x * sin + y * cos
    out[:, POSITION_INDICES] *= scale
    return out


def augment(seq: np.ndarray, rng: np.random.Generator, face_features: bool) -> np.ndarray:
    out = change_speed(seq, float(rng.uniform(0.8, 1.2)))
    out = rotate_scale(out, float(np.deg2rad(rng.uniform(-10, 10))), float(rng.uniform(0.9, 1.1)))
    noise = rng.normal(0, 0.02, out.shape).astype(np.float32)
    for block in (DOMINANT, NON_DOMINANT):
        present = out[:, block + PRESENCE] >= 0.5
        out[present, block : block + PRESENCE] += noise[present, block : block + PRESENCE]
    if rng.random() < 0.5:
        out = mirror_frames(out)
    if not face_features:
        out = mask_face(out)
    return out


def person_folds(collectors: list[str], k: int) -> list[set[str]]:
    """k grupos de personas (semilla fija): cada persona valida en un solo pliegue."""
    people = sorted(set(collectors))
    random.Random(SEED).shuffle(people)  # noqa: S311 — separación reproducible
    folds = max(2, min(k, len(people)))
    return [set(people[i::folds]) for i in range(folds)]


def fold_split(
    collectors: np.ndarray, held: set[str], k: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Máscaras (ajuste, parada temprana, evaluación) de un pliegue, con personas disjuntas.

    La parada temprana elige la época con personas del propio entrenamiento: si mirara a las
    evaluadas, el acierto «con personas no vistas» saldría optimista (revisión de D-045).
    """
    val = np.isin(collectors, list(held))
    inner = person_folds([str(c) for c in collectors[~val]], k)[0]
    stop = ~val & np.isin(collectors, list(inner))
    return ~val & ~stop, stop, val


def balanced_weights(y: np.ndarray, classes: int) -> dict[int, float]:
    """Peso por clase: cada una aporta lo mismo a la pérdida (NINGUNA suele tener más).

    Keras exige todas las claves de 0 a n-1: una clase ausente en el pliegue lleva peso 0.
    """
    counts = np.bincount(y, minlength=classes)
    total = float(counts.sum())
    return {c: total / (classes * float(n)) if n else 0.0 for c, n in enumerate(counts)}


# ---------- Evaluación con la decisión real de la app (plan de mejora, etapa 5; D-045) ----------


def app_decision(probs: np.ndarray, threshold: float, none_index: int) -> np.ndarray:
    """Igual que `decide` en sequence-classifier.ts: bajo el umbral, NINGUNA («no reconocida»)."""
    # En double, como JavaScript lee los Float32Array: float32(0,7) queda bajo 0,7 en ambos.
    wide = probs.astype(np.float64)
    best = wide.argmax(axis=1)
    confident = wide.max(axis=1) + 1e-9 >= threshold
    return np.where(confident, best, none_index)


class ClassRow(TypedDict):
    label: str
    samples: int
    recall: float
    precision: float
    rejected: int
    confusedWith: dict[str, int]  # clave del JSON en camelCase


class EvaluationReport(TypedDict):
    accuracy: float
    falseDetections: float
    minRecall: float
    minSamples: int
    classes: list[ClassRow]
    publishable: list[str]


def class_report(
    real: np.ndarray,
    decided: np.ndarray,
    classes: list[str],
    min_recall: float,
    min_samples: int,
) -> EvaluationReport:
    """Acierto (recall) y precisión por clase, confusiones, rechazos y falsas detecciones.

    «Publicable» (D-043): una seña llega a `min_recall` con personas no vistas y tiene al menos
    `min_samples` muestras. NINGUNA nunca se publica como seña.
    """
    none = classes.index(NONE_LABEL) if NONE_LABEL in classes else -1
    rows: list[ClassRow] = []
    publishable: list[str] = []
    for i, label in enumerate(classes):
        mine = real == i
        support = int(mine.sum())
        hits = int((decided[mine] == i).sum())
        predicted = int((decided == i).sum())
        recall = hits / support if support else 0.0
        confused = Counter(classes[int(g)] for g in decided[mine] if g != i and g != none)
        rows.append(
            {
                "label": label,
                "samples": support,
                "recall": recall,
                "precision": hits / predicted if predicted else 0.0,
                "rejected": int((decided[mine] == none).sum()) if i != none else 0,
                "confusedWith": dict(sorted(confused.items())),
            }
        )
        if i != none and support >= min_samples and recall + 1e-9 >= min_recall:
            publishable.append(label)
    nothing = real == none
    false_detections = float((decided[nothing] != none).mean()) if nothing.any() else 0.0
    return {
        "accuracy": float((real == decided).mean()) if len(real) else 0.0,
        "falseDetections": false_detections,
        "minRecall": min_recall,
        "minSamples": min_samples,
        "classes": rows,
        "publishable": publishable,
    }


def feature_stats(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    flat = x.reshape(-1, FEATURE_SIZE).astype(np.float64)
    return flat.mean(axis=0), flat.std(axis=0)


# ---------- Entrenamiento ----------


def _build_model(classes: int) -> object:
    import tensorflow as tf

    layers = tf.keras.layers
    model = tf.keras.Sequential(
        [
            layers.Input((FRAMES, FEATURE_SIZE)),
            # reset_after=False es OBLIGATORIO: TensorFlow.js no carga reset_after=True (B73).
            layers.GRU(64, return_sequences=True, reset_after=False),
            layers.GRU(64, reset_after=False),
            layers.Dense(64, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(classes, activation="softmax"),
        ]
    )
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model


def _fit(
    x: np.ndarray,
    y: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    classes: int,
    face: bool,
    copies: int,
    balance: bool = False,
) -> tuple[object, np.ndarray, np.ndarray]:
    import tensorflow as tf

    rng = np.random.default_rng(SEED)
    augmented = [x] + [np.stack([augment(s, rng, face) for s in x]) for _ in range(copies)]
    x_train = np.concatenate(augmented)
    y_train = np.concatenate([y] * (copies + 1))
    # Normalización y pesos solo con el entrenamiento del pliegue: la validación no se filtra.
    mean, std = feature_stats(x)
    model = _build_model(classes)
    model.fit(  # type: ignore[attr-defined]  # modelo de Keras sin tipos
        normalize(x_train, mean, std),
        y_train,
        validation_data=(normalize(x_val, mean, std), y_val),
        epochs=EPOCHS,
        batch_size=32,
        shuffle=True,
        verbose=0,
        class_weight=balanced_weights(y, classes) if balance else None,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=15, restore_best_weights=True)],
    )
    return model, mean, std


def _probs(model: object, x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return np.asarray(model.predict(normalize(x, mean, std), verbose=0))  # type: ignore[attr-defined]  # Keras


def set_seeds() -> None:
    os.environ["PYTHONHASHSEED"] = str(SEED)
    random.seed(SEED)
    np.random.seed(SEED)
    import tensorflow as tf

    tf.random.set_seed(SEED)


def train(
    seqs: Sequences,
    out: Path,
    reports: Path,
    folds: int,
    copies: int,
    balance: bool = False,
    min_recall: float = 0.8,
    min_samples: int = 10,
) -> float:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    set_seeds()
    classes = label_order(seqs.labels)
    index = {label: i for i, label in enumerate(classes)}
    x = seqs.data
    y = np.array([index[label] for label in seqs.labels], dtype=np.int32)
    collectors = np.array(seqs.collectors)
    none_index = index.get(NONE_LABEL, -1)

    # Validación cruzada por persona: cada persona se evalúa sin haberla visto (A.8).
    groups = person_folds(seqs.collectors, folds)
    matrix = np.zeros((len(classes), len(classes)), dtype=int)
    real_all: list[np.ndarray] = []
    decided_all: list[np.ndarray] = []
    hits = 0
    for n, held in enumerate(groups, start=1):
        fit, stop, val = fold_split(collectors, held, folds)
        model, mean, std = _fit(
            x[fit], y[fit], x[stop], y[stop], len(classes), seqs.face_features, copies, balance
        )
        probs = _probs(model, x[val], mean, std)
        guess = probs.argmax(axis=1)
        hits += int((guess == y[val]).sum())
        for real, g in zip(y[val], guess, strict=True):
            matrix[real, g] += 1
        real_all.append(y[val])
        decided_all.append(app_decision(probs, THRESHOLD, none_index))
        print(f"  pliegue {n}/{len(groups)}: {(guess == y[val]).mean():.1%} con {sorted(held)}")
    accuracy = hits / len(y)
    print(f"Precisión con personas no vistas (argmax): {accuracy:.1%}")
    # Lo que vería quien practica: con el umbral de la aplicación, lo dudoso es «no reconocida».
    report = class_report(
        np.concatenate(real_all), np.concatenate(decided_all), classes, min_recall, min_samples
    )
    print(
        f"Con el umbral {THRESHOLD:.2f} de la aplicación: acierto {report['accuracy']:.1%}, "
        f"falsas detecciones de NINGUNA {report['falseDetections']:.1%}"
    )
    for row in report["classes"]:
        print(
            f"  {row['label']:>14}: {row['recall']:.1%} ({row['samples']} muestras, "
            f"{row['rejected']} no reconocidas, confusiones {row['confusedWith']})"
        )
    print(f"Publicables (≥ {min_recall:.0%} y ≥ {min_samples} muestras): {report['publishable']}")

    # Modelo final con todas las personas (la parada temprana mira un pliegue).
    held = groups[0]
    val = np.isin(collectors, list(held))
    model, mean, std = _fit(x, y, x[val], y[val], len(classes), seqs.face_features, copies, balance)
    out.mkdir(parents=True, exist_ok=True)
    export_tfjs(model, out)
    (out / "labels.json").write_text(json.dumps(classes, ensure_ascii=False), encoding="utf-8")
    prototypes = {}
    for label in classes:
        rows = x[[i for i, lab in enumerate(seqs.labels) if lab == label]]
        summary = summarize(rows.reshape(-1, FEATURE_SIZE))
        if summary and label != NONE_LABEL:
            prototypes[label] = summary
    meta = {
        "featureVersion": FEATURE_VERSION,
        "featureSize": FEATURE_SIZE,
        "frames": FRAMES,
        "durationSec": DURATION_SEC,
        "threshold": THRESHOLD,
        "faceFeatures": seqs.face_features,
        "mean": [float(v) for v in mean],
        "std": [float(v) for v in std],
        "labels": classes,
        "prototypes": prototypes,
        "cvAccuracy": accuracy,
        "people": len(set(seqs.collectors)),
        "samples": dict(Counter(seqs.labels)),
        "sources": seqs.sources,
        "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Modelo, labels.json y meta.json en {out}")
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "confusion-gestos.json").write_text(
        json.dumps({"classes": classes, "matrix": matrix.tolist(), "accuracy": accuracy}),
        encoding="utf-8",
    )
    (reports / "reporte-gestos.json").write_text(
        json.dumps(
            {**report, "threshold": THRESHOLD, "balance": balance, "argmaxAccuracy": accuracy},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    try:
        save_confusion(matrix, classes, reports / "confusion-gestos.png")
    except Exception as exc:  # un reporte no puede tumbar el entrenamiento
        print(f"ADVERTENCIA: no se pudo dibujar la matriz de confusión ({exc}).")
        print(matrix)
    return accuracy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Entrena el modelo de gestos holistic-v2 (A.8).")
    parser.add_argument(
        "--data", nargs="+", required=True, help="Archivos dataset.json holistic-v2"
    )
    # Obligatoria (D-045): sin ella, un entrenamiento de prueba sobrescribía el modelo publicado.
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Carpeta del modelo (para publicar: apps/web/public/models/lsc-gestos)",
    )
    parser.add_argument("--signs", type=Path, default=ROOT / "content/signs.csv")
    parser.add_argument("--reports", type=Path, default=ROOT / "ml/reports")
    parser.add_argument("--labels", nargs="*", help="Señas a entrenar (además de NINGUNA)")
    parser.add_argument(
        "--others-as-none", action="store_true", help="Las demás señas cuentan como NINGUNA"
    )
    parser.add_argument("--cv", type=int, default=6, help="Pliegues por persona")
    parser.add_argument("--augment", type=int, default=4, help="Copias aumentadas por muestra")
    parser.add_argument(
        "--balance", action="store_true", help="Pesos por clase (NINGUNA suele tener más muestras)"
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=0.8,
        help="Acierto mínimo para publicar una seña (D-043)",
    )
    parser.add_argument(
        "--min-samples", type=int, default=10, help="Muestras mínimas para publicar una seña"
    )
    args = parser.parse_args(argv)
    try:
        seqs = select_labels(
            load_datasets(expand_paths(args.data), args.signs), args.labels, args.others_as_none
        )
    except DatasetError as exc:
        print(f"Error en los datos: {exc}", file=sys.stderr)
        return 1
    print(
        f"{len(seqs.labels)} muestras de {len(set(seqs.collectors))} personas · "
        f"clases: {dict(Counter(seqs.labels))} · expresión facial: {seqs.face_features}"
    )
    train(
        seqs,
        args.out,
        args.reports,
        args.cv,
        args.augment,
        args.balance,
        args.min_recall,
        args.min_samples,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
