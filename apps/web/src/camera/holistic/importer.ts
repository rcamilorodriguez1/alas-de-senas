// Importador `/admin/importar` (anexo A.7.1): videos o secuencias de imágenes de datasets externos →
// mismo pipeline del navegador (HolisticLandmarker + buildHolisticFrame + FrameSequencer, regla 1 de A.7).
// Los archivos no se suben: se procesan aquí y solo salen números.
import { NONE } from "../classifier";
import type { ExtractedFrame } from "../recognizer";
import { HolisticExtractorV2 } from "./extractor";
import { maskFace, type DominantHand } from "./frame";
import { makeSample, type HolisticSample } from "./dataset-v2";
import { chooseSigningHand, FrameSequencer } from "./sequencer";

/** Paso entre cuadros al recorrer un video (~15 por segundo, como la cámara, A.2.3). */
export const IMPORT_STEP_S = 1 / 15;

export interface MappingRow {
  source: string;
  sourceLabel: string;
  slug: string;
}

/** «Buenos días» → «buenos-dias» (para comparar con el nombre de archivo). */
export function slugify(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** `content/dataset-mapping.csv` (`fuente,etiqueta_fuente,slug`); sin comillas ni comas internas. */
export function parseMapping(csv: string): MappingRow[] {
  const [header, ...lines] = csv.split(/\r?\n/).filter((line) => line.trim() && !line.startsWith("#"));
  if (header?.trim() !== "fuente,etiqueta_fuente,slug") return [];
  return lines.map((line) => {
    const [source = "", sourceLabel = "", slug = ""] = line.split(",").map((cell) => cell.trim());
    return { source, sourceLabel, slug };
  });
}

/** Etiqueta del nombre de archivo → slug del currículo (o null: la seña no está y se ignora, A.7 regla 3). */
export function resolveLabel(fileLabel: string, source: string, mapping: readonly MappingRow[]): string | null {
  const key = slugify(fileLabel);
  const row = mapping.find((r) => r.source === source && slugify(r.sourceLabel) === key);
  if (row) return row.slug;
  if (fileLabel === NONE) return NONE;
  const direct = mapping.find((r) => r.source === source && r.slug === fileLabel);
  return direct ? direct.slug : null;
}

const NAME = /^(.+?)__([A-Za-z0-9-]+)__([A-Za-z0-9-]+?)(?:-(\d+))?\.([a-z0-9]+)$/i;
const VIDEO_EXT = new Set(["mp4", "webm", "mov", "m4v"]);
const IMAGE_EXT = new Set(["jpg", "jpeg", "png", "webp"]);

export interface ImportItem {
  key: string;
  label: string;
  collector: string;
  kind: "video" | "images";
  files: File[];
}

/**
 * Agrupa archivos `etiqueta__persona__toma.mp4` (un video = una muestra) y
 * `etiqueta__persona__toma-0001.jpg` (imágenes ordenadas por nombre = una muestra).
 */
export function groupFiles(files: readonly File[]): { items: ImportItem[]; ignored: string[] } {
  const items = new Map<string, ImportItem>();
  const ignored: string[] = [];
  for (const file of [...files].sort((a, b) => a.name.localeCompare(b.name))) {
    const match = NAME.exec(file.name);
    const ext = match?.[5].toLowerCase() ?? "";
    if (!match || (!VIDEO_EXT.has(ext) && !IMAGE_EXT.has(ext))) {
      ignored.push(file.name);
      continue;
    }
    const kind = VIDEO_EXT.has(ext) ? "video" : "images";
    const key = `${match[1]}__${match[2]}__${match[3]}${kind === "video" ? `.${ext}` : ""}`;
    const item = items.get(key) ?? { key, label: match[1], collector: match[2], kind, files: [] };
    item.files.push(file);
    items.set(key, item);
  }
  return { items: [...items.values()], ignored };
}

export interface ImportOptions {
  source: string;
  license: string;
  faceFeatures: boolean;
  dominantHand: DominantHand;
  mapping: readonly MappingRow[];
}

export interface ImportOutcome {
  item: string;
  sample: HolisticSample | null;
  reason: string | null;
}

function asFrame(extracted: ExtractedFrame | null): Float32Array | null {
  return extracted?.features instanceof Float32Array ? extracted.features : null;
}

/** Espera máxima de un evento del video: a veces «seeked» nunca llega y el lote quedaba congelado. */
export const VIDEO_EVENT_TIMEOUT_MS = 10_000;

export function waitFor(
  video: HTMLVideoElement,
  event: "loadeddata" | "seeked",
  timeoutMs = VIDEO_EVENT_TIMEOUT_MS,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      window.clearTimeout(timer);
      video.removeEventListener(event, done);
      video.removeEventListener("error", fail);
    };
    const done = () => {
      cleanup();
      resolve();
    };
    const fail = () => {
      cleanup();
      reject(new Error("El navegador no pudo leer este video (usa MP4 con H.264)."));
    };
    const timer = window.setTimeout(() => {
      cleanup();
      reject(new Error("El video no respondió a tiempo (se omite)."));
    }, timeoutMs);
    video.addEventListener(event, done);
    video.addEventListener("error", fail);
  });
}

