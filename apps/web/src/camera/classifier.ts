// Clasificación de los 63 valores normalizados (§10.2): modelo propio de TensorFlow.js o, mientras
// no exista, `MockClassifier` (R8.6). Toda predicción va dentro de `tf.tidy()` (B: fugas de tfjs).
import type * as tfType from "@tensorflow/tfjs";

export const NONE = "NINGUNA";
export const THRESHOLD = 0.7;
export const SMOOTHING_WINDOW = 10;
/** Votos mínimos de la misma etiqueta en la ventana: un cuadro aislado nunca basta (B37). */
export const MIN_VOTES = 6;
export const MODEL_DIR = "/models/lsc-alfabeto";

export interface Prediction {
  label: string;
  confidence: number;
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

/** Carga el modelo de `/models/lsc-alfabeto`; si no existe o no coincide con `labels.json`, simula. */
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
    return new TfjsClassifier(tf, model, labels as string[]);
  } catch {
    return new MockClassifier();
  }
}

/** Mayoría de los últimos 10 resultados; solo cuenta si confianza ≥ 0,70 y no es «NINGUNA». */
export class Smoother {
  private readonly window: Prediction[] = [];

  push(prediction: Prediction): Prediction | null {
    this.window.push(prediction);
    if (this.window.length > SMOOTHING_WINDOW) this.window.shift();
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
    if (winner === null || winner === NONE || top < MIN_VOTES) return null;
    // Confianza media de esa etiqueta en la ventana: un pico aislado no basta.
    const matches = this.window.filter((item) => item.label === winner);
    const confidence = matches.reduce((sum, item) => sum + item.confidence, 0) / matches.length;
    // Tolerancia para el error de redondeo de la media (0,7 × 6 / 6 ≠ 0,7 exacto en coma flotante).
    return confidence + 1e-9 >= THRESHOLD ? { label: winner, confidence } : null;
  }

  reset(): void {
    this.window.length = 0;
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
