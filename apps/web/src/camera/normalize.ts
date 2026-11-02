// normalizeLandmarks (§10.3): la MISMA función para recolectar, entrenar (Python solo lee estos
// números, D11) e inferir. Cambiarla exige una nueva `featureVersion` y volver a recolectar.

export const FEATURE_VERSION = "hand-v1";
export const FEATURE_SIZE = 63;
/** Versión exacta de `@mediapipe/tasks-vision` (se guarda en cada `dataset.json`). */
export const TASKS_VISION_VERSION = "1.1.0";
const POINTS = 21;
const MIDDLE_BASE = 9;
const MIN_SCALE = 1e-6;

export interface Landmark {
  x: number;
  y: number;
  z: number;
}

export type Handedness = "Left" | "Right";

/**
 * 21 puntos → 63 números: refleja la mano izquierda (x → 1 − x), pone la muñeca en el origen y
 * divide entre la distancia muñeca–base del dedo medio. Devuelve `null` si el cuadro no sirve.
 */
export function normalizeLandmarks(points: readonly Landmark[], handedness: Handedness): number[] | null {
  if (points.length !== POINTS) return null;
  const mirrored = handedness === "Left" ? points.map((p) => ({ x: 1 - p.x, y: p.y, z: p.z })) : points;
  const wrist = mirrored[0];
  const base = mirrored[MIDDLE_BASE];
  const scale = Math.hypot(base.x - wrist.x, base.y - wrist.y, base.z - wrist.z);
  if (scale < MIN_SCALE) return null;
  const values: number[] = [];
  for (const p of mirrored) {
    values.push((p.x - wrist.x) / scale, (p.y - wrist.y) / scale, (p.z - wrist.z) / scale);
  }
  return values;
}

/**
 * Elige la mano que hace la seña: la más alta en la imagen (muñeca con menor `y`). Con una sola
 * mano detectada, la otra (en reposo, colgando) se tomaba a veces por la seña (D-020).
 */
export function pickSigningHand<T extends { y: number }>(
  hands: readonly (readonly T[])[],
  handedness: readonly (readonly { categoryName: string }[])[],
): { points: readonly T[]; side: Handedness } | null {
  let best = -1;
  for (let i = 0; i < hands.length; i += 1) {
    if (hands[i]?.length && (best < 0 || hands[i][0].y < hands[best][0].y)) best = i;
  }
  if (best < 0) return null;
  return { points: hands[best], side: handedness[best]?.[0]?.categoryName === "Left" ? "Left" : "Right" };
}
