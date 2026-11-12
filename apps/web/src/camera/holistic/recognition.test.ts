// Fábrica de reconocedores (A.10), delegados (A.2.1), guía (A.5), FPS (A.8.1), meta.json (H5),
// retroalimentación de Tomi y formato del dataset (A.6).
import { describe, expect, it, vi } from "vitest";
import { NONE } from "../classifier";
import { RecognizerFactory, type Overlay } from "../recognizer";
import { buildHolisticDataset, makeSample } from "./dataset-v2";
import { createWithFallback, SilentGpuGuard } from "./extractor";
import { tomiFeedback } from "./feedback";
import { BLENDSHAPES, HOLISTIC_V2_SIZE, LAYOUT, maskFace, PRESENCE_OFFSET } from "./frame";
import { FpsMeter, FrameThrottle, guidanceMessages, guideInputOf, meanLuminance, readyToRecord } from "./guide";
import { decide, parseSequenceMeta, prepareSequence, type SequenceMeta } from "./sequence-classifier";
import { SEQUENCE_FRAMES } from "./sequencer";

const zeros = () => Array.from({ length: HOLISTIC_V2_SIZE }, () => 0);
const ones = () => Array.from({ length: HOLISTIC_V2_SIZE }, () => 1);
const rawMeta = (overrides: Record<string, unknown> = {}) => ({
  featureVersion: "holistic-v2",
  featureSize: 159,
  frames: 30,
  durationSec: 2,
  threshold: 0.7,
  mean: zeros(),
  std: ones(),
  labels: [NONE, "hola", "adios"],
  ...overrides,
});

describe("RecognizerFactory", () => {
  it("elige el clasificador por featureVersion; el alfabeto sin meta.json sigue estático", () => {
    expect(RecognizerFactory.kindFor(null)).toBe("static");
    expect(RecognizerFactory.kindFor({ featureVersion: "hand-v1" })).toBe("static");
    expect(RecognizerFactory.kindFor({ featureVersion: "holistic-v2" })).toBe("sequence");
    expect(RecognizerFactory.kindFor({ featureVersion: "holistic-v9" })).toBeNull();
    expect(RecognizerFactory.kindFor("x")).toBeNull();
  });

  it("readMeta: null si no hay meta.json o la red falla", async () => {
    const missing = vi.fn().mockResolvedValue(new Response("", { status: 404 }));
    expect(await RecognizerFactory.readMeta("/models/x", missing)).toBeNull();
    const failing = vi.fn().mockRejectedValue(new Error("red"));
    expect(await RecognizerFactory.readMeta("/models/x", failing)).toBeNull();
    const ok = vi.fn().mockResolvedValue(new Response(JSON.stringify({ featureVersion: "holistic-v2" })));
    expect(await RecognizerFactory.readMeta("/models/x", ok)).toEqual({ featureVersion: "holistic-v2" });
    expect(ok).toHaveBeenCalledWith("/models/x/meta.json");
  });
});

describe("delegados de MediaPipe (A.2.1)", () => {
  it("GPU → CPU: si la GPU falla al crear, usa CPU y registra el aviso", async () => {
    const warn = vi.fn();
    const make = vi.fn(async (d: "GPU" | "CPU") => {
      if (d === "GPU") throw new Error("sin WebGL");
      return "detector";
    });
    expect(await createWithFallback(make, ["GPU", "CPU"], warn)).toEqual({ instance: "detector", delegate: "CPU" });
    expect(warn).toHaveBeenCalledOnce();
    await expect(createWithFallback(async () => Promise.reject(new Error("x")), ["CPU"], warn)).rejects.toThrow("x");
  });

  it("SilentGpuGuard: 60 cuadros vacíos seguidos piden pasar a CPU; uno con detección reinicia", () => {
    const guard = new SilentGpuGuard(3);
    expect(guard.push(false)).toBe(false);
    expect(guard.push(false)).toBe(false);
    expect(guard.push(true)).toBe(false);
    expect([guard.push(false), guard.push(false), guard.push(false)]).toEqual([false, false, true]);
  });

  it("SilentGpuGuard: errores seguidos al detectar con GPU también piden CPU; un cuadro bueno reinicia", () => {
    const guard = new SilentGpuGuard(60, 2);
    expect(guard.pushError()).toBe(false);
    guard.push(true);
    expect(guard.pushError()).toBe(false);
    expect(guard.pushError()).toBe(true);
  });
});

