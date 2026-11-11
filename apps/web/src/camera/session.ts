// Sesión de cámara (§10.2, §10.4): getUserMedia → extractor `hand-v1` → clasificador.
// Nada de la imagen sale del navegador (R8.3): solo se usan los 21 puntos de la mano.
import { loadClassifier, MonotonicTimestamps, Smoother, type Classifier, type Prediction } from "./classifier";
import { createFrameScheduler, FpsMeter, type FrameStats } from "./frame-loop";
import { HandOnlyExtractorV1 } from "./hand-extractor";
import type { Point2 } from "./recognizer";

// El singleton de HandLandmarker vive en hand-extractor.ts (se reexporta por compatibilidad).
export { acquireHandLandmarker, releaseHandLandmarker } from "./hand-extractor";

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
  points: readonly Point2[] | null;
  /** Los 63 valores de `normalizeLandmarks` (lo único que guarda el colector). */
  features: number[] | null;
  detected: Prediction | null;
  /** FPS y milisegundos por cuadro del último segundo (null al empezar, D-038). */
  stats?: FrameStats | null;
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
  const stopTracks = () => stream.getTracks().forEach((track) => track.stop());
  // Si algo falla, se suelta todo lo adquirido: el contador del singleton no se descuadra y el
  // modelo de tfjs no queda en memoria.
  let model: Classifier | null = null;
  let extractor: HandOnlyExtractorV1;
  try {
    video.srcObject = stream;
    await video.play();
    model = await loadClassifier();
    extractor = await HandOnlyExtractorV1.create();
  } catch (error) {
    stopTracks();
    video.srcObject = null;
    model?.dispose();
    throw error;
  }
  const timestamps = new MonotonicTimestamps();
  const smoother = new Smoother();
  const meter = new FpsMeter();
  // Un cuadro de la cámara = un análisis (D-038): antes se analizaba al ritmo de la pantalla.
  const scheduler = createFrameScheduler(video);

  const tick = () => {
    if (stopped || document.hidden) return;
    const startedAt = performance.now();
    const timestamp = timestamps.next(startedAt);
    if (timestamp !== null && video.readyState >= 2) {
      const extracted = extractor.extract(video, timestamp);
      if (!extracted) {
        scheduler.request(tick); // un cuadro fallido no detiene el bucle
        return;
      }
      const points = extracted.overlay.dominant;
      const features = extracted.features ? Array.from(extracted.features) : null;
      let detected: Prediction | null = null;
      if (features) detected = smoother.push(model.classify(features), timestamp);
      else if (!points) smoother.reset();
      const stats = meter.tick(startedAt, performance.now() - startedAt);
      onFrame({ points, features, detected, stats });
    }
    scheduler.request(tick);
  };

  const onVisibility = () => {
    scheduler.cancel();
    meter.reset();
    if (!document.hidden && !stopped) scheduler.request(tick);
  };
  document.addEventListener("visibilitychange", onVisibility);
  scheduler.request(tick);

  return {
    classifier: model,
    stop() {
      if (stopped) return;
      stopped = true;
      scheduler.cancel();
      document.removeEventListener("visibilitychange", onVisibility);
      stopTracks(); // R8.5: la cámara se apaga al salir
      video.srcObject = null;
      model.dispose();
      extractor.close();
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
