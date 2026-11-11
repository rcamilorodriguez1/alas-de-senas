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
/** Tiempo que la seña debe mantenerse estable cuando hay pocos FPS (D-038). */
export const STABLE_MS = 250;
/** Votos mínimos para aceptar por tiempo (nunca un cuadro aislado, B37). */
export const MIN_STABLE_VOTES = 3;
/** Los resultados más viejos que esto salen de la ventana (con cámaras lentas se amplía, D-038). */
export const WINDOW_MS = 600;
/** Ventana máxima con pocos FPS: 4 cuadros del ritmo típico, hasta 2 s. */
export const MAX_WINDOW_MS = 2000;

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
    /** D-041: pares que se suman (B/4, 2/V, 3/W). Vacío = el máximo de siempre. */
    private readonly equivalences: Equivalences = new Map(),
  ) {}

  classify(features: readonly number[]): Prediction {
    const scores = this.tf.tidy(() => {
      const output = this.model.predict(this.tf.tensor2d([Array.from(features)])) as tfType.Tensor;
      return output.dataSync();
    });
    const best = bestWithEquivalents(scores, this.labels, this.equivalences);
    return { label: best.label || NONE, confidence: best.confidence };
  }

  dispose(): void {
    this.model.dispose();
  }
}

/** El mismo modelo calculado en JavaScript, sin tfjs en cada cuadro (D-038). */
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
 * Si el modelo es solo de capas densas, se calcula en JavaScript (D-038); si no, con tfjs.
 */
export async function loadClassifier(fetchFn: typeof fetch = fetch): Promise<Classifier> {
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
    let network: DenseNetwork | null = null;
    try {
      network = DenseNetwork.fromModel(model);
    } catch {
      network = null; // p. ej. contexto WebGL perdido al leer los pesos: se sigue con tfjs
    }
    if (network && network.inputSize === 63) {
      model.dispose(); // los pesos ya están copiados: tfjs no queda ocupando memoria
      return new DenseClassifier(network, labels as string[], CAMERA_EQUIVALENCES);
    }
    return new TfjsClassifier(tf, model, labels as string[], CAMERA_EQUIVALENCES);
  } catch {
    return new MockClassifier();
  }
}

/**
 * Mayoría de los últimos 10 resultados; solo cuenta si confianza ≥ 0,70 y no es «NINGUNA».
 *
 * Con el instante del cuadro (D-038) también acepta la seña si se mantiene estable
 * `STABLE_MS` con al menos `MIN_STABLE_VOTES` votos y es mayoría: en un portátil a 10 FPS
 * reconoce en ~0,3 s en vez de ~0,6 s. A 30 FPS se comporta igual que antes (6 votos).
 */
export class Smoother {
  private readonly window: TimedPrediction[] = [];

  push(prediction: Prediction, nowMs?: number): Prediction | null {
    this.window.push({ ...prediction, at: nowMs });
    if (this.window.length > SMOOTHING_WINDOW) this.window.shift();
    if (nowMs !== undefined) {
      const span = this.windowSpan();
      while (this.window.length > 0 && (this.window[0].at ?? nowMs) < nowMs - span) this.window.shift();
    }
    const counts = new Map<string, { count: number; confidence: number }>();
    for (const item of this.window) {
      const entry = counts.get(item.label) ?? { count: 0, confidence: 0 };
      counts.set(item.label, {
        count: entry.count + 1,
        confidence: Math.max(entry.confidence, item.confidence),
      });
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

  /**
   * Duración de la ventana: 600 ms, o 4 cuadros del ritmo típico si la cámara va lenta (hasta 2 s).
   * Se usa la mediana de los intervalos: una pausa aislada (cambiar de pestaña) no la amplía.
   */
  private windowSpan(): number {
    const intervals: number[] = [];
    for (let i = 1; i < this.window.length; i += 1) {
      const previous = this.window[i - 1].at;
      const current = this.window[i].at;
      if (previous !== undefined && current !== undefined) intervals.push(current - previous);
    }
    if (intervals.length === 0) return WINDOW_MS;
    intervals.sort((x, y) => x - y);
    const typical = intervals[Math.floor(intervals.length / 2)];
    return Math.min(MAX_WINDOW_MS, Math.max(WINDOW_MS, typical * (MIN_STABLE_VOTES + 1)));
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