describe("guía de captura (A.5)", () => {
  const hand = (x: number) => Array.from({ length: 21 }, () => ({ x, y: 0.5 }));
  const overlay = (o: Partial<Overlay> = {}): Overlay => ({
    dominant: hand(0.5),
    other: null,
    shoulders: [{ x: 0.4, y: 0.7 }, { x: 0.6, y: 0.7 }],
    face: [{ x: 0.5, y: 0.3 }],
    ...o,
  });

  it("todo visible: sin mensajes y se puede grabar", () => {
    const input = guideInputOf(overlay(), 0.6);
    expect(guidanceMessages(input)).toEqual([]);
    expect(readyToRecord(input)).toBe(true);
  });

  it("avisa cara, hombros, manos fuera del cuadro y poca luz; sin mano no se graba", () => {
    const input = guideInputOf(overlay({ face: [], shoulders: [], dominant: hand(0.995) }), 0.1);
    expect(guidanceMessages(input)).toEqual([
      "Hay poca luz",
      "No veo tu cara",
      "No veo tus hombros, aléjate un poco",
      "Tus manos salen del cuadro",
    ]);
    expect(readyToRecord(input)).toBe(false);
    expect(readyToRecord(guideInputOf(overlay({ dominant: null }), 0.6))).toBe(false);
    expect(guidanceMessages(guideInputOf(null, null))).toContain("No veo tu cara");
    // Modelo sin rostro: no se pide la cara para grabar.
    const noFace = guideInputOf(overlay({ face: [] }), 0.6);
    expect(guidanceMessages(noFace, false)).toEqual([]);
    expect(readyToRecord(noFace, false)).toBe(true);
    expect(readyToRecord(noFace)).toBe(false);
    // «NINGUNA»: se puede grabar con las manos abajo.
    const noHands = guideInputOf(overlay({ dominant: null }), 0.6);
    expect(readyToRecord(noHands, true, false)).toBe(true);
    expect(readyToRecord(noHands)).toBe(false);
  });

  it("luminancia media de RGBA entre 0 y 1", () => {
    expect(meanLuminance(new Uint8ClampedArray([255, 255, 255, 255, 0, 0, 0, 255]))).toBeCloseTo(0.5);
    expect(meanLuminance(new Uint8ClampedArray([]))).toBe(0);
  });
});

describe("rendimiento (A.2.3, A.8.1)", () => {
  it("FpsMeter mide los cuadros del último segundo", () => {
    const meter = new FpsMeter();
    for (let t = 0; t <= 2000; t += 50) meter.tick(t);
    expect(meter.fps).toBeCloseTo(20, 0);
  });

  it("FrameThrottle procesa ~15 de 30 cuadros por segundo", () => {
    const throttle = new FrameThrottle(15);
    let processed = 0;
    for (let i = 0; i < 30; i += 1) if (throttle.shouldProcess(i * (1000 / 30))) processed += 1;
    expect(processed).toBe(15);
  });
});

describe("meta.json del modelo de gestos (H5)", () => {
  it("acepta holistic-v2 válido y lee faceFeatures y prototipos", () => {
    const meta = parseSequenceMeta(rawMeta({ faceFeatures: false, prototypes: { hola: { handFace: 1, handY: 0, browUp: 0 } } }));
    expect(meta?.labels).toEqual([NONE, "hola", "adios"]);
    expect(meta?.faceFeatures).toBe(false);
    expect(meta?.prototypes.hola).toEqual({ handFace: 1, handY: 0, browUp: 0 });
    expect(parseSequenceMeta(rawMeta())?.faceFeatures).toBe(true);
  });

  it("rechaza otra versión, otro tamaño, media incompleta o etiquetas distintas de labels.json", () => {
    expect(parseSequenceMeta(rawMeta({ featureVersion: "hand-v1" }))).toBeNull();
    expect(parseSequenceMeta(rawMeta({ featureSize: 158 }))).toBeNull();
    expect(parseSequenceMeta(rawMeta({ frames: 20 }))).toBeNull();
    expect(parseSequenceMeta(rawMeta({ mean: [0] }))).toBeNull();
    expect(parseSequenceMeta(rawMeta({ labels: ["hola", "hola"] }))).toBeNull();
    expect(parseSequenceMeta(rawMeta(), [NONE, "hola"])).toBeNull();
  });

  it("prepareSequence normaliza cada cuadro y, sin faceFeatures, pone los blendshapes en 0", () => {
    const meta = parseSequenceMeta(rawMeta({ mean: ones(), std: Array.from({ length: 159 }, () => 2) })) as SequenceMeta;
    const frame = new Float32Array(HOLISTIC_V2_SIZE).fill(3);
    const flat = prepareSequence(Array.from({ length: SEQUENCE_FRAMES }, () => frame), meta);
    expect(flat).toHaveLength(SEQUENCE_FRAMES * HOLISTIC_V2_SIZE);
    expect(flat.every((v) => v === 1)).toBe(true);
    const masked = prepareSequence([frame], { ...meta, faceFeatures: false });
    expect(masked[LAYOUT.blendshapes]).toBeCloseTo(-0.5);
    expect(masked[0]).toBe(1);
    // Sin rostro: mano–cara, blendshapes y presencia de cara en 0; las manos no cambian.
    const faceless = maskFace(frame);
    expect(Array.from(faceless.subarray(LAYOUT.handFace))).toEqual(Array.from({ length: 6 + BLENDSHAPES.length + 1 }, () => 0));
    expect(faceless[LAYOUT.handFace - 1]).toBe(3);
  });

  it("bajo el umbral la respuesta es NINGUNA", () => {
    expect(decide({ label: "hola", confidence: 0.69 }, 0.7)).toEqual({ label: NONE, confidence: 0.69 });
    expect(decide({ label: "hola", confidence: 0.7 }, 0.7)).toEqual({ label: "hola", confidence: 0.7 });
  });
});

