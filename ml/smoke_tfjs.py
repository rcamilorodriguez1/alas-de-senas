"""Prueba temprana de compatibilidad Python (Keras 2) ↔ navegador (TensorFlow.js).

Crea dos modelos pequeños con las MISMAS arquitecturas que se usarán de verdad (§10.5 y anexo),
los convierte a TensorFlow.js y guarda la salida esperada para una entrada fija. La prueba de Vitest
`apps/web/src/camera/tfjs-compat.test.ts` carga esos archivos y compara (tolerancia 1e-4).

Uso:  uv run --project ml python ml/smoke_tfjs.py
Los archivos generados ya vienen en el kit (ml/fixtures/tfjs-smoke/); regenerarlos solo si cambian
las versiones de TensorFlow o tensorflowjs.
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np  # noqa: E402
import tensorflow as tf  # noqa: E402
import tensorflowjs as tfjs  # noqa: E402

OUT = Path(__file__).parent / "fixtures" / "tfjs-smoke"
L = tf.keras.layers


def fixed_input(shape: tuple[int, ...]) -> np.ndarray:
    """Entrada determinista que la prueba de TypeScript reproduce: ((i*37) % 101) / 100 - 0.5."""
    n = int(np.prod(shape))
    flat = np.array([((i * 37) % 101) / 100 - 0.5 for i in range(n)], dtype="float32")
    return flat.reshape((1, *shape))


def static_model(classes: int) -> tf.keras.Model:
    # §10.5: Dense(128) → Dropout(0.3) → Dense(64) → Dense(n, softmax)
    return tf.keras.Sequential([
        L.Input((63,)), L.Dense(128, activation="relu"), L.Dropout(0.3),
        L.Dense(64, activation="relu"), L.Dense(classes, activation="softmax"),
    ])


def sequence_model(classes: int) -> tf.keras.Model:
    # Anexo holístico. reset_after=False es OBLIGATORIO: TensorFlow.js no soporta reset_after=True
    # (el valor por defecto de Keras) y el modelo no cargaría en el navegador (B73).
    return tf.keras.Sequential([
        L.Input((30, 159)),
        L.GRU(64, return_sequences=True, reset_after=False), L.GRU(64, reset_after=False),
        L.Dense(64, activation="relu"), L.Dropout(0.3), L.Dense(classes, activation="softmax"),
    ])


def build(name: str, model: tf.keras.Model, shape: tuple[int, ...], classes: int) -> None:
    rng = np.random.default_rng(7)
    x = rng.random((64, *shape), dtype=np.float32)
    y = rng.integers(0, classes, 64)
    model.compile("adam", "sparse_categorical_crossentropy")
    model.fit(x, y, epochs=2, verbose=0)
    out_dir = OUT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*"):
        old.unlink()
    tfjs.converters.save_keras_model(model, str(out_dir))
    expected = model.predict(fixed_input(shape), verbose=0)[0].tolist()
    (out_dir / "reference.json").write_text(json.dumps({
        "inputShape": [1, *shape], "input": "((i*37) % 101) / 100 - 0.5",
        "expected": [round(v, 6) for v in expected], "tolerance": 1e-4,
        "tensorflow": tf.__version__, "tensorflowjs": tfjs.__version__,
    }, indent=2))


def main() -> None:
    random.seed(7)
    np.random.seed(7)
    tf.random.set_seed(7)
    build("static", static_model(4), (63,), 4)
    build("sequence", sequence_model(3), (30, 159), 3)
    print(f"Listo: {OUT}")


if __name__ == "__main__":
    main()
