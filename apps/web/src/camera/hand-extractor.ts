// Extractor `hand-v1` del alfabeto (§10.2): HandLandmarker → mano que hace la seña → 63 valores.
// Es el mismo comportamiento de antes del Grupo 10B, detrás de la interfaz `FeatureExtractor`.
import type { HandLandmarker } from "@mediapipe/tasks-vision";
import { normalizeLandmarks, pickSigningHand } from "./normalize";
import type { ExtractedFrame, FeatureExtractor } from "./recognizer";

const WASM_DIR = "/mediapipe/wasm";
const HAND_MODEL = "/mediapipe/hand_landmarker.task";

// ---------- Singleton de HandLandmarker (StrictMode monta dos veces: nunca dos instancias) ----------

let landmarker: Promise<HandLandmarker> | null = null;
let users = 0;

async function createLandmarker(): Promise<HandLandmarker> {
  const { FilesetResolver, HandLandmarker } = await import("@mediapipe/tasks-vision");
  const fileset = await FilesetResolver.forVisionTasks(WASM_DIR);
  return HandLandmarker.createFromOptions(fileset, {
    // CPU: la GPU falla sin aviso en equipos sin aceleración (laboratorios, navegadores sin
    // drivers) y una mano a 30 fps cabe de sobra en CPU (D-019).
    baseOptions: { modelAssetPath: HAND_MODEL, delegate: "CPU" },
    runningMode: "VIDEO",
    numHands: 2, // se elige la mano que hace la seña (pickSigningHand, D-020)
  });
}

export function acquireHandLandmarker(): Promise<HandLandmarker> {
  users += 1;
  landmarker ??= createLandmarker().catch((error: unknown) => {
    landmarker = null;
    throw error;
  });
  return landmarker;
}

export function releaseHandLandmarker(): void {
  users = Math.max(0, users - 1);
  if (users > 0 || landmarker === null) return;
  const closing = landmarker;
  landmarker = null;
  void closing.then((instance) => instance.close()).catch(() => undefined);
}

export class HandOnlyExtractorV1 implements FeatureExtractor {
  readonly featureVersion = "hand-v1";
  readonly featureSize = 63;
  private closed = false;

  private constructor(private readonly landmarks: HandLandmarker) {}

  static async create(): Promise<HandOnlyExtractorV1> {
    try {
      return new HandOnlyExtractorV1(await acquireHandLandmarker());
    } catch (error) {
      releaseHandLandmarker(); // si falla, el contador del singleton no queda descuadrado
      throw error;
    }
  }

  /** null si MediaPipe falla en este cuadro (el bucle sigue con el siguiente). */
  extract(video: HTMLVideoElement, timestampMs: number): ExtractedFrame | null {
    let result: ReturnType<HandLandmarker["detectForVideo"]>;
    try {
      result = this.landmarks.detectForVideo(video, timestampMs);
    } catch {
      return null;
    }
    const hand = pickSigningHand(result.landmarks, result.handedness);
    const values = hand ? normalizeLandmarks(hand.points, hand.side) : null;
    return {
      features: values, // number[]: el colector guarda los mismos números que antes
      overlay: { dominant: hand ? [...hand.points] : null, other: null, shoulders: [], face: [] },
    };
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    releaseHandLandmarker();
  }
}