describe("retroalimentación de Tomi (A.10)", () => {
  const sample = (handFace: number, browUp = 0, present = true) => {
    const f = new Float32Array(HOLISTIC_V2_SIZE);
    f[LAYOUT.dominant + PRESENCE_OFFSET] = present ? 1 : 0;
    f[LAYOUT.handFace] = handFace;
    f[LAYOUT.blendshapes + BLENDSHAPES.indexOf("browInnerUp")] = browUp;
    return [f, f];
  };
  const target = { handFace: 0.5, handY: 0, browUp: 0.6 };

  it("altura de la mano respecto al promedio de la seña", () => {
    const at = (y: number) => {
      const f = new Float32Array(HOLISTIC_V2_SIZE);
      f[LAYOUT.dominant + PRESENCE_OFFSET] = 1;
      f[LAYOUT.dominant + PRESENCE_OFFSET - 2] = y;
      return [f];
    };
    expect(tomiFeedback(at(1), { handFace: 0, handY: 0, browUp: 0 }, false)).toBe("Sube un poco la mano.");
    expect(tomiFeedback(at(-1), { handFace: 0, handY: 0, browUp: 0 }, false)).toBe("Baja un poco la mano.");
  });

  it("sin mano, lejos de la cara o sin cejas levantadas", () => {
    expect(tomiFeedback(sample(1, 0, false), target, true)).toMatch(/No vi tu mano/);
    expect(tomiFeedback(sample(2), target, true)).toMatch(/acerca la mano a la cara/);
    expect(tomiFeedback(sample(0.5, 0.1), target, true)).toMatch(/Levanta las cejas/);
    // Sin rostro en el modelo no se habla de la cara ni de las cejas (sus promedios valen 0).
    expect(tomiFeedback(sample(0.5, 0.1), target, false)).toMatch(/Casi/);
    expect(tomiFeedback(sample(2), { handFace: 0, handY: 0, browUp: 0 }, false)).toMatch(/Casi/);
  });
});

describe("dataset holistic-v2 (A.6)", () => {
  const frames = Array.from({ length: SEQUENCE_FRAMES }, () => new Float32Array(HOLISTIC_V2_SIZE).fill(0.1234567));
  const base = {
    label: "hola",
    collector: " persona-03 ",
    dominantHand: "right" as const,
    source: "propio",
    license: "propio-con-autorizacion",
    quality: { faceRatio: 1, domHandRatio: 1, poseRatio: 1 },
    frames,
    id: "id-1",
  };

  it("muestra con 30×159 números (5 decimales), alias y licencia; cabecera A.6", () => {
    const sample = makeSample(base);
    expect(sample.collector).toBe("persona-03");
    expect(sample.data).toHaveLength(30);
    expect(sample.data[0]).toHaveLength(159);
    expect(sample.data[0][0]).toBe(0.12346);
    const dataset = buildHolisticDataset([sample], true, "abc123");
    expect(dataset).toMatchObject({
      format: "alas-dataset",
      featureVersion: "holistic-v2",
      featureSize: 159,
      frames: 30,
      durationSec: 2,
      faceFeatures: true,
      createdWith: { tasksVision: "1.1.0", app: "abc123" },
    });
  });

  it("rechaza tamaños incorrectos, fuente o licencia vacías y alias vacío", () => {
    // Origen del archivo (D-044): se conserva para poder filtrar después; es opcional.
    expect(makeSample(base).origin).toBeUndefined();
    const withOrigin = makeSample({ ...base, origin: { file: "Ayudar__lsc54-s2-01__1.mp4", sourceLabel: "Ayudar" } });
    expect(withOrigin.origin).toEqual({ file: "Ayudar__lsc54-s2-01__1.mp4", sourceLabel: "Ayudar" });
    expect(() => makeSample({ ...base, frames: frames.slice(1) })).toThrow();
    expect(() => makeSample({ ...base, license: " " })).toThrow(/licencia/);
    expect(() => makeSample({ ...base, collector: "" })).toThrow(/alias/);
  });
});
