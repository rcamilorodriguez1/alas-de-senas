// Extractor `holistic-v2` (anexo A.2.1): HolisticLandmarker → buildHolisticFrame (159 valores).
// Archivos locales, nunca CDN. GPU primero; si falla al crear (o queda «muda»), CPU.
import type { HolisticLandmarker, HolisticLandmarkerResult } from "@mediapipe/tasks-vision";
import type { ExtractedFrame, FeatureExtractor, Overlay } from "../recognizer";
import { buildHolisticFrame, HOLISTIC_V2_SIZE, missingBlendshapes, type DominantHand, type HolisticInput } from "./frame";

const WASM_DIR = "/mediapipe/wasm";
const HOLISTIC_MODEL = "/mediapipe/holistic_landmarker.task";
const SHOULDERS = [11, 12];
// Contorno simple de la cara (no la malla completa, A.5): óvalo de la malla de 478 puntos.
const FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152,
  148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109];
/**
 * Cuadros seguidos sin pose con GPU antes de pasar a CPU: la GPU puede fallar sin error, o detectar
 * solo las manos (sin hombros el vector no existe). Si la persona no está, pasar a CPU no hace daño.
 */
export const SILENT_GPU_FRAMES = 60;
/** Errores seguidos de la GPU al detectar (se crea bien pero cada cuadro falla) antes de pasar a CPU. */
export const GPU_ERROR_FRAMES = 5;

export type Delegate = "GPU" | "CPU";
export type RunningMode = "VIDEO" | "IMAGE";
type Warn = (message: string) => void;

/** Crea con el primer delegado que funcione (A.2.1): GPU → CPU, registrando el aviso. */
export async function createWithFallback<T>(
  make: (delegate: Delegate) => Promise<T>,
  order: readonly Delegate[] = ["GPU", "CPU"],
  warn: Warn = console.warn,
): Promise<{ instance: T; delegate: Delegate }> {
  let lastError: unknown = new Error("Sin delegados");
  for (const delegate of order) {
    try {
      return { instance: await make(delegate), delegate };
    } catch (error) {
      lastError = error;
      warn(`HolisticLandmarker no pudo crearse con ${delegate}; se intenta el siguiente.`);
    }
  }
  throw lastError;
}

/** Cuenta cuadros vacíos seguidos: con GPU, muchos seguidos indican que el delegado falla en silencio. */
export class SilentGpuGuard {
  private empty = 0;
  private errors = 0;
  constructor(
    private readonly limit = SILENT_GPU_FRAMES,
    private readonly errorLimit = GPU_ERROR_FRAMES,
  ) {}

  /** true cuando hay que recrear el detector en CPU. */
  push(somethingDetected: boolean): boolean {
    this.errors = 0;
    this.empty = somethingDetected ? 0 : this.empty + 1;
    return this.empty >= this.limit;
  }

  /** MediaPipe lanzó un error en este cuadro (p. ej. «UNIMPLEMENTED» del grafo de GPU). */
  pushError(): boolean {
    this.errors += 1;
    return this.errors >= this.errorLimit;
  }
}

async function createHolistic(delegate: Delegate, runningMode: RunningMode): Promise<HolisticLandmarker> {
  const { FilesetResolver, HolisticLandmarker } = await import("@mediapipe/tasks-vision");
  const fileset = await FilesetResolver.forVisionTasks(WASM_DIR);
  return HolisticLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: HOLISTIC_MODEL, delegate },
    runningMode,
    minFaceDetectionConfidence: 0.5,
    minPoseDetectionConfidence: 0.5,
    minHandLandmarksConfidence: 0.5,
    outputFaceBlendshapes: true, // expresión facial: solo se guardan 18 valores (A.9)
    outputPoseSegmentationMasks: false,
  });
}

