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

/** La seña y sus equivalentes, en orden estable (la reconocida primero). */
export function withEquivalents(label: string, equivalences: Equivalences = CAMERA_EQUIVALENCES): string[] {
  return [label, ...(equivalences.get(label) ?? [])];
}
