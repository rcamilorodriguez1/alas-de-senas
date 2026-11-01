// dataset.json del colector (tarea 10.5, §10.5).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { buildDataset, countByLabel } from "./dataset";
import { FEATURE_SIZE, TASKS_VISION_VERSION } from "./normalize";

const vector = (value: number) => Array.from({ length: FEATURE_SIZE }, () => value);

describe("buildDataset", () => {
  it("lleva hand-v1, 63 valores, alias y versión de MediaPipe", () => {
    const dataset = buildDataset("  ana ", [{ label: "letra-a", features: vector(0.1) }], new Date("2026-11-03T15:00:00Z"));
    expect(dataset).toEqual({
      featureVersion: "hand-v1",
      featureSize: 63,
      collector: "ana",
      tasksVision: TASKS_VISION_VERSION,
      createdAt: "2026-11-03T15:00:00.000Z",
      samples: [{ label: "letra-a", features: vector(0.1) }],
    });
  });

  it("descarta muestras con un tamaño distinto de 63", () => {
    const dataset = buildDataset("ana", [
      { label: "letra-a", features: [1, 2, 3] },
      { label: "NINGUNA", features: vector(0) },
    ]);
    expect(dataset.samples.map((s) => s.label)).toEqual(["NINGUNA"]);
  });

  it("la versión de MediaPipe coincide con la instalada (package.json)", () => {
    const pkg = JSON.parse(readFileSync(join(process.cwd(), "package.json"), "utf-8")) as {
      dependencies: Record<string, string>;
    };
    expect(pkg.dependencies["@mediapipe/tasks-vision"]).toBe(TASKS_VISION_VERSION);
  });
});

describe("countByLabel", () => {
  it("cuenta muestras por clase", () => {
    const counts = countByLabel([
      { label: "letra-a", features: [] },
      { label: "letra-a", features: [] },
      { label: "NINGUNA", features: [] },
    ]);
    expect(Object.fromEntries(counts)).toEqual({ "letra-a": 2, NINGUNA: 1 });
  });
});
