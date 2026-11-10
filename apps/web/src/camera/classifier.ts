// Clasificación de los 63 valores normalizados (§10.2): modelo propio de TensorFlow.js o, mientras
// no exista, `MockClassifier` (R8.6). Toda predicción va dentro de `tf.tidy()` (B: fugas de tfjs).
import type * as tfType from "@tensorflow/tfjs";
import { DenseNetwork, type DenseNetworkLike } from "./dense";
import { bestWithEquivalents, CAMERA_EQUIVALENCES, type Equivalences } from "./equivalences";

export const NONE = "NINGUNA";
export const THRESHOLD = 0.7;
export const SMOOTHING_WINDOW = 10;
/** Votos mínimos de la misma etiqueta en la ventana: un cuadro aislado nunca basta (B37). */
export const MIN_VOTES = 6;
export const MODEL_DIR = "/models/lsc-alfabeto";
/** Prueba D-038: tiempo que la seña debe mantenerse estable cuando hay pocos FPS. */
export const STABLE_MS = 250;
/** Prueba D-038: votos mínimos para aceptar por tiempo (nunca un cuadro aislado, B37). */
export const MIN_STABLE_VOTES = 3;
/** Prueba D-038: los resultados más viejos que esto salen de la ventana. */
export const WINDOW_MS = 600;

export interface Prediction {
  label: string;
  confidence: number;
}

interface TimedPrediction extends Prediction {
  at: number | undefined;
}

export interface Classifier {
  readonly simulated: boolean;
  readonly labels: readonly string[];
  classify(features: readonly number[]): Prediction;
  dispose(): void;
}

/** Sin modelo entrenado: siempre «NINGUNA» con confianza 0 (la interfaz no falla, R8.6). */
export class MockClassifier implements Classifier {
  readonly simulated = true;
  readonly labels: readonly string[] = [];
  classify(): Prediction {
    return { label: NONE, confidence: 0 };
  }
  dispose(): void {}
}

export class TfjsClassifier implements Classifier {
  readonly simulated = false;
  constructor(
    private readonly tf: typeof tfType,
    private readonly model: tfType.LayersModel,
    readonly labels: readonly string[],
  ) {}

  classify(features: readonly number[]): Prediction {
    const scores = this.tf.tidy(() => {
      const output = this.model.predict(this.tf.tensor2d([Array.from(features)])) as tfType.Tensor;
      return output.dataSync();
    });
    let best = 0;
    for (let i = 1; i < scores.length; i += 1) if (scores[i] > scores[best]) best = i;
    return { label: this.labels[best] ?? NONE, confidence: scores[best] ?? 0 };
  }

  dispose(): void {
    this.model.dispose();
  }
}

/** Prueba D-038: el mismo modelo calculado en JavaScript, sin tfjs en cada cuadro. */
export class DenseClassifier implements Classifier {
  readonly simulated = false;
  constructor(
    private readonly network: DenseNetworkLike,
    readonly labels: readonly string[],
    /** D-041: pares que se suman (B/4, 2/V, 3/W). Vacío = el máximo de siempre. */
    private readonly equivalences: Equivalences = new Map(),
  ) {}

  classify(features: readonly number[]): Prediction {
    const best = bestWithEquivalents(this.network.predict(features), this.labels, this.equivalences);
    return { label: best.label || NONE, confidence: best.confidence };
  }

  dispose(): void {}
}

/**
 * Carga el modelo de `/models/lsc-alfabeto`; si no existe o no coincide con `labels.json`, simula.
 * Prueba D-038: si el modelo es solo de capas densas, se calcula en JavaScript (`fast`, por defecto);
 * con `fast: false` se usa tfjs como antes, para comparar.
 */
