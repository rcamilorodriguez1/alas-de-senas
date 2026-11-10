// Reconocedor (tarea 10.3, §10.2–10.4): suavizado, umbral, timestamps y modo simulado.
import { describe, expect, it, vi } from "vitest";
import {
  DenseClassifier,
  loadClassifier,
  MIN_STABLE_VOTES,
  MIN_VOTES,
  MockClassifier,
  MonotonicTimestamps,
  NONE,
  Smoother,
  STABLE_MS,
  THRESHOLD,
  WINDOW_MS,
} from "./classifier";

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

describe("Smoother con tiempo (prueba D-038: reconocer igual de rápido en equipos lentos)", () => {
  const a = { label: "letra-a", confidence: 0.9 };

  it("a 30 FPS se comporta igual que antes: 6 votos", () => {
    const smoother = new Smoother();
    for (let i = 0; i < MIN_VOTES - 1; i += 1) expect(smoother.push(a, i * 33)).toBeNull();
    expect(smoother.push(a, (MIN_VOTES - 1) * 33)?.label).toBe("letra-a");
  });

  it(`a 10 FPS basta con la seña estable ${STABLE_MS} ms (${MIN_STABLE_VOTES} votos o más), sin esperar 6 cuadros`, () => {
    const smoother = new Smoother();
    expect(smoother.push(a, 0)).toBeNull();
    expect(smoother.push(a, 100)).toBeNull();
    expect(smoother.push(a, 200)).toBeNull(); // 3 votos, pero solo 200 ms
    expect(smoother.push(a, 300)?.label).toBe("letra-a"); // 4 votos en 300 ms
  });

  it("un cuadro aislado sigue sin bastar aunque pase mucho tiempo (B37)", () => {
    const smoother = new Smoother();
    expect(smoother.push(a, 0)).toBeNull();
    expect(smoother.push(a, 2000)).toBeNull();
  });

  it(`hacen falta al menos ${MIN_STABLE_VOTES} votos aunque estén separados`, () => {
    const smoother = new Smoother();
    expect(smoother.push(a, 0)).toBeNull();
    expect(smoother.push(a, 300)).toBeNull(); // 2 votos en 300 ms
  });

  it("la seña estable tiene que ser mayoría en la ventana", () => {
    const smoother = new Smoother();
    const b = { label: "letra-b", confidence: 0.9 };
    smoother.push(a, 0);
    smoother.push(b, 50);
    smoother.push(a, 100);
    smoother.push(b, 150);
    smoother.push(b, 200);
    expect(smoother.push(a, 300)).toBeNull(); // «a» tiene 3 de 6: no es mayoría
  });

  it(`los resultados de hace más de ${WINDOW_MS} ms salen de la ventana`, () => {
    const smoother = new Smoother();
    smoother.push(a, 0);
    smoother.push(a, 100);
    smoother.push(a, 200);
    // Después de una pausa larga, los votos viejos ya no cuentan.
    expect(smoother.push(a, 200 + WINDOW_MS + 1)).toBeNull();
  });

  it("sigue respetando el umbral de 0,70 (R8.2)", () => {
    const smoother = new Smoother();
    const low = { label: "letra-a", confidence: THRESHOLD - 0.01 };
    let last = null;
    for (let i = 0; i < 5; i += 1) last = smoother.push(low, i * 100);
    expect(last).toBeNull();
  });

  it("«NINGUNA» nunca se muestra (R8.2)", () => {
    const smoother = new Smoother();
    let last = null;
    for (let i = 0; i < 5; i += 1) last = smoother.push({ label: NONE, confidence: 0.99 }, i * 100);
    expect(last).toBeNull();
  });
});

describe("DenseClassifier", () => {
  it("elige la etiqueta con mayor puntaje usando la red en JavaScript", () => {
    const network = { inputSize: 2, outputSize: 3, predict: () => Float32Array.from([0.1, 0.7, 0.2]) };
    const classifier = new DenseClassifier(network, ["letra-a", "letra-b", "letra-c"]);
    expect(classifier.simulated).toBe(false);
    expect(classifier.classify([0, 0])).toEqual({ label: "letra-b", confidence: expect.closeTo(0.7, 5) });
  });

  it("con equivalencias suma el par (D-041): B 0,4 + 4 0,35 = 0,75", () => {
    const network = { inputSize: 2, outputSize: 3, predict: () => Float32Array.from([0.25, 0.4, 0.35]) };
    const equivalences = new Map([
      ["letra-b", ["numero-4"]],
      ["numero-4", ["letra-b"]],
    ]);
    const classifier = new DenseClassifier(network, ["NINGUNA", "letra-b", "numero-4"], equivalences);
    expect(classifier.classify([0, 0])).toEqual({ label: "letra-b", confidence: expect.closeTo(0.75, 5) });
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
