// Etiquetas del modelo propio (§10.1, §10.5): qué señas puede reconocer la cámara.
import { MODEL_DIR } from "./classifier";

interface LayerJson {
  class_name?: string;
  config?: { units?: number };
}

interface ModelJson {
  modelTopology?: {
    model_config?: { config?: { layers?: LayerJson[] } };
    config?: { layers?: LayerJson[] };
  };
}

/** Número de salidas del modelo exportado (unidades de la última capa `Dense`), o null. */
export function modelOutputUnits(modelJson: unknown): number | null {
  const topology = (modelJson as ModelJson | null)?.modelTopology;
  const layers = topology?.model_config?.config?.layers ?? topology?.config?.layers ?? [];
  const dense = layers.filter((layer) => layer.class_name === "Dense");
  const units = dense.at(-1)?.config?.units;
  return typeof units === "number" ? units : null;
}

/** `labels.json` válido para el modelo: una etiqueta por salida, sin repetidas (R4.8, §10.5). */
export function labelsMatchModel(modelJson: unknown, labels: unknown): boolean {
  if (!Array.isArray(labels) || !labels.every((label) => typeof label === "string")) return false;
  return new Set(labels).size === labels.length && modelOutputUnits(modelJson) === labels.length;
}

let cached: Promise<string[]> | null = null;

/** Etiquetas publicadas (en caché); lista vacía si aún no hay modelo entrenado (R8.6). */
export function fetchModelLabels(fetchFn: typeof fetch = fetch): Promise<string[]> {
  cached ??= fetchFn(`${MODEL_DIR}/labels.json`)
    .then(async (response) => {
      if (!response.ok) return [];
      const labels = (await response.json()) as unknown;
      return Array.isArray(labels) ? labels.filter((label): label is string => typeof label === "string") : [];
    })
    .catch(() => []);
  return cached;
}

export function resetModelLabelsCache(): void {
  cached = null;
}
