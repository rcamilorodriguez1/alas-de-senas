// Vector por cuadro `holistic-v2` (anexo A.3): una sola función pura para recolectar, importar y
// reconocer, todo en el navegador. Python nunca recalcula puntos (D11): entrena sobre estos números.

export const HOLISTIC_FEATURE_VERSION = "holistic-v2";

/** Marcadores no manuales (A.3.4), buscados por nombre. */
export const BLENDSHAPES = [
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
] as const;

const HAND_POINTS = 21;
const SHAPE = HAND_POINTS * 3; // 63
const HAND_BLOCK = SHAPE + 3 + 1; // forma + posición + presencia = 67
const HAND_FACE = 6;

/** Desplazamientos de cada bloque dentro del vector (A.3.3). */
export const LAYOUT = {
  dominant: 0,
  nonDominant: HAND_BLOCK,
  handFace: 2 * HAND_BLOCK,
  blendshapes: 2 * HAND_BLOCK + HAND_FACE,
  facePresence: 2 * HAND_BLOCK + HAND_FACE + BLENDSHAPES.length,
} as const;

/** 159: calculado a partir de los bloques, no escrito a mano. */
export const HOLISTIC_V2_SIZE = LAYOUT.facePresence + 1;
export const PRESENCE_OFFSET = SHAPE + 3; // presencia dentro de un bloque de mano

const MIN_SCALE = 1e-6;
const SHOULDER_LEFT = 11;
const SHOULDER_RIGHT = 12;
const NOSE = 1; // punta de la nariz en la malla de la cara
const INDEX_TIP = 8;
const MIDDLE_BASE = 9;

export interface Point {
  x: number;
  y: number;
  z: number;
}

export interface Category {
  categoryName: string;
  score: number;
}

/** Subconjunto de `HolisticLandmarkerResult` que usa el vector (nombres verificados en 1.1.0). */
export interface HolisticInput {
  poseLandmarks: readonly (readonly Point[])[];
  leftHandLandmarks: readonly (readonly Point[])[];
  rightHandLandmarks: readonly (readonly Point[])[];
  faceLandmarks: readonly (readonly Point[])[];
  faceBlendshapes: readonly { categories: readonly Category[] }[];
}

export type DominantHand = "right" | "left";

/** Pares izquierda/derecha de los blendshapes (índices dentro de BLENDSHAPES). */
const MIRROR_PAIRS: [number, number][] = (() => {
  const pairs: [number, number][] = [];
  BLENDSHAPES.forEach((name, i) => {
    if (name.endsWith("Left")) {
      const j = BLENDSHAPES.indexOf(name.replace(/Left$/, "Right") as (typeof BLENDSHAPES)[number]);
      if (j >= 0) pairs.push([i, j]);
    }
  });
  return pairs;
})();

/** Índices de las componentes x (reflejo x → −x en el sistema del cuerpo). */
const X_INDICES: number[] = (() => {
  const xs: number[] = [];
  for (const block of [LAYOUT.dominant, LAYOUT.nonDominant]) {
    for (let p = 0; p < HAND_POINTS; p += 1) xs.push(block + p * 3);
    xs.push(block + SHAPE); // posición x
  }
  xs.push(LAYOUT.handFace, LAYOUT.handFace + 3);
  return xs;
})();

/**
 * Reflejo para zurdos (A.3.2) y aumento en Python (A.8): x → −x en todos los bloques e intercambio
 * de blendshapes izquierda/derecha. Aplicarlo dos veces devuelve el vector original (H2).
 */
export function mirrorFrame(frame: Float32Array): Float32Array {
  const out = Float32Array.from(frame);
  for (const i of X_INDICES) out[i] = out[i] === 0 ? 0 : -out[i];
  for (const [a, b] of MIRROR_PAIRS) {
    out[LAYOUT.blendshapes + a] = frame[LAYOUT.blendshapes + b];
    out[LAYOUT.blendshapes + b] = frame[LAYOUT.blendshapes + a];
  }
  return out;
}

