// `dataset.json` del colector (§10.5): vectores YA normalizados; Python nunca recalcula puntos (D11).
import { FEATURE_SIZE, FEATURE_VERSION, TASKS_VISION_VERSION } from "./normalize";

export const NONE_LABEL = "NINGUNA";

export interface Sample {
  label: string;
  features: number[];
}

export interface Dataset {
  featureVersion: string;
  featureSize: number;
  collector: string;
  tasksVision: string;
  createdAt: string;
  samples: Sample[];
}

export function buildDataset(collector: string, samples: readonly Sample[], now: Date = new Date()): Dataset {
  return {
    featureVersion: FEATURE_VERSION,
    featureSize: FEATURE_SIZE,
    collector: collector.trim(),
    tasksVision: TASKS_VISION_VERSION,
    createdAt: now.toISOString(),
    samples: samples.filter((s) => s.features.length === FEATURE_SIZE),
  };
}

export function countByLabel(samples: readonly Sample[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const sample of samples) counts.set(sample.label, (counts.get(sample.label) ?? 0) + 1);
  return counts;
}

/** Descarga el JSON en el navegador (sin servidor: los datos no salen salvo que el admin los comparta). */
export function downloadDataset(dataset: Dataset): void {
  const blob = new Blob([JSON.stringify(dataset)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `dataset-${dataset.collector || "anonimo"}-${dataset.createdAt.slice(0, 10)}.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000); // algunos navegadores cortan la descarga si se revoca ya
}
