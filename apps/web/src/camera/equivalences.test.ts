// Señas equivalentes para la cámara (D-027).
import { describe, expect, it } from "vitest";
import {
  bestWithEquivalents,
  CAMERA_EQUIVALENCES,
  matchesTarget,
  parseEquivalences,
  withEquivalents,
} from "./equivalences";

describe("equivalencias de la cámara (D-027)", () => {
  const eq = parseEquivalences("slug,equivalente,nota\n# comentario\nletra-b,numero-4,misma forma, sin movimiento\nletra-o,numero-0,x\n");

  it("el mapa es simétrico y la nota puede tener comas", () => {
    expect(eq.get("letra-b")).toEqual(["numero-4"]);
    expect(eq.get("numero-4")).toEqual(["letra-b"]);
    expect(eq.get("letra-o")).toEqual(["numero-0"]);
  });

  it("en una lección se acepta la seña pedida o su equivalente, nada más", () => {
    expect(matchesTarget("numero-4", "letra-b", eq)).toBe(true);
    expect(matchesTarget("letra-b", "numero-4", eq)).toBe(true);
    expect(matchesTarget("letra-b", "letra-b", eq)).toBe(true);
    expect(matchesTarget("letra-a", "letra-b", eq)).toBe(false);
    expect(matchesTarget("numero-0", "letra-b", eq)).toBe(false);
  });

  it("sin contexto se muestran las dos, la reconocida primero", () => {
    expect(withEquivalents("numero-4", eq)).toEqual(["numero-4", "letra-b"]);
    expect(withEquivalents("letra-a", eq)).toEqual(["letra-a"]);
  });

  it("cabecera incorrecta o filas incompletas se ignoran", () => {
    expect(parseEquivalences("a,b\nletra-b,numero-4").size).toBe(0);
    expect(parseEquivalences("slug,equivalente,nota\nletra-b,,x\nletra-c,letra-c,x").size).toBe(0);
  });

  it("content/camera-equivalences.csv trae B = 4", () => {
    expect(matchesTarget("numero-4", "letra-b", CAMERA_EQUIVALENCES)).toBe(true);
  });

  describe("bestWithEquivalents: suma las probabilidades de cada par (D-041)", () => {
    const labels = ["NINGUNA", "letra-a", "letra-w", "numero-3"];

    it("3 (0,45) y W (0,40) juntas pasan el umbral aunque ninguna lo pase sola", () => {
      const best = bestWithEquivalents(Float32Array.from([0.05, 0.1, 0.4, 0.45]), labels, CAMERA_EQUIVALENCES);
      expect(best.confidence).toBeCloseTo(0.85, 5);
    });

    it("el par siempre sale con la misma etiqueta (la primera en orden), para que los votos no se repartan", () => {
      const a = bestWithEquivalents(Float32Array.from([0, 0.1, 0.5, 0.4]), labels, CAMERA_EQUIVALENCES);
      const b = bestWithEquivalents(Float32Array.from([0, 0.1, 0.4, 0.5]), labels, CAMERA_EQUIVALENCES);
      expect(a.label).toBe("letra-w");
      expect(b.label).toBe("letra-w");
      // Y la lección que pide un 3 la acepta.
      expect(matchesTarget(a.label, "numero-3", CAMERA_EQUIVALENCES)).toBe(true);
    });

    it("una seña sin par queda igual", () => {
      const best = bestWithEquivalents(Float32Array.from([0.05, 0.6, 0.2, 0.15]), labels, CAMERA_EQUIVALENCES);
      expect(best.label).toBe("letra-a");
      expect(best.confidence).toBeCloseTo(0.6, 5);
    });

    it("«NINGUNA» no se suma con nada", () => {
      const best = bestWithEquivalents(Float32Array.from([0.5, 0.1, 0.2, 0.2]), labels, CAMERA_EQUIVALENCES);
      expect(best.label).toBe("NINGUNA");
      expect(best.confidence).toBeCloseTo(0.5, 5);
    });

    it("sin equivalencias es el máximo de siempre", () => {
      const best = bestWithEquivalents(Float32Array.from([0.05, 0.1, 0.4, 0.45]), labels, new Map());
      expect(best).toEqual({ label: "numero-3", confidence: expect.closeTo(0.45, 5) });
    });
  });

  it("content/camera-equivalences.csv trae 2 = V y 3 = W (el modelo los confunde)", () => {
    expect(matchesTarget("letra-v", "numero-2", CAMERA_EQUIVALENCES)).toBe(true);
    expect(matchesTarget("numero-2", "letra-v", CAMERA_EQUIVALENCES)).toBe(true);
    expect(matchesTarget("letra-w", "numero-3", CAMERA_EQUIVALENCES)).toBe(true);
    expect(matchesTarget("numero-3", "letra-w", CAMERA_EQUIVALENCES)).toBe(true);
    expect(withEquivalents("numero-3", CAMERA_EQUIVALENCES)).toEqual(["numero-3", "letra-w"]);
    // Solo esos pares: el 2 no acepta la W ni el 3 la V.
    expect(matchesTarget("letra-w", "numero-2", CAMERA_EQUIVALENCES)).toBe(false);
    expect(matchesTarget("letra-v", "numero-3", CAMERA_EQUIVALENCES)).toBe(false);
  });
});
