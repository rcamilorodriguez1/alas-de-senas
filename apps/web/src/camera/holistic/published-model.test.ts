// El modelo de gestos publicado (public/models/lsc-gestos) es el que el navegador puede usar: si alguien
// lo regenera mal (otra versión del vector, etiquetas desordenadas, GRU con reset_after), esto falla.
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { parseSequenceMeta } from "./sequence-classifier";

const DIR = resolve(__dirname, "../../../public/models/lsc-gestos");
const read = (name: string): unknown => JSON.parse(readFileSync(resolve(DIR, name), "utf-8"));

interface Layer {
  class_name: string;
  config: { reset_after?: boolean; units?: number; batch_input_shape?: (number | null)[] };
}

describe.runIf(existsSync(resolve(DIR, "meta.json")))("modelo de gestos publicado", () => {
  it("meta.json es holistic-v2 válido y coincide con labels.json", () => {
    const labels = read("labels.json") as string[];
    const meta = parseSequenceMeta(read("meta.json"), labels);
    expect(meta).not.toBeNull();
    expect(meta?.labels[0]).toBe("NINGUNA");
    expect(meta?.labels.length).toBeGreaterThanOrEqual(4); // 3–5 señas + NINGUNA (A.8)
  });

  it("model.json: GRU con reset_after=false (B73) y una salida por etiqueta", () => {
    const model = read("model.json") as { modelTopology: { model_config: { config: { layers: Layer[] } } } };
    const layers = model.modelTopology.model_config.config.layers;
    const grus = layers.filter((l) => l.class_name === "GRU");
    expect(grus.length).toBeGreaterThan(0);
    expect(grus.every((l) => l.config.reset_after === false)).toBe(true);
    const dense = layers.filter((l) => l.class_name === "Dense").at(-1);
    expect(dense?.config.units).toBe((read("labels.json") as string[]).length);
  });
});
