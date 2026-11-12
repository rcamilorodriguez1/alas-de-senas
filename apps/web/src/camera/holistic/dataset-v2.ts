// Formato del dataset `holistic-v2` (anexo A.6): solo números (sin imágenes ni la malla de la cara, A.9).
import { NONE } from "../classifier";
import { HOLISTIC_FEATURE_VERSION, HOLISTIC_V2_SIZE, type DominantHand } from "./frame";
import { SEQUENCE_DURATION_MS, SEQUENCE_FRAMES, type SequenceQuality } from "./sequencer";

export const TASKS_VISION_VERSION = "1.1.0"; // fija en package.json (D-019)

export interface HolisticSample {
  id: string;
  label: string;
  collector: string;
  dominantHand: DominantHand;
  source: string;
  license: string;
  quality: SequenceQuality;
  data: number[][];
  /** Archivo y etiqueta originales (D-044): permite filtrar después, p. ej. quitar una seña de NINGUNA. */
  origin?: { file: string; sourceLabel: string };
}

export interface HolisticDataset {
  format: "alas-dataset";
  featureVersion: typeof HOLISTIC_FEATURE_VERSION;
  featureSize: number;
  frames: number;
  durationSec: number;
  /** false si las caras no se ven (dataset pixelado): el entrenador ignora la expresión facial. */
  faceFeatures: boolean;
  createdWith: { tasksVision: string; app: string };
  samples: HolisticSample[];
}

/** 5 decimales bastan (los puntos de MediaPipe no son más precisos) y el archivo pesa la mitad. */
function compact(frames: readonly Float32Array[]): number[][] {
  return frames.map((frame) => Array.from(frame, (v) => Number(v.toFixed(5))));
}

export function makeSample(input: {
  label: string;
  collector: string;
  dominantHand: DominantHand;
  source: string;
  license: string;
  quality: SequenceQuality;
  frames: readonly Float32Array[];
  id?: string;
  origin?: { file: string; sourceLabel: string };
}): HolisticSample {
  if (input.frames.length !== SEQUENCE_FRAMES || input.frames.some((f) => f.length !== HOLISTIC_V2_SIZE)) {
    throw new Error(`Cada muestra debe tener ${SEQUENCE_FRAMES} cuadros de ${HOLISTIC_V2_SIZE} valores.`);
  }
  if (!input.source.trim() || !input.license.trim()) throw new Error("Fuente y licencia son obligatorias (A.6).");
  if (!input.collector.trim()) throw new Error("Falta el alias de quien graba.");
  return {
    id: input.id ?? crypto.randomUUID(),
    label: input.label,
    collector: input.collector.trim(),
    dominantHand: input.dominantHand,
    source: input.source.trim(),
    license: input.license.trim(),
    quality: input.quality,
    data: compact(input.frames),
    ...(input.origin ? { origin: { ...input.origin } } : {}),
  };
}

export function buildHolisticDataset(samples: readonly HolisticSample[], faceFeatures: boolean, app = "dev"): HolisticDataset {
  return {
    format: "alas-dataset",
    featureVersion: HOLISTIC_FEATURE_VERSION,
    featureSize: HOLISTIC_V2_SIZE,
    frames: SEQUENCE_FRAMES,
    durationSec: SEQUENCE_DURATION_MS / 1000,
    faceFeatures,
    createdWith: { tasksVision: TASKS_VISION_VERSION, app },
    samples: [...samples],
  };
}

export function countByLabel(samples: readonly { label: string }[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const s of samples) counts.set(s.label, (counts.get(s.label) ?? 0) + 1);
  return counts;
}

export function isNone(label: string): boolean {
  return label === NONE;
}

export function downloadJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
