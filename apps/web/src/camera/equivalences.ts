// Señas con la misma forma de mano (D-027, `content/camera-equivalences.csv`): el modelo las mantiene
// separadas; encima, el contexto decide. En una lección se acepta cualquiera del par; sin contexto
// (/camara) se muestran las dos.
import equivalencesCsv from "../../../../content/camera-equivalences.csv?raw";

export type Equivalences = ReadonlyMap<string, readonly string[]>;

/** `slug,equivalente,nota` → mapa simétrico slug → equivalentes (la nota puede tener comas). */
export function parseEquivalences(csv: string): Equivalences {
  const [header, ...lines] = csv.split(/\r?\n/).filter((line) => line.trim() && !line.startsWith("#"));
  const map = new Map<string, string[]>();
  if (header?.trim() !== "slug,equivalente,nota") return map;
  const add = (a: string, b: string) => {
    const list = map.get(a) ?? [];
    if (!list.includes(b)) list.push(b);
    map.set(a, list);
  };
  for (const line of lines) {
    const [a = "", b = ""] = line.split(",").map((cell) => cell.trim());
    if (!a || !b || a === b) continue;
    add(a, b);
    add(b, a);
  }
  return map;
}

export const CAMERA_EQUIVALENCES = parseEquivalences(equivalencesCsv);

/** ¿La seña reconocida cuenta para la pedida? La misma o una equivalente. */
export function matchesTarget(label: string, target: string, equivalences: Equivalences = CAMERA_EQUIVALENCES): boolean {
  return label === target || (equivalences.get(target)?.includes(label) ?? false);
}

/**
 * La seña más probable sumando las probabilidades de cada par equivalente (D-041). Si el modelo
 * duda entre 3 (0,45) y W (0,40), el par «3 / W» tiene 0,85 y pasa el umbral, que sigue en 0,70.
 * El par sale siempre con la misma etiqueta (la primera en orden alfabético) para que los votos
 * del suavizado no se repartan entre las dos.
 */
export function bestWithEquivalents(
  scores: ArrayLike<number>,
  labels: readonly string[],
  equivalences: Equivalences = CAMERA_EQUIVALENCES,
): { label: string; confidence: number } {
  const totals = new Map<string, number>();
  for (let i = 0; i < labels.length; i += 1) {
    const group = canonical(labels[i], equivalences);
    totals.set(group, (totals.get(group) ?? 0) + (scores[i] ?? 0));
  }
  let label = labels[0] ?? "";
  let confidence = -Infinity;
  for (const [group, total] of totals) {
    if (total > confidence) {
      label = group;
      confidence = total;
    }
  }
  return { label, confidence: Math.max(0, confidence) };
}

function canonical(label: string, equivalences: Equivalences): string {
  return [label, ...(equivalences.get(label) ?? [])].sort()[0] ?? label;
}

/** La seña y sus equivalentes, en orden estable (la reconocida primero). */
export function withEquivalents(label: string, equivalences: Equivalences = CAMERA_EQUIVALENCES): string[] {
  return [label, ...(equivalences.get(label) ?? [])];
}