function sub(a: Point, b: Point): Point {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function writeHand(out: Float32Array, offset: number, hand: readonly Point[] | undefined, origin: Point, scale: number) {
  if (!hand || hand.length !== HAND_POINTS) return false;
  const wrist = hand[0];
  const base = hand[MIDDLE_BASE];
  const size = Math.hypot(base.x - wrist.x, base.y - wrist.y, base.z - wrist.z);
  if (size < MIN_SCALE) return false;
  hand.forEach((p, i) => {
    out[offset + i * 3] = (p.x - wrist.x) / size;
    out[offset + i * 3 + 1] = (p.y - wrist.y) / size;
    out[offset + i * 3 + 2] = (p.z - wrist.z) / size;
  });
  const position = sub(wrist, origin);
  out[offset + SHAPE] = position.x / scale;
  out[offset + SHAPE + 1] = position.y / scale;
  out[offset + SHAPE + 2] = position.z / scale;
  out[offset + PRESENCE_OFFSET] = 1;
  return true;
}

/**
 * Resultado de HolisticLandmarker → 159 valores, o `null` si falta la pose o los hombros están
 * superpuestos (cuadro inválido, A.3.1). Origen: punto medio de los hombros; escala: su distancia.
 */
export function buildHolisticFrame(result: HolisticInput, dominantHand: DominantHand = "right"): Float32Array | null {
  const pose = result.poseLandmarks[0];
  if (!pose || pose.length <= SHOULDER_RIGHT) return null;
  const left = pose[SHOULDER_LEFT];
  const right = pose[SHOULDER_RIGHT];
  const origin = { x: (left.x + right.x) / 2, y: (left.y + right.y) / 2, z: (left.z + right.z) / 2 };
  const scale = Math.hypot(left.x - right.x, left.y - right.y);
  if (scale < MIN_SCALE) return null;

  const out = new Float32Array(HOLISTIC_V2_SIZE);
  const dominant = dominantHand === "left" ? result.leftHandLandmarks[0] : result.rightHandLandmarks[0];
  const other = dominantHand === "left" ? result.rightHandLandmarks[0] : result.leftHandLandmarks[0];
  const hasDominant = writeHand(out, LAYOUT.dominant, dominant, origin, scale);
  writeHand(out, LAYOUT.nonDominant, other, origin, scale);

  const face = result.faceLandmarks[0];
  if (face && face.length > NOSE) {
    out[LAYOUT.facePresence] = 1;
    if (hasDominant && dominant) {
      const nose = face[NOSE];
      const wrist = sub(dominant[0], nose);
      const tip = sub(dominant[INDEX_TIP], nose);
      out.set([wrist.x / scale, wrist.y / scale, wrist.z / scale, tip.x / scale, tip.y / scale, tip.z / scale], LAYOUT.handFace);
    }
    const scores = new Map((result.faceBlendshapes[0]?.categories ?? []).map((c) => [c.categoryName, c.score]));
    BLENDSHAPES.forEach((name, i) => {
      out[LAYOUT.blendshapes + i] = scores.get(name) ?? 0;
    });
  }
  return dominantHand === "left" ? mirrorFrame(out) : out;
}

/** Nombres de blendshapes que faltan en la versión instalada (prueba de arranque, H4). */
export function missingBlendshapes(available: readonly string[]): string[] {
  const names = new Set(available);
  return BLENDSHAPES.filter((name) => !names.has(name));
}

/** (x − media) / desviación por característica (A.8); desviaciones casi nulas cuentan como 1. */
export function normalizeFeatures(frame: Float32Array, mean: readonly number[], std: readonly number[]): Float32Array {
  const out = new Float32Array(frame.length);
  for (let i = 0; i < frame.length; i += 1) {
    const s = std[i] > MIN_SCALE ? std[i] : 1;
    out[i] = (frame[i] - mean[i]) / s;
  }
  return out;
}

/**
 * Sin rostro (modelos entrenados con caras pixeladas, A.7): todo lo que depende de la cara en 0
 * (mano–cara, 18 blendshapes y presencia), para que la cámara en vivo vea lo mismo que el entrenamiento.
 */
export function maskFace(frame: Float32Array): Float32Array {
  const out = Float32Array.from(frame);
  out.fill(0, LAYOUT.handFace, LAYOUT.facePresence + 1);
  return out;
}