export async function loadClassifier(
  fetchFn: typeof fetch = fetch,
  options: { fast?: boolean } = {},
): Promise<Classifier> {
  try {
    const response = await fetchFn(`${MODEL_DIR}/labels.json`);
    if (!response.ok) return new MockClassifier();
    const labels = (await response.json()) as unknown;
    if (!Array.isArray(labels) || !labels.every((l) => typeof l === "string")) return new MockClassifier();
    const tf = await import("@tensorflow/tfjs"); // carga diferida: solo en la cámara
    const model = await tf.loadLayersModel(`${MODEL_DIR}/model.json`);
    const outputs = model.outputs[0]?.shape.at(-1) ?? 0;
    if (outputs !== labels.length || new Set(labels).size !== labels.length) {
      model.dispose();
      return new MockClassifier();
    }
    if (options.fast ?? true) {
      const network = DenseNetwork.fromModel(model);
      if (network && network.inputSize === 63) {
        model.dispose(); // los pesos ya están copiados: tfjs no queda ocupando memoria
        return new DenseClassifier(network, labels as string[], CAMERA_EQUIVALENCES);
      }
    }
    return new TfjsClassifier(tf, model, labels as string[]);
  } catch {
    return new MockClassifier();
  }
}

/**
 * Mayoría de los últimos 10 resultados; solo cuenta si confianza ≥ 0,70 y no es «NINGUNA».
 *
 * Con el instante del cuadro (prueba D-038) también acepta la seña si se mantiene estable
 * `STABLE_MS` con al menos `MIN_STABLE_VOTES` votos y es mayoría: en un portátil a 10 FPS
 * reconoce en ~0,3 s en vez de ~0,6 s. A 30 FPS se comporta igual que antes (6 votos).
 */
export class Smoother {
  private readonly window: TimedPrediction[] = [];

  push(prediction: Prediction, nowMs?: number): Prediction | null {
    this.window.push({ ...prediction, at: nowMs });
    if (this.window.length > SMOOTHING_WINDOW) this.window.shift();
    if (nowMs !== undefined) {
      while (this.window.length > 0 && (this.window[0].at ?? nowMs) < nowMs - WINDOW_MS) this.window.shift();
    }
    const counts = new Map<string, { count: number; confidence: number }>();
    for (const item of this.window) {
      const entry = counts.get(item.label) ?? { count: 0, confidence: 0 };
      counts.set(item.label, { count: entry.count + 1, confidence: Math.max(entry.confidence, item.confidence) });
    }
    let winner: string | null = null;
    let top = 0;
    for (const [label, entry] of counts) {
      if (entry.count > top) {
        winner = label;
        top = entry.count;
      }
    }
    if (winner === null || winner === NONE) return null;
    const matches = this.window.filter((item) => item.label === winner);
    if (top < MIN_VOTES && !this.stableLongEnough(matches, top, nowMs)) return null;
    // Confianza media de esa etiqueta en la ventana: un pico aislado no basta.
    const confidence = matches.reduce((sum, item) => sum + item.confidence, 0) / matches.length;
    // Tolerancia para el error de redondeo de la media (0,7 × 6 / 6 ≠ 0,7 exacto en coma flotante).
    return confidence + 1e-9 >= THRESHOLD ? { label: winner, confidence } : null;
  }

  reset(): void {
    this.window.length = 0;
  }

  /** Votos suficientes, mayoría y la misma seña durante `STABLE_MS` (B37: nunca un cuadro aislado). */
  private stableLongEnough(matches: readonly TimedPrediction[], votes: number, nowMs?: number): boolean {
    if (nowMs === undefined || votes < MIN_STABLE_VOTES || votes * 2 <= this.window.length) return false;
    const first = matches[0].at;
    return first !== undefined && nowMs - first >= STABLE_MS;
  }
}

/** `detectForVideo` exige timestamps estrictamente crecientes: salta el cuadro si no lo son. */
export class MonotonicTimestamps {
  private last = -Infinity;

  next(now: number): number | null {
    if (now <= this.last) return null;
    this.last = now;
    return now;
  }
}
