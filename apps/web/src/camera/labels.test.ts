// labels.json ↔ salidas del modelo (tarea 10.7, §10.5).
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchModelLabels, labelsMatchModel, modelOutputUnits, resetModelLabelsCache } from "./labels";

const SMOKE = join(process.cwd(), "..", "..", "ml", "fixtures", "tfjs-smoke", "static", "model.json");
const PUBLISHED = join(process.cwd(), "public", "models", "lsc-alfabeto");

afterEach(() => resetModelLabelsCache());

describe("modelOutputUnits y labelsMatchModel", () => {
  it("lee las salidas de un modelo real convertido desde Python (fixture del kit)", () => {
    const model = JSON.parse(readFileSync(SMOKE, "utf-8")) as unknown;
    expect(modelOutputUnits(model)).toBe(4);
    expect(labelsMatchModel(model, ["NINGUNA", "letra-a", "letra-b", "letra-c"])).toBe(true);
    expect(labelsMatchModel(model, ["NINGUNA", "letra-a", "letra-b"])).toBe(false);
    expect(labelsMatchModel(model, ["NINGUNA", "letra-a", "letra-a", "letra-b"])).toBe(false);
    expect(labelsMatchModel(model, { a: 1 })).toBe(false);
  });

  it("el modelo publicado (si ya existe) tiene una etiqueta por salida", () => {
    // Antes de entrenar (tarea 10.8) no hay carpeta: la app funciona en modo simulado (R8.6).
    if (!existsSync(join(PUBLISHED, "model.json"))) return;
    const model = JSON.parse(readFileSync(join(PUBLISHED, "model.json"), "utf-8")) as unknown;
    const labels = JSON.parse(readFileSync(join(PUBLISHED, "labels.json"), "utf-8")) as unknown;
    expect(labelsMatchModel(model, labels)).toBe(true);
  });

  it("un modelo sin capas Dense no tiene salidas conocidas", () => {
    expect(modelOutputUnits({ modelTopology: { config: { layers: [] } } })).toBeNull();
    expect(modelOutputUnits(null)).toBeNull();
  });
});

describe("fetchModelLabels", () => {
  it("sin modelo publicado devuelve una lista vacía", async () => {
    const fetchFn = vi.fn(async () => new Response("", { status: 404 }));
    expect(await fetchModelLabels(fetchFn)).toEqual([]);
  });

  it("devuelve las etiquetas y las guarda en caché", async () => {
    const fetchFn = vi.fn(async () => new Response(JSON.stringify(["NINGUNA", "letra-a"]), { status: 200 }));
    expect(await fetchModelLabels(fetchFn)).toEqual(["NINGUNA", "letra-a"]);
    await fetchModelLabels(fetchFn);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });
});
