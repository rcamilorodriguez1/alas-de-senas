"""Entrena el MLP del alfabeto estático a partir de los `dataset.json` del colector (§10.5).

Uso:
    uv run --project ml python ml/train_static.py --data ml/data/*.json \\
        --out apps/web/public/models/lsc-alfabeto

Python NUNCA recalcula puntos (D11): solo entrena sobre los 63 números que exportó el navegador
con `normalizeLandmarks` (hand-v1). Solo letras `motion = static` de `content/signs.csv` (R8.3a).
`labels.json` y `meta.json` se escriben en el mismo paso que el modelo, para que el orden de las
etiquetas coincida siempre con las salidas.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import random
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

FEATURE_VERSION = "hand-v1"
FEATURE_SIZE = 63
NONE_LABEL = "NINGUNA"
THRESHOLD = 0.7
SEED = 42
EPOCHS = 60
MIN_PEOPLE_FOR_GROUP_SPLIT = 3
ROOT = Path(__file__).resolve().parent.parent


class DatasetError(ValueError):
    """Datos inválidos: se explica en español qué archivo y qué falla."""


@dataclass(frozen=True)
class Samples:
    features: list[list[float]]
    labels: list[str]
    collectors: list[str]
    skipped_dynamic: dict[str, int]  # muestras de letras con movimiento descartadas


# ---------- Carga y validación (sin TensorFlow: se puede probar sola) ----------


def expand_paths(patterns: list[str]) -> list[Path]:
    """En Windows la terminal no expande `*.json`: se expande aquí."""
    paths: list[Path] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        paths.extend(Path(match) for match in (matches or [pattern]))
    return paths


def static_labels(signs_csv: Path) -> tuple[set[str], set[str]]:
    """(slugs estáticos, slugs con movimiento) según la columna `motion` de signs.csv."""
    static: set[str] = set()
    dynamic: set[str] = set()
    with signs_csv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            motion = (row.get("motion") or "").strip()
            if motion == "static":
                static.add(row["slug"])
            elif motion == "dynamic":
                dynamic.add(row["slug"])
    return static, dynamic


def load_datasets(paths: list[Path], signs_csv: Path) -> Samples:
    static, dynamic = static_labels(signs_csv)
    features: list[list[float]] = []
    labels: list[str] = []
    collectors: list[str] = []
    skipped: Counter[str] = Counter()
    if not paths:
        raise DatasetError("No hay archivos de datos: pasa --data ml/data/*.json")
    for path in paths:
        if not path.is_file():
            raise DatasetError(f"No existe el archivo {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{path.name} no es un JSON válido ({exc}).") from exc
        if not isinstance(data, dict):
            raise DatasetError(f"{path.name}: se esperaba un objeto con `samples`.")
        if data.get("featureVersion") != FEATURE_VERSION or data.get("featureSize") != FEATURE_SIZE:
            raise DatasetError(
                f"{path.name}: se esperaba featureVersion={FEATURE_VERSION} y featureSize="
                f"{FEATURE_SIZE}; vuelve a recolectar con la versión actual del colector."
            )
        collector = str(data.get("collector") or "").strip()
        samples_in = data.get("samples", [])
        per_sample = all(
            str(s.get("collector") or "").strip() for s in samples_in if isinstance(s, dict)
        )
        if not collector and not (samples_in and per_sample):
            raise DatasetError(f"{path.name}: falta el alias de quien grabó (`collector`).")
        for index, sample in enumerate(samples_in):
            label = sample.get("label")
            vector = sample.get("features")
            where = f"{path.name}, muestra {index}"
            if label in dynamic:
                # Las letras con movimiento se practican con autoevaluación (R8.3a): se descartan
                # sus muestras sin perder el resto del archivo.
                skipped[str(label)] += 1
                continue
            if label != NONE_LABEL and label not in static:
                raise DatasetError(
                    f"{where}: «{label}» no es una letra estática de signs.csv ni {NONE_LABEL}."
                )
            if (
                not isinstance(vector, list)
                or len(vector) != FEATURE_SIZE
                or not all(
                    isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
                    for v in vector
                )
            ):
                raise DatasetError(f"{where}: se esperaban {FEATURE_SIZE} números finitos.")
            features.append([float(v) for v in vector])
            labels.append(str(label))
            # Persona por muestra (videos de varias personas, D-019); si no, el alias del archivo.
            collectors.append(str(sample.get("collector") or collector).strip())
    if len(set(labels)) < 2:
        raise DatasetError("Se necesitan al menos 2 clases (por ejemplo una letra y NINGUNA).")
    return Samples(features, labels, collectors, dict(skipped))


def label_order(labels: list[str]) -> list[str]:
    """Orden estable de las clases = índice de cada salida del modelo."""
    return sorted(set(labels))


# ---------- Entrenamiento ----------


def set_seeds() -> None:
    os.environ["PYTHONHASHSEED"] = str(SEED)
    random.seed(SEED)
    import numpy as np
    import tensorflow as tf

    np.random.seed(SEED)
    tf.random.set_seed(SEED)


def train(samples: Samples, out: Path, reports: Path) -> dict[str, float]:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    set_seeds()
    import numpy as np
    import tensorflow as tf

    classes = label_order(samples.labels)
    index = {label: i for i, label in enumerate(classes)}
    x = np.array(samples.features, dtype="float32")
    y = np.array([index[label] for label in samples.labels], dtype="int32")
    people = sorted(set(samples.collectors))
    train_idx, val_idx = split_indices(y, samples.collectors)

    layers = tf.keras.layers
    model = tf.keras.Sequential(
        [
            layers.Input((FEATURE_SIZE,)),
            layers.Dense(128, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(64, activation="relu"),
            layers.Dense(len(classes), activation="softmax"),
        ]
    )
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    model.fit(
        x[train_idx],
        y[train_idx],
        validation_data=(x[val_idx], y[val_idx]),
        epochs=EPOCHS,
        batch_size=32,
        shuffle=True,
        verbose=2,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True)],
    )

    predicted = model.predict(x[val_idx], verbose=0).argmax(axis=1)
    per_class: dict[str, float] = {}
    for i, label in enumerate(classes):
        mask = y[val_idx] == i
        per_class[label] = float((predicted[mask] == i).mean()) if mask.any() else float("nan")
        print(f"  {label:>16}: {per_class[label]:.2%} ({int(mask.sum())} muestras de validación)")

    out.mkdir(parents=True, exist_ok=True)
    export_tfjs(model, out)
    (out / "labels.json").write_text(json.dumps(classes, ensure_ascii=False), encoding="utf-8")
    meta = {
        "featureVersion": FEATURE_VERSION,
        "featureSize": FEATURE_SIZE,
        "threshold": THRESHOLD,
        "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "classes": len(classes),
        "samples": dict(Counter(samples.labels)),
        "people": len(people),
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Modelo, labels.json y meta.json en {out}")

    # La matriz va después de exportar: si la gráfica falla, el modelo ya quedó guardado.
    reports.mkdir(parents=True, exist_ok=True)
    matrix = np.zeros((len(classes), len(classes)), dtype=int)
    for real, guess in zip(y[val_idx], predicted, strict=True):
        matrix[real, guess] += 1
    try:
        save_confusion(matrix, classes, reports / "confusion.png")
    except Exception as exc:  # un reporte no puede tumbar el entrenamiento
        print(f"ADVERTENCIA: no se pudo dibujar la matriz de confusión ({exc}).")
        print(matrix)
    return per_class


def split_indices(y: object, collectors: list[str]) -> tuple[object, object]:
    """Validación con personas que el modelo no ve (≈ 20 % de las personas, semilla fija); con
    menos de 3 personas, 80/20 al azar con aviso. Sin scikit-learn (no siempre instala)."""
    import numpy as np

    people = sorted(set(collectors))
    rng = random.Random(SEED)  # noqa: S311 — separación reproducible, no criptográfica
    if len(people) >= MIN_PEOPLE_FOR_GROUP_SPLIT:
        held = set(rng.sample(people, max(1, round_up_fifth(len(people)))))
        mask = np.array([c in held for c in collectors])
        print(f"Separación por persona: {len(people)} personas; validación con {sorted(held)}.")
    else:
        print(
            f"ADVERTENCIA: solo {len(people)} persona(s); se usa 80/20 al azar. "
            "La meta es ≥ 3 personas para medir cómo generaliza."
        )
        order = list(range(len(collectors)))
        rng.shuffle(order)
        mask = np.zeros(len(collectors), dtype=bool)
        mask[order[: len(order) // 5]] = True
    indices = np.arange(len(collectors))
    return indices[~mask], indices[mask]


def round_up_fifth(n: int) -> int:
    """Una quinta parte, redondeando hacia arriba con enteros (sin round())."""
    return (n + 4) // 5


def export_tfjs(model: object, out: Path) -> None:
    """Exporta a TensorFlow.js. Usa `tensorflowjs` si está; si no (no instala en Windows), escribe
    el formato de capas directamente: `model.json` + `group1-shard1of1.bin` (D-020)."""
    try:
        import tensorflowjs as tfjs
    except ImportError:
        tfjs = None
    if tfjs is not None:
        tfjs.converters.save_keras_model(model, str(out))
        return
    import numpy as np
    import tensorflow as tf

    if not isinstance(model, tf.keras.Model):
        raise TypeError("Se esperaba un modelo de Keras.")
    keras_model = model
    specs: list[dict[str, object]] = []
    chunks: list[bytes] = []
    for weight in keras_model.weights:
        values = np.asarray(weight.numpy(), dtype="<f4")
        specs.append(
            {"name": weight.name.split(":")[0], "shape": list(values.shape), "dtype": "float32"}
        )
        chunks.append(values.tobytes())
    (out / "group1-shard1of1.bin").write_bytes(b"".join(chunks))
    manifest = {
        "format": "layers-model",
        "generatedBy": f"keras v{tf.__version__}",
        "convertedBy": "alas-de-senas export_tfjs (D-020)",
        "modelTopology": {
            "keras_version": tf.__version__,
            "backend": "tensorflow",
            "model_config": json.loads(keras_model.to_json()),
        },
        "weightsManifest": [{"paths": ["group1-shard1of1.bin"], "weights": specs}],
    }
    (out / "model.json").write_text(json.dumps(manifest), encoding="utf-8")


def save_confusion(matrix: object, classes: list[str], path: Path) -> None:
    # Colab define MPLBACKEND=module://matplotlib_inline…, que el matplotlib de este entorno no
    # reconoce y falla al importarse: se fuerza el modo sin pantalla antes de importarlo.
    os.environ["MPLBACKEND"] = "Agg"
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    size = max(4, len(classes) * 0.6)
    figure, axis = plt.subplots(figsize=(size, size))
    axis.imshow(matrix, cmap="Greens")
    axis.set_xticks(range(len(classes)), classes, rotation=90)
    axis.set_yticks(range(len(classes)), classes)
    axis.set_xlabel("Predicción")
    axis.set_ylabel("Real")
    axis.set_title("Matriz de confusión (validación)")
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)
    print(f"Matriz de confusión en {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Entrena el alfabeto estático (§10.5).")
    parser.add_argument("--data", nargs="+", required=True, help="Archivos dataset.json")
    parser.add_argument("--out", type=Path, default=ROOT / "apps/web/public/models/lsc-alfabeto")
    parser.add_argument("--signs", type=Path, default=ROOT / "content/signs.csv")
    parser.add_argument("--reports", type=Path, default=ROOT / "ml/reports")
    args = parser.parse_args(argv)
    try:
        samples = load_datasets(expand_paths(args.data), args.signs)
    except DatasetError as exc:
        print(f"Error en los datos: {exc}", file=sys.stderr)
        return 1
    if samples.skipped_dynamic:
        print(
            "ADVERTENCIA: se descartaron muestras de letras con movimiento: "
            f"{samples.skipped_dynamic}"
        )
    print(f"{len(samples.labels)} muestras · clases: {dict(Counter(samples.labels))}")
    train(samples, args.out, args.reports)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
