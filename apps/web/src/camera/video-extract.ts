// Muestras desde archivos de video (D-019): el MISMO pipeline del navegador (HandLandmarker +
// normalizeLandmarks, D11) aplicado a videos locales, p. ej. los de LSC-54. Los videos no se suben.
import type { HandLandmarker } from "@mediapipe/tasks-vision";
import type { Sample } from "./dataset";
import { normalizeLandmarks, pickSigningHand } from "./normalize";

const WASM_DIR = "/mediapipe/wasm";
const HAND_MODEL = "/mediapipe/hand_landmarker.task";
export const SAMPLE_STEP_S = 0.1; // ~10 muestras por segundo, como el colector con cámara
/** Parte central de cada clip: al inicio la mano sube y al final baja (cuadros de transición). */
export const HOLD_START = 0.25;
export const HOLD_END = 0.85;

/** Instantes (s) a muestrear: solo la parte central; «NINGUNA» usa el clip completo. */
export function sampleTimes(duration: number, label: string): number[] {
  const [from, to] = label === "NINGUNA" ? [0, duration] : [duration * HOLD_START, duration * HOLD_END];
  const times: number[] = [];
  for (let t = from + SAMPLE_STEP_S / 2; t < to; t += SAMPLE_STEP_S) times.push(t);
  return times;
}

const NAME = /^([a-z0-9-]+|NINGUNA)__([A-Za-z0-9-]+)__[A-Za-z0-9-]+\.([a-z0-9]+)$/i;
const VIDEO_EXT = new Set(["mp4", "webm", "mov", "m4v"]);
const IMAGE_EXT = new Set(["jpg", "jpeg", "png", "webp"]);

function parseName(name: string, allowed: Set<string>): { label: string; collector: string } | null {
  const match = NAME.exec(name);
  if (!match || !allowed.has(match[3].toLowerCase()) || match[1] !== match[1].toLowerCase() && match[1] !== "NINGUNA") {
    return null;
  }
  return { label: match[1], collector: match[2] };
}

/** «numero-3__p17__t0.mp4» → etiqueta y persona; null si el nombre no sigue el formato. */
export function parseVideoName(name: string): { label: string; collector: string } | null {
  return parseName(name, VIDEO_EXT);
}

/** «letra-a__p12__foto3.jpg» → etiqueta y persona (fotos de letras estáticas, p. ej. LSC70). */
export function parseImageName(name: string): { label: string; collector: string } | null {
  return parseName(name, IMAGE_EXT);
}

export function isImageFile(name: string): boolean {
  return IMAGE_EXT.has(name.split(".").pop()?.toLowerCase() ?? "");
}

async function createLandmarker(runningMode: "VIDEO" | "IMAGE" = "VIDEO"): Promise<HandLandmarker> {
  const { FilesetResolver, HandLandmarker } = await import("@mediapipe/tasks-vision");
  const fileset = await FilesetResolver.forVisionTasks(WASM_DIR);
  // CPU: funciona igual en equipos sin GPU y en navegadores automatizados.
  return HandLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: HAND_MODEL, delegate: "CPU" },
    runningMode,
    numHands: 2, // se elige la mano que hace la seña (pickSigningHand, D-020)
  });
}

/** Una muestra por foto (letras estáticas): mismo HandLandmarker y normalización (D11). */
export async function extractFromImages(
  files: readonly File[],
  onProgress: (progress: ExtractProgress) => void,
): Promise<{ samples: Sample[]; skipped: string[] }> {
  const landmarker = await createLandmarker("IMAGE");
  const samples: Sample[] = [];
  const skipped: string[] = [];
  try {
    for (const [index, file] of files.entries()) {
      const meta = parseImageName(file.name);
      if (!meta) {
        skipped.push(file.name);
        continue;
      }
      try {
        const bitmap = await createImageBitmap(file);
        const result = landmarker.detect(bitmap);
        bitmap.close();
        const hand = pickSigningHand(result.landmarks, result.handedness);
        const features = hand ? normalizeLandmarks(hand.points, hand.side) : null;
        if (features) samples.push({ label: meta.label, features, collector: meta.collector });
        else skipped.push(file.name);
      } catch {
        skipped.push(file.name);
      }
      if ((index + 1) % 25 === 0 || index + 1 === files.length) {
        onProgress({ file: file.name, index: index + 1, total: files.length, samples: samples.length });
      }
    }
  } finally {
    landmarker.close();
  }
  return { samples, skipped };
}

function waitFor(video: HTMLVideoElement, event: "loadeddata" | "seeked"): Promise<void> {
  return new Promise((resolve, reject) => {
    const done = () => {
      video.removeEventListener(event, done);
      video.removeEventListener("error", fail);
      resolve();
    };
    const fail = () => {
      video.removeEventListener(event, done);
      video.removeEventListener("error", fail);
      reject(new Error("El navegador no pudo leer este video (usa MP4 con H.264)."));
    };
    video.addEventListener(event, done);
    video.addEventListener("error", fail);
  });
}

export interface ExtractProgress {
  file: string;
  index: number;
  total: number;
  samples: number;
}

/** Recorre cada video cada 0,1 s y devuelve las muestras normalizadas (una por cuadro con mano). */
export async function extractFromVideos(
  files: readonly File[],
  onProgress: (progress: ExtractProgress) => void,
): Promise<{ samples: Sample[]; skipped: string[] }> {
  const landmarker = await createLandmarker();
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  const samples: Sample[] = [];
  const skipped: string[] = [];
  let timestamp = 0; // estrictamente creciente entre todos los videos (§10.4)
  try {
    for (const [index, file] of files.entries()) {
      const meta = parseVideoName(file.name);
      if (!meta) {
        skipped.push(file.name);
        continue;
      }
      const url = URL.createObjectURL(file);
      try {
        video.src = url;
        await waitFor(video, "loadeddata");
        for (const t of sampleTimes(video.duration, meta.label)) {
          video.currentTime = t;
          await waitFor(video, "seeked");
          timestamp += SAMPLE_STEP_S * 1000;
          const result = landmarker.detectForVideo(video, timestamp);
          const hand = pickSigningHand(result.landmarks, result.handedness);
          if (!hand) continue;
          const features = normalizeLandmarks(hand.points, hand.side);
          if (features) samples.push({ label: meta.label, features, collector: meta.collector });
        }
      } catch {
        skipped.push(file.name);
      } finally {
        URL.revokeObjectURL(url);
      }
      onProgress({ file: file.name, index: index + 1, total: files.length, samples: samples.length });
    }
  } finally {
    landmarker.close();
    video.removeAttribute("src");
  }
  return { samples, skipped };
}
