// Plan de una importación (D-044): qué archivos se importarán, cuáles quedan fuera del mapeo y,
// al reanudar, cuáles faltan. Función pura: la página solo la muestra y la ejecuta.
import type { HolisticSample } from "./dataset-v2";
import { resolveLabel, type ImportItem, type MappingRow } from "./importer";

/** Resultado de un archivo ya procesado (se guarda en el navegador para poder continuar). */
export interface SavedOutcome {
  item: string;
  sample: HolisticSample | null;
  reason: string | null;
}

export interface ImportPlan {
  /** Archivos con una seña del mapeo: son los que se procesan. */
  importable: ImportItem[];
  /** Archivos cuya seña no está en el mapeo de esa fuente: no se procesan. */
  outsideMapping: ImportItem[];
  /** Los importables que todavía no tienen resultado guardado. */
  pending: ImportItem[];
  /** Resultados guardados que corresponden a archivos de esta selección. */
  restored: SavedOutcome[];
}

export function planImport(
  items: readonly ImportItem[],
  source: string,
  mapping: readonly MappingRow[],
  saved: readonly SavedOutcome[] = [],
): ImportPlan {
  const importable: ImportItem[] = [];
  const outsideMapping: ImportItem[] = [];
  for (const item of items) {
    (resolveLabel(item.label, source, mapping) ? importable : outsideMapping).push(item);
  }
  const keys = new Set(importable.map((item) => item.key));
  const restored = saved.filter((outcome) => keys.has(outcome.item));
  const processed = new Set(restored.map((outcome) => outcome.item));
  return {
    importable,
    outsideMapping,
    pending: importable.filter((item) => !processed.has(item.key)),
    restored,
  };
}
