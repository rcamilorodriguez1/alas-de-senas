"""Escribe `ml/fixtures/holistic_v2_cases.json` (H11): entrada → salida esperada del reflejo, la
máscara facial y la normalización. pytest (Python) y Vitest (TypeScript) prueban los mismos casos.

Uso:  uv run --no-project --with numpy python ml/parity_fixtures.py
Solo se regenera si cambia la especificación; si un lado cambia sin la otra, su prueba falla.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from train_sequence import (
    DOMINANT,
    FACE_PRESENCE,
    FEATURE_SIZE,
    NON_DOMINANT,
    PRESENCE,
    mask_face,
    mirror_frames,
    normalize,
)

OUT = Path(__file__).resolve().parent / "fixtures" / "holistic_v2_cases.json"


def as_list(values: np.ndarray) -> list[float]:
    return [float(v) for v in np.asarray(values, dtype=np.float32)]


def make_case(
    rng: np.random.Generator, name: str, other_hand: bool, face: bool
) -> dict[str, object]:
    # Valores representables en float32: los dos lenguajes parten exactamente del mismo vector.
    frame = rng.uniform(-2, 2, FEATURE_SIZE).astype(np.float32)
    frame[DOMINANT + PRESENCE] = 1
    frame[NON_DOMINANT + PRESENCE] = 1 if other_hand else 0
    if not other_hand:
        frame[NON_DOMINANT : NON_DOMINANT + PRESENCE] = 0
    frame[FACE_PRESENCE] = 1 if face else 0
    mean = rng.uniform(-1, 1, FEATURE_SIZE).astype(np.float32)
    std = rng.uniform(0.5, 2, FEATURE_SIZE).astype(np.float32)
    std[[3, 70, 150]] = [0, 1e-7, 0]  # desviación casi nula → cuenta como 1
    return {
        "name": name,
        "frame": as_list(frame),
        "mean": as_list(mean),
        "std": as_list(std),
        "mirror": as_list(mirror_frames(frame)),
        "maskFace": as_list(mask_face(frame)),
        "normalize": as_list(normalize(frame, mean.astype(np.float64), std.astype(np.float64))),
    }


def main() -> None:
    rng = np.random.default_rng(20261102)
    cases = [
        make_case(rng, "dos manos y cara", other_hand=True, face=True),
        make_case(rng, "solo mano dominante", other_hand=False, face=True),
        make_case(rng, "sin cara", other_hand=True, face=False),
    ]
    payload = {"featureVersion": "holistic-v2", "featureSize": FEATURE_SIZE, "cases": cases}
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cases)} casos en {OUT}")


if __name__ == "__main__":
    main()