/**
 * Procesa los grupos uno a uno (se puede pausar con `shouldStop`). Los videos se recorren cuadro a
 * cuadro buscando cada instante (`currentTime`) en vez de reproducirlos: es determinista y no depende
 * del ritmo del equipo; el instante del video es el timestamp (D-025).
 */
export async function importItems(
  items: readonly ImportItem[],
  options: ImportOptions,
  onOutcome: (outcome: ImportOutcome, index: number) => void,
  shouldStop: () => boolean = () => false,
): Promise<void> {
  // CPU: igual en todos los equipos y en navegadores automatizados (D-019).
  const videoExtractor = await HolisticExtractorV2.create(options.dominantHand, { delegates: ["CPU"] });
  const imageExtractor = items.some((i) => i.kind === "images")
    ? await HolisticExtractorV2.create(options.dominantHand, { runningMode: "IMAGE", delegates: ["CPU"] })
    : null;
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  let clock = 0; // ms, estrictamente creciente entre todos los videos (MediaPipe lo exige)
  try {
    for (const [index, item] of items.entries()) {
      if (shouldStop()) break;
      const label = resolveLabel(item.label, options.source, options.mapping);
      if (!label) {
        onOutcome({ item: item.key, sample: null, reason: `«${item.label}» no está en el mapeo de ${options.source}.` }, index);
        continue;
      }
      const sequencer = new FrameSequencer(0);
      const alternate = new FrameSequencer(0); // la otra mano: en un dataset no se sabe quién es zurdo (D-028)
      try {
        if (item.kind === "video") {
          const url = URL.createObjectURL(item.files[0]);
          try {
            video.src = url;
            await waitFor(video, "loadeddata");
            // WebM de MediaRecorder: duración Infinity; sin duración el recorrido no terminaría.
            if (!Number.isFinite(video.duration) || video.duration <= 0) {
              throw new Error("El video no informa su duración (conviértelo a MP4).");
            }
            const start = clock;
            for (let t = 0; t < video.duration; t += IMPORT_STEP_S) {
              if (shouldStop()) throw new Error("Pausado.");
              video.currentTime = t;
              await waitFor(video, "seeked");
              clock = start + t * 1000;
              const extracted = videoExtractor.extract(video, clock);
              sequencer.push(asFrame(extracted), clock);
              alternate.push(extracted?.alternate ?? null, clock);
            }
          } finally {
            URL.revokeObjectURL(url);
            clock += 1000; // también si el video falla a mitad: el siguiente nunca repite un timestamp
          }
        } else if (imageExtractor) {
          for (const [n, file] of item.files.entries()) {
            const bitmap = await createImageBitmap(file);
            const extracted = imageExtractor.extractImage(bitmap);
            bitmap.close();
            sequencer.push(asFrame(extracted), n * IMPORT_STEP_S * 1000);
            alternate.push(extracted?.alternate ?? null, n * IMPORT_STEP_S * 1000);
          }
        }
      } catch (error) {
        if (shouldStop()) break; // pausa a mitad de un video: queda pendiente para «Continuar»
        onOutcome({ item: item.key, sample: null, reason: error instanceof Error ? error.message : "Error al leer." }, index);
        continue;
      }
      const chosen = chooseSigningHand(sequencer, alternate, {
        faceRequired: options.faceFeatures,
        handRequired: label !== NONE,
      });
      if (!chosen.check.ok) {
        onOutcome({ item: item.key, sample: null, reason: chosen.check.reason }, index);
        continue;
      }
      const other = options.dominantHand === "left" ? "right" : "left";
      const sample = makeSample({
        label,
        collector: item.collector,
        dominantHand: chosen.switchedHand ? other : options.dominantHand,
        source: options.source,
        license: options.license,
        quality: chosen.quality,
        // Sin rostro (caras pixeladas): no se exporta lo que depende de la cara (minimización, H9).
        frames: options.faceFeatures ? chosen.frames : chosen.frames.map(maskFace),
      });
      onOutcome({ item: item.key, sample, reason: null }, index);
    }
  } finally {
    videoExtractor.close();
    imageExtractor?.close();
    video.removeAttribute("src");
  }
}
