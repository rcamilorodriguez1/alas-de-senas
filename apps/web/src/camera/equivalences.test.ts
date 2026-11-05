// Señas equivalentes para la cámara (D-027).
import { describe, expect, it } from "vitest";
import { CAMERA_EQUIVALENCES, matchesTarget, parseEquivalences, withEquivalents } from "./equivalences";

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
});
