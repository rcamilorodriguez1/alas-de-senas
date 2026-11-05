// Paridad Python ↔ TypeScript (anexo A.8, H11): los mismos casos que prueba pytest en
// ml/tests/test_train_sequence.py. Si un lado cambia, la prueba del otro falla.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { HOLISTIC_V2_SIZE, maskFace, mirrorFrame, normalizeFeatures } from "./frame";

interface ParityCase {
  name: string;
  frame: number[];
  mean: number[];
  std: number[];
  mirror: number[];
  maskFace: number[];
  normalize: number[];
}

const payload = JSON.parse(
  readFileSync(resolve(__dirname, "../../../../../ml/fixtures/holistic_v2_cases.json"), "utf-8"),
) as { featureVersion: string; featureSize: number; cases: ParityCase[] };

describe("paridad con Python (ml/fixtures/holistic_v2_cases.json)", () => {
  it("misma versión y tamaño del vector", () => {
    expect(payload.featureVersion).toBe("holistic-v2");
    expect(payload.featureSize).toBe(HOLISTIC_V2_SIZE);
    expect(payload.cases.length).toBeGreaterThanOrEqual(3);
  });

  for (const c of payload.cases) {
    it(`reflejo, máscara facial y normalización: ${c.name}`, () => {
      const frame = Float32Array.from(c.frame);
      expect(Array.from(mirrorFrame(frame))).toEqual(Array.from(Float32Array.from(c.mirror)));
      expect(Array.from(maskFace(frame))).toEqual(Array.from(Float32Array.from(c.maskFace)));
      const normalized = normalizeFeatures(frame, c.mean, c.std);
      normalized.forEach((v, i) => expect(Math.abs(v - c.normalize[i])).toBeLessThanOrEqual(1e-5 * Math.max(1, Math.abs(c.normalize[i]))));
    });
  }
});
