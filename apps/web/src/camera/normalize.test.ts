// normalizeLandmarks (tarea 10.2, §10.3): una sola función para recolectar, entrenar e inferir.
import { describe, expect, it } from "vitest";
import { FEATURE_SIZE, normalizeLandmarks, type Landmark } from "./normalize";

/** 21 puntos: muñeca en (0.5, 0.5, 0) y el punto 9 a 0.2 hacia arriba; el resto en una diagonal. */
function hand(): Landmark[] {
  return Array.from({ length: 21 }, (_, i) => {
    if (i === 0) return { x: 0.5, y: 0.5, z: 0 };
    if (i === 9) return { x: 0.5, y: 0.3, z: 0 };
    return { x: 0.5 + i * 0.01, y: 0.5 - i * 0.01, z: i * 0.001 };
  });
}

function moved(points: Landmark[], dx: number, dy: number, scale: number): Landmark[] {
  const [wrist] = points;
  return points.map((p) => ({
    x: wrist.x + dx + (p.x - wrist.x) * scale,
    y: wrist.y + dy + (p.y - wrist.y) * scale,
    z: p.z * scale,
  }));
}

function expectClose(actual: number[], expected: number[]) {
  expect(actual).toHaveLength(expected.length);
  actual.forEach((value, i) => expect(value).toBeCloseTo(expected[i], 6));
}

describe("normalizeLandmarks", () => {
  it("devuelve 63 valores con la muñeca en el origen y el punto 9 a distancia 1", () => {
    const result = normalizeLandmarks(hand(), "Right");
    expect(FEATURE_SIZE).toBe(63);
    expect(result).not.toBeNull();
    const values = result ?? [];
    expect(values).toHaveLength(63);
    expectClose(values.slice(0, 3), [0, 0, 0]);
    expectClose(values.slice(27, 30), [0, -1, 0]); // punto 9: (0, -0.2, 0) / 0.2
  });

  it("valores conocidos: el punto 1 de la mano derecha", () => {
    const values = normalizeLandmarks(hand(), "Right") ?? [];
    // (0.51 − 0.5, 0.49 − 0.5, 0.001 − 0) / 0.2
    expectClose(values.slice(3, 6), [0.05, -0.05, 0.005]);
  });

  it("es invariante a traslación y escala", () => {
    const base = normalizeLandmarks(hand(), "Right") ?? [];
    const other = normalizeLandmarks(moved(hand(), 0.13, -0.07, 1.7), "Right") ?? [];
    expectClose(other, base);
  });

  it("la mano izquierda se refleja (x → 1 − x): un solo modelo para ambas manos", () => {
    const left = hand().map((p) => ({ ...p, x: 1 - p.x }));
    expectClose(normalizeLandmarks(left, "Left") ?? [], normalizeLandmarks(hand(), "Right") ?? []);
  });

  it("descarta el cuadro si la distancia muñeca–punto 9 es menor que 1e-6", () => {
    const collapsed = hand().map((p, i) => (i === 9 ? { x: 0.5, y: 0.5, z: 0 } : p));
    expect(normalizeLandmarks(collapsed, "Right")).toBeNull();
  });

  it("descarta entradas que no tienen 21 puntos", () => {
    expect(normalizeLandmarks(hand().slice(0, 20), "Right")).toBeNull();
    expect(normalizeLandmarks([], "Right")).toBeNull();
  });

  it("no modifica la entrada", () => {
    const points = hand();
    const copy = structuredClone(points);
    normalizeLandmarks(points, "Left");
    expect(points).toEqual(copy);
  });
});

describe("pickSigningHand (D-020)", () => {
  it("elige la mano más alta (la que hace la seña), no la que cuelga en reposo", async () => {
    const { pickSigningHand } = await import("./normalize");
    const resting = Array.from({ length: 21 }, () => ({ x: 0.3, y: 0.9, z: 0 }));
    const signing = Array.from({ length: 21 }, () => ({ x: 0.6, y: 0.4, z: 0 }));
    const picked = pickSigningHand([resting, signing], [[{ categoryName: "Left" }], [{ categoryName: "Right" }]]);
    expect(picked?.points).toBe(signing);
    expect(picked?.side).toBe("Right");
  });

  it("sin manos devuelve null y con una sola la usa", async () => {
    const { pickSigningHand } = await import("./normalize");
    expect(pickSigningHand([], [])).toBeNull();
    const only = Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5, z: 0 }));
    expect(pickSigningHand([only], [[{ categoryName: "Left" }]])?.side).toBe("Left");
  });
});
