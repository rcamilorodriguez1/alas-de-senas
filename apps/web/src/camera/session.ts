// Sesión de cámara (§10.2, §10.4): getUserMedia → HandLandmarker → normalizeLandmarks → clasificador.
// Nada de la imagen sale del navegador (R8.3): solo se usan los 21 puntos de la mano.
import type { HandLandmarker, NormalizedLandmark } from "@mediapipe/tasks-vision";
import { loadClassifier, MonotonicTimestamps, Smoother, type Classifier, type Prediction } from "./classifier";
import { normalizeLandmarks, pickSigningHand } from "./normalize";

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

// ---------- Errores de la cámara (§10.4), cada uno con su mensaje en español ----------

export type CameraErrorKind = "denied" | "not-found" | "busy" | "insecure" | "unknown";

export function cameraErrorKind(error: unknown): CameraErrorKind {
  const name = error instanceof DOMException || error instanceof Error ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "denied";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "not-found";
  if (name === "NotReadableError" || name === "AbortError") return "busy";
  if (name === "InsecureContextError") return "insecure";
  return "unknown";
}

export const CAMERA_ERRORS: Record<CameraErrorKind, string> = {
  denied:
    "Necesitamos permiso para usar la cámara. Actívalo en el candado de la barra de direcciones y vuelve a intentarlo.",
  "not-found": "No encontramos una cámara en este equipo.",
  busy: "La cámara está ocupada por otra aplicación. Ciérrala y vuelve a intentarlo.",
  insecure: "La cámara solo funciona con HTTPS (o en localhost).",
  unknown: "No pudimos encender la cámara. Vuelve a intentarlo.",
};

// ---------- Bucle de reconocimiento ----------

export interface FrameResult {
  points: NormalizedLandmark[] | null;
  /** Los 63 valores de `normalizeLandmarks` (lo único que guarda el colector). */
  features: number[] | null;
  detected: Prediction | null;
}

export interface CameraSession {
  readonly classifier: Classifier;
  stop(): void;
}


/** Enciende la cámara y procesa cuadros hasta `stop()`; se pausa con la pestaña oculta. */
export async function startCameraSession(
  video: HTMLVideoElement,
  onFrame: (result: FrameResult) => void,
): Promise<CameraSession> {
  if (!window.isSecureContext) {
    throw new DOMException(CAMERA_ERRORS.insecure, "InsecureContextError");
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: 640, height: 480, facingMode: "user" },
    audio: false,
  });
  let stopped = false;
  let frame = 0;
  const stopTracks = () => stream.getTracks().forEach((track) => track.stop());
  // Si algo falla, se suelta todo lo adquirido: el contador del singleton no se descuadra y el
  // modelo de tfjs no queda en memoria.
  let model: Classifier | null = null;
  let acquired = false;
  let landmarks: HandLandmarker;
  try {
    video.srcObject = stream;
    await video.play();
    model = await loadClassifier();
    acquired = true;
    landmarks = await acquireHandLandmarker();
  } catch (error) {
    stopTracks();
    video.srcObject = null;
    if (acquired) releaseHandLandmarker();
    model?.dispose();
    throw error;
  }
  const timestamps = new MonotonicTimestamps();
  const smoother = new Smoother();

  const tick = () => {
    if (stopped || document.hidden) return;
    const timestamp = timestamps.next(performance.now());
    if (timestamp !== null && video.readyState >= 2) {
      let result: ReturnType<HandLandmarker["detectForVideo"]>;
      try {
        result = landmarks.detectForVideo(video, timestamp);
      } catch {
        frame = requestAnimationFrame(tick); // un cuadro fallido no detiene el bucle
        return;
      }
      const hand = pickSigningHand(result.landmarks, result.handedness);
      const points = hand ? [...hand.points] : null;
      let detected: Prediction | null = null;
      let features: number[] | null = null;
      if (points) {
        features = normalizeLandmarks(points, hand?.side ?? "Right");
        if (features) detected = smoother.push(model.classify(features));
      } else {
        smoother.reset();
      }
      onFrame({ points, features, detected });
    }
    frame = requestAnimationFrame(tick);
  };

  const onVisibility = () => {
    cancelAnimationFrame(frame);
    if (!document.hidden && !stopped) frame = requestAnimationFrame(tick);
  };
  document.addEventListener("visibilitychange", onVisibility);
  frame = requestAnimationFrame(tick);

  return {
    classifier: model,
    stop() {
      if (stopped) return;
      stopped = true;
      cancelAnimationFrame(frame);
      document.removeEventListener("visibilitychange", onVisibility);
      stopTracks(); // R8.5: la cámara se apaga al salir
      video.srcObject = null;
      model.dispose();
      releaseHandLandmarker();
    },
  };
}

/** «letra-a» → «A», «letra-n-tilde» → «Ñ», «numero-3» → «3»; el resto se muestra tal cual. */
export function displayLabel(label: string): string {
  if (label === "letra-n-tilde") return "Ñ";
  if (label.startsWith("letra-")) return label.slice("letra-".length).toUpperCase();
  if (label.startsWith("numero-")) return label.slice("numero-".length);
  return label;
}
