// Clasificador de secuencias `[30, 159]` (anexo A.8): modelo GRU de `/models/lsc-gestos` con su
// `meta.json` (media y desviación del entrenamiento). Inferencia una vez por ventana, dentro de tf.tidy().
import type * as tfType from "@tensorflow/tfjs";
import { NONE, type Prediction } from "../classifier";
import { RecognizerFactory, type SignClassifier } from "../recognizer";
import { HOLISTIC_FEATURE_VERSION, HOLISTIC_V2_SIZE, maskFace, normalizeFeatures } from "./frame";
import { SEQUENCE_FRAMES } from "./sequencer";

export const GESTURE_MODEL_DIR = "/models/lsc-gestos";

/** Promedios de la seña en el entrenamiento, para la retroalimentación de Tomi (A.10). */
export interface Prototype {
  handFace: number;
  handY: number;
  browUp: number;
}

export interface SequenceMeta {
  featureVersion: typeof HOLISTIC_FEATURE_VERSION;
  featureSize: number;
  frames: number;
  durationSec: number;
  threshold: number;
  mean: number[];
  std: number[];
  labels: string[];
  /** false si se entrenó sin expresión facial (p. ej. LSC-54, caras pixeladas): se ponen en 0. */
  faceFeatures: boolean;
  prototypes: Record<string, Prototype>;
}

const isNumbers = (value: unknown, length: number): value is number[] =>
  Array.isArray(value) && value.length === length && value.every((v) => typeof v === "number" && Number.isFinite(v));

function parsePrototype(value: unknown): Prototype | null {
  if (typeof value !== "object" || value === null) return null;
  const { handFace, handY, browUp } = value as Record<string, unknown>;
  if (typeof handFace !== "number" || typeof handY !== "number" || typeof browUp !== "number") return null;
  return { handFace, handY, browUp };
}

/** Valida `meta.json` (H5): otra versión, otro tamaño o etiquetas distintas → null (no se usa). */
export function parseSequenceMeta(raw: unknown, labels?: readonly string[]): SequenceMeta | null {
  if (RecognizerFactory.kindFor(raw) !== "sequence" || typeof raw !== "object" || raw === null) return null;
  const meta = raw as Record<string, unknown>;
  if (meta.featureSize !== HOLISTIC_V2_SIZE || meta.frames !== SEQUENCE_FRAMES) return null;
  if (!isNumbers(meta.mean, HOLISTIC_V2_SIZE) || !isNumbers(meta.std, HOLISTIC_V2_SIZE)) return null;
  const list = meta.labels;
  if (!Array.isArray(list) || !list.every((l) => typeof l === "string") || new Set(list).size !== list.length) return null;
  if (labels && (labels.length !== list.length || labels.some((l, i) => l !== list[i]))) return null;
  const threshold = typeof meta.threshold === "number" ? meta.threshold : 0.7;
  const prototypes: Record<string, Prototype> = {};
  if (typeof meta.prototypes === "object" && meta.prototypes !== null) {
    for (const [label, value] of Object.entries(meta.prototypes)) {
      const proto = parsePrototype(value);
      if (proto) prototypes[label] = proto;
    }
  }
  return {
    featureVersion: HOLISTIC_FEATURE_VERSION,
    featureSize: HOLISTIC_V2_SIZE,
    frames: SEQUENCE_FRAMES,
    durationSec: typeof meta.durationSec === "number" ? meta.durationSec : 2,
    threshold,
    mean: meta.mean,
    std: meta.std,
    labels: list as string[],
    faceFeatures: meta.faceFeatures !== false,
    prototypes,
  };
}

/** 30 cuadros → entrada plana del modelo: máscara facial (si aplica) y normalización (A.8, H11). */
export function prepareSequence(frames: readonly Float32Array[], meta: SequenceMeta): Float32Array {
  const out = new Float32Array(SEQUENCE_FRAMES * HOLISTIC_V2_SIZE);
  frames.slice(0, SEQUENCE_FRAMES).forEach((frame, i) => {
    const input = meta.faceFeatures ? frame : maskFace(frame);
    out.set(normalizeFeatures(input, meta.mean, meta.std), i * HOLISTIC_V2_SIZE);
  });
  return out;
}

/** Bajo el umbral, la respuesta es «NINGUNA» (la cámara no adivina). */
export function decide(prediction: Prediction, threshold: number): Prediction {
  return prediction.confidence + 1e-9 >= threshold ? prediction : { label: NONE, confidence: prediction.confidence };
}

export class SequenceClassifier implements SignClassifier<readonly Float32Array[]> {
  readonly featureVersion = "holistic-v2";
  readonly simulated = false;

  constructor(
    private readonly tf: typeof tfType,
    private readonly model: tfType.LayersModel,
    readonly meta: SequenceMeta,
  ) {}

  get labels(): readonly string[] {
    return this.meta.labels;
  }

  classify(frames: readonly Float32Array[]): Prediction {
    if (frames.length !== SEQUENCE_FRAMES) return { label: NONE, confidence: 0 };
    const input = prepareSequence(frames, this.meta);
    const scores = this.tf.tidy(() => {
      const output = this.model.predict(this.tf.tensor3d(input, [1, SEQUENCE_FRAMES, HOLISTIC_V2_SIZE])) as tfType.Tensor;
      return output.dataSync();
    });
    let best = 0;
    for (let i = 1; i < scores.length; i += 1) if (scores[i] > scores[best]) best = i;
    return decide({ label: this.meta.labels[best] ?? NONE, confidence: scores[best] ?? 0 }, this.meta.threshold);
  }

  dispose(): void {
    this.model.dispose();
  }
}

/** `meta.json` válido del modelo de gestos, o null si no hay modelo (entonces no hay modo gestos). */
export async function loadGestureMeta(fetchFn: typeof fetch = fetch): Promise<SequenceMeta | null> {
  const raw = await RecognizerFactory.readMeta(GESTURE_MODEL_DIR, fetchFn);
  return raw === null ? null : parseSequenceMeta(raw);
}

export async function loadSequenceClassifier(fetchFn: typeof fetch = fetch): Promise<SequenceClassifier | null> {
  const meta = await loadGestureMeta(fetchFn);
  if (!meta) return null;
  try {
    const tf = await import("@tensorflow/tfjs"); // carga diferida: solo con la cámara
    const model = await tf.loadLayersModel(`${GESTURE_MODEL_DIR}/model.json`);
    if ((model.outputs[0]?.shape.at(-1) ?? 0) !== meta.labels.length) {
      model.dispose();
      return null;
    }
    return new SequenceClassifier(tf, model, meta);
  } catch {
    return null;
  }
}

let gestureLabels: Promise<string[]> | null = null;

/** Señas que conoce el modelo de gestos publicado (en caché); vacío si no hay modelo. */
export function fetchGestureLabels(fetchFn: typeof fetch = fetch): Promise<string[]> {
  const pending = (gestureLabels ??= loadGestureMeta(fetchFn).then((meta) =>
    meta ? meta.labels.filter((l) => l !== NONE) : [],
  ));
  // Solo se guarda un modelo válido: un error de red (o un 404 pasajero) no desactiva el modo gestos
  // hasta recargar; el siguiente ejercicio vuelve a intentarlo.
  return pending
    .catch(() => [])
    .then((labels) => {
      if (labels.length === 0 && gestureLabels === pending) gestureLabels = null;
      return labels;
    });
}

export function resetGestureLabelsCache(): void {
  gestureLabels = null;
}