function overlayOf(result: HolisticInput, dominantHand: DominantHand): Overlay {
  const pose = result.poseLandmarks[0] ?? [];
  const face = result.faceLandmarks[0] ?? [];
  const right = result.rightHandLandmarks[0] ?? null;
  const left = result.leftHandLandmarks[0] ?? null;
  return {
    dominant: dominantHand === "left" ? left : right,
    other: dominantHand === "left" ? right : left,
    shoulders: SHOULDERS.map((i) => pose[i]).filter((p) => p !== undefined),
    face: face.length ? FACE_OVAL.map((i) => face[i]).filter((p) => p !== undefined) : [],
  };
}

export class HolisticExtractorV2 implements FeatureExtractor {
  readonly featureVersion = "holistic-v2";
  readonly featureSize = HOLISTIC_V2_SIZE;
  private guard = new SilentGpuGuard();
  private checkedBlendshapes = false;
  private switching = false;
  private closed = false;

  private constructor(
    private landmarker: HolisticLandmarker,
    private delegateInUse: Delegate,
    private readonly dominantHand: DominantHand,
    private readonly runningMode: RunningMode,
    private readonly warn: Warn,
  ) {}

  static async create(
    dominantHand: DominantHand,
    { runningMode = "VIDEO", delegates = ["GPU", "CPU"], warn = console.warn }: {
      runningMode?: RunningMode;
      delegates?: readonly Delegate[];
      warn?: Warn;
    } = {},
  ): Promise<HolisticExtractorV2> {
    const { instance, delegate } = await createWithFallback((d) => createHolistic(d, runningMode), delegates, warn);
    return new HolisticExtractorV2(instance, delegate, dominantHand, runningMode, warn);
  }

  get delegate(): Delegate {
    return this.delegateInUse;
  }

  private process(result: HolisticLandmarkerResult): ExtractedFrame {
    const blendshapes = result.faceBlendshapes[0]?.categories;
    if (!this.checkedBlendshapes && blendshapes?.length) {
      // Prueba de arranque (H4): si cambian los nombres en otra versión, se avisa en vez de entrenar con ceros.
      this.checkedBlendshapes = true;
      const missing = missingBlendshapes(blendshapes.map((c) => c.categoryName));
      if (missing.length) this.warn(`Faltan blendshapes en esta versión de MediaPipe: ${missing.join(", ")}`);
    }
    if (this.delegateInUse === "GPU" && this.guard.push(result.poseLandmarks.length > 0)) void this.fallBackToCpu();
    const other = this.dominantHand === "left" ? "right" : "left";
    return {
      features: buildHolisticFrame(result, this.dominantHand),
      alternate: buildHolisticFrame(result, other),
      overlay: overlayOf(result, this.dominantHand),
    };
  }

  private async fallBackToCpu(): Promise<void> {
    if (this.switching || this.closed) return;
    this.switching = true;
    this.warn("La GPU no detecta la pose; se cambia HolisticLandmarker a CPU.");
    try {
      const cpu = await createHolistic("CPU", this.runningMode);
      if (this.closed) {
        cpu.close();
        return;
      }
      this.landmarker.close();
      this.landmarker = cpu;
      this.delegateInUse = "CPU";
    } catch {
      // Sin CPU: se queda con la GPU.
      this.guard = new SilentGpuGuard(Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY);
    } finally {
      this.switching = false;
    }
  }

  extract(video: HTMLVideoElement, timestampMs: number): ExtractedFrame | null {
    if (this.switching) return null;
    try {
      return this.process(this.landmarker.detectForVideo(video, timestampMs));
    } catch {
      if (this.delegateInUse === "GPU" && this.guard.pushError()) void this.fallBackToCpu();
      return null;
    }
  }

  /** Modo IMAGE (importador de fotos): sin timestamps. */
  extractImage(image: ImageBitmap | HTMLImageElement): ExtractedFrame | null {
    try {
      return this.process(this.landmarker.detect(image));
    } catch {
      return null;
    }
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.landmarker.close();
  }
}
