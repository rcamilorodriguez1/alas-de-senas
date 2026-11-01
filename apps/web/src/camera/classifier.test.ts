// Reconocedor (tarea 10.3, §10.2–10.4): suavizado, umbral, timestamps y modo simulado.
import { describe, expect, it, vi } from "vitest";
import { loadClassifier, MIN_VOTES, MockClassifier, MonotonicTimestamps, NONE, Smoother, THRESHOLD } from "./classifier";

describe("Smoother", () => {
  it("devuelve la mayoría de los últimos 10 resultados con su confianza media", () => {
    const smoother = new Smoother();
    let last = null;
    for (let i = 0; i < 6; i += 1) last = smoother.push({ label: "letra-a", confidence: 0.9 });
    for (let i = 0; i < 4; i += 1) last = smoother.push({ label: "letra-b", confidence: 0.95 });
    expect(last).toEqual({ label: "letra-a", confidence: 0.9 });
  });

  it("solo mira los últimos 10: los resultados viejos salen de la ventana", () => {
    const smoother = new Smoother();
    for (let i = 0; i < 10; i += 1) smoother.push({ label: "letra-a", confidence: 0.9 });
    let last = null;
    for (let i = 0; i < 6; i += 1) last = smoother.push({ label: "letra-b", confidence: 0.8 });
    expect(last?.label).toBe("letra-b");
  });

  it("no muestra nada por debajo de 0,70 (R8.2)", () => {
    const smoother = new Smoother();
    let last = null;
    for (let i = 0; i < 10; i += 1) last = smoother.push({ label: "letra-a", confidence: THRESHOLD - 0.01 });
    expect(last).toBeNull();
  });

  it("acepta justo 0,70", () => {
    const smoother = new Smoother();
    let last = null;
    for (let i = 0; i < MIN_VOTES; i += 1) last = smoother.push({ label: "letra-a", confidence: THRESHOLD });
    expect(last?.label).toBe("letra-a");
    expect(last?.confidence).toBeCloseTo(THRESHOLD, 9);
  });

  it("un cuadro aislado no basta: hacen falta 6 votos de la misma etiqueta (B37)", () => {
    const smoother = new Smoother();
    for (let i = 0; i < MIN_VOTES - 1; i += 1) {
      expect(smoother.push({ label: "letra-a", confidence: 0.99 })).toBeNull();
    }
    expect(smoother.push({ label: "letra-a", confidence: 0.99 })?.label).toBe("letra-a");
  });

  it("«NINGUNA» nunca se muestra como seña detectada (R8.2)", () => {
    const smoother = new Smoother();
    let last = null;
    for (let i = 0; i < 10; i += 1) last = smoother.push({ label: NONE, confidence: 0.99 });
    expect(last).toBeNull();
  });

  it("reset vacía la ventana", () => {
    const smoother = new Smoother();
    for (let i = 0; i < 9; i += 1) smoother.push({ label: "letra-a", confidence: 0.9 });
    smoother.reset();
    let last = null;
    for (let i = 0; i < MIN_VOTES; i += 1) last = smoother.push({ label: "letra-b", confidence: 0.9 });
    expect(last?.label).toBe("letra-b");
  });
});

describe("MonotonicTimestamps", () => {
  it("salta los timestamps repetidos o hacia atrás", () => {
    const clock = new MonotonicTimestamps();
    expect(clock.next(10)).toBe(10);
    expect(clock.next(10)).toBeNull();
    expect(clock.next(9)).toBeNull();
    expect(clock.next(11)).toBe(11);
  });
});

describe("loadClassifier", () => {
  it("sin modelo publicado usa el modo simulado sin errores (R8.6)", async () => {
    const fetchFn = vi.fn(async () => new Response("no", { status: 404 }));
    const classifier = await loadClassifier(fetchFn);
    expect(classifier).toBeInstanceOf(MockClassifier);
    expect(classifier.simulated).toBe(true);
    expect(classifier.classify([0])).toEqual({ label: NONE, confidence: 0 });
  });

  it("si labels.json no es una lista de textos, simula", async () => {
    const fetchFn = vi.fn(async () => new Response(JSON.stringify({ a: 1 }), { status: 200 }));
    expect((await loadClassifier(fetchFn)).simulated).toBe(true);
  });

  it("si la red falla, simula", async () => {
    const fetchFn = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    expect((await loadClassifier(fetchFn)).simulated).toBe(true);
  });
});
