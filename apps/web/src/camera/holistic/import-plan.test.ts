// Plan de importación: qué se importa, qué queda fuera del mapeo y qué falta tras reanudar.
import { describe, expect, it } from "vitest";
import { groupFiles, parseMapping } from "./importer";
import { planImport, type SavedOutcome } from "./import-plan";
import type { HolisticSample } from "./dataset-v2";

const mapping = parseMapping("fuente,etiqueta_fuente,slug\nLSC-54,Hola,hola\nLSC-54,Chao,adios\n");
const file = (name: string) => new File(["x"], name, { type: "video/mp4" });
const { items } = groupFiles([
  file("Hola__p1__1.mp4"),
  file("Hola__p2__1.mp4"),
  file("Chao__p1__1.mp4"),
  file("Sentarse__p1__1.mp4"),
]);
const sample = (label: string): HolisticSample => ({
  id: "x",
  label,
  collector: "p1",
  dominantHand: "right",
  source: "LSC-54",
  license: "CC BY-NC 4.0",
  quality: { poseRatio: 1, domHandRatio: 1, faceRatio: 0 },
  data: [],
});

describe("planImport", () => {
  it("separa lo que se importará de lo que está fuera del mapeo", () => {
    const plan = planImport(items, "LSC-54", mapping);
    expect(plan.importable.map((i) => i.key)).toEqual(["Chao__p1__1.mp4", "Hola__p1__1.mp4", "Hola__p2__1.mp4"]);
    expect(plan.outsideMapping.map((i) => i.key)).toEqual(["Sentarse__p1__1.mp4"]);
    expect(plan.pending).toEqual(plan.importable);
    expect(plan.restored).toEqual([]);
  });

  it("al reanudar salta lo ya procesado y recupera sus resultados", () => {
    const saved: SavedOutcome[] = [
      { item: "Chao__p1__1.mp4", sample: sample("adios"), reason: null },
      { item: "Hola__p1__1.mp4", sample: null, reason: "Tu mano salió del cuadro" },
    ];
    const plan = planImport(items, "LSC-54", mapping, saved);
    expect(plan.pending.map((i) => i.key)).toEqual(["Hola__p2__1.mp4"]);
    expect(plan.restored).toEqual(saved);
  });

  it("ignora resultados guardados de archivos que ya no están en la selección", () => {
    const saved: SavedOutcome[] = [{ item: "Otro__p9__1.mp4", sample: sample("hola"), reason: null }];
    const plan = planImport(items, "LSC-54", mapping, saved);
    expect(plan.restored).toEqual([]);
    expect(plan.pending).toHaveLength(3);
  });

  it("con otra fuente, nada coincide con el mapeo", () => {
    const plan = planImport(items, "LSC70", mapping);
    expect(plan.importable).toEqual([]);
    expect(plan.outsideMapping).toHaveLength(4);
  });
});
