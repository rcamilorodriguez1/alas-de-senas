// Muestras desde archivos de video (D-019): el MISMO pipeline del navegador (HandLandmarker +
// normalizeLandmarks, D11) aplicado a videos locales, p. ej. los de LSC-54. Los videos no se suben.
import type { HandLandmarker } from "@mediapipe/tasks-vision";
import type { Sample } from "./dataset";
import { normalizeLandmarks, type Handedness } from "./normalize";

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

/** «numero-3__p17__t0.mp4» → etiqueta y persona; null si el nombre no sigue el formato. */
export function parseVideoName(name: string): { label: string; collector: string } | null {
  const match = /^([a-z0-9-]+|NINGUNA)__([A-Za-z0-9-]+)__[A-Za-z0-9-]+\.(mp4|webm|mov|m4v)$/.exec(name);
  return match ? { label: match[1], collector: match[2] } : null;
}

async function createLandmarker(): Promise<HandLandmarker> {
  const { FilesetResolver, HandLandmarker } = await import("@mediapipe/tasks-vision");
  const fileset = await FilesetResolver.forVisionTasks(WASM_DIR);
  // CPU: funciona igual en equipos sin GPU y en navegadores automatizados.
  return HandLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: HAND_MODEL, delegate: "CPU" },
    runningMode: "VIDEO",
    numHands: 1,
  });
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
          const points = result.landmarks[0];
          if (!points) continue;
          const side = result.handedness[0]?.[0]?.categoryName === "Left" ? "Left" : "Right";
          const features = normalizeLandmarks(points, side as Handedness);
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
