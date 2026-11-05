// Contratos del reconocimiento (anexo A.10): la interfaz depende de estas interfaces, no de MediaPipe
// ni de un modelo concreto. `RecognizerFactory` elige extractor y clasificador por `meta.featureVersion`;
// el alfabeto (sin `meta.json` o con «hand-v1») sigue funcionando igual.
import type { Prediction } from "./classifier";

export type FeatureVersion = "hand-v1" | "holistic-v2";

export interface Point2 {
  x: number;
  y: number;
}

/** Puntos para el dibujo superpuesto (coordenadas normalizadas 0–1 de la imagen). */
export interface Overlay {
  dominant: readonly Point2[] | null;
  other: readonly Point2[] | null;
  shoulders: readonly Point2[];
  face: readonly Point2[];
}

export interface ExtractedFrame {
  /** Vector del cuadro, o null si el cuadro no es válido (sin mano o sin pose). */
  features: Float32Array | readonly number[] | null;
  /** holistic-v2: el mismo cuadro tomando la otra mano como dominante (por si la persona firma con ella). */
  alternate?: Float32Array | null;
  overlay: Overlay;
}

export interface FeatureExtractor {
  readonly featureVersion: FeatureVersion;
  readonly featureSize: number;
  extract(video: HTMLVideoElement, timestampMs: number): ExtractedFrame | null;
  close(): void;
}

/** Un cuadro (estático) o 30 cuadros (secuencia) → etiqueta y confianza. */
export interface SignClassifier<Input> {
  readonly featureVersion: FeatureVersion;
  readonly simulated: boolean;
  readonly labels: readonly string[];
  classify(input: Input): Prediction;
  dispose(): void;
}

export type RecognizerKind = "static" | "sequence";

/** Qué extractor y clasificador corresponden a un modelo, según su `meta.json` (null = no soportado). */
export const RecognizerFactory = {
  kindFor(meta: unknown): RecognizerKind | null {
    if (meta === null || meta === undefined) return "static"; // alfabeto sin meta.json
    if (typeof meta !== "object" || !("featureVersion" in meta)) return null;
    if (meta.featureVersion === "hand-v1") return "static";
    if (meta.featureVersion === "holistic-v2") return "sequence";
    return null;
  },

  /** Lee `meta.json` de la carpeta del modelo: null si no existe (modelo del alfabeto). */
  async readMeta(dir: string, fetchFn: typeof fetch = fetch): Promise<unknown> {
    try {
      const response = await fetchFn(`${dir}/meta.json`);
      if (!response.ok) return null;
      return (await response.json()) as unknown;
    } catch {
      return null;
    }
  },
};
