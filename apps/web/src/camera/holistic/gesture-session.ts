// Sesión de cámara holística (anexo A.2.3, A.4, A.5): procesa ~15 cuadros por segundo, calcula la guía
// cada 0,5 s y graba ventanas de 2 s. El video nunca sale del navegador ni se graba (A.9).
import { MonotonicTimestamps } from "../classifier";
import { CAMERA_ERRORS } from "../session";
import type { Overlay } from "../recognizer";
import { captureCheck, FIXED_CAPTURE, type CaptureEnd, type CaptureLimits } from "./capture";
import { HolisticExtractorV2, type Delegate } from "./extractor";
import type { DominantHand } from "./frame";
import { FpsMeter, FrameThrottle, GUIDE_INTERVAL_MS, guidanceMessages, guideInputOf, meanLuminance, readyToRecord } from "./guide";
import {
  chooseSigningHand,
  FrameSequencer,
  type QualityCheck,
  type QualityOptions,
  type SequenceQuality,
} from "./sequencer";

export interface GestureFrame {
  overlay: Overlay | null;
  guidance: string[];
  ready: boolean;
  fps: number;
  /** ms que tarda MediaPipe en este cuadro (modo ADMIN, A.8.1). */
  extractMs: number;
}

export interface RecordedSample {
  frames: Float32Array[];
  quality: SequenceQuality;
  check: QualityCheck;
  /** true si se usó la otra mano (D-028). */
  switchedHand: boolean;
}

/** Una grabación en curso: se cierra sola al llegar al máximo, o antes con `end` (D-045). */
export interface CaptureHandle {
  readonly result: Promise<RecordedSample>;
  /** «Terminar»: la persona acabó la seña. */
  end(): void;
  /** «Cancelar»: la muestra se descarta. */
  cancel(): void;
}

export interface GestureSession {
  readonly delegate: Delegate;
  /** Graba 2 s y devuelve los 30 cuadros (recortados al tramo con mano) con su control de calidad. */
  record(options?: QualityOptions): Promise<RecordedSample>;
  /** Graba hasta `limits.maxMs` o hasta `end()`; el resultado es la misma secuencia de 30 cuadros. */
  capture(options?: QualityOptions, limits?: CaptureLimits): CaptureHandle;
  stop(): void;
}

/** Luminancia de un cuadro reducido a 32×24 (barato: se calcula cada 0,5 s). */
function luminanceOf(video: HTMLVideoElement, canvas: HTMLCanvasElement): number | null {
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return meanLuminance(context.getImageData(0, 0, canvas.width, canvas.height).data);
}

export async function startGestureSession(
  video: HTMLVideoElement,
  {
    dominantHand,
    onFrame,
    requireFace = true,
    requireHand = () => true,
    isCancelled = () => false,
  }: {
    dominantHand: DominantHand;
    onFrame: (frame: GestureFrame) => void;
    requireFace?: boolean;
    /** false para «NINGUNA»: se puede grabar con las manos abajo. Se consulta en cada cuadro. */
    requireHand?: () => boolean;
    /** true si quien pidió la cámara ya no la quiere (salió de la página mientras cargaba). */
    isCancelled?: () => boolean;
  },
): Promise<GestureSession> {
  if (!window.isSecureContext) throw new DOMException(CAMERA_ERRORS.insecure, "InsecureContextError");
  const cancelled = () => new DOMException("Se canceló al salir.", "AbortError");
  // Primero el detector (WASM y modelo tardan segundos) y después la cámara: si la persona sale
  // mientras carga, la cámara nunca llega a encenderse (R8.5).
  const extractor = await HolisticExtractorV2.create(dominantHand);
  if (isCancelled()) {
    extractor.close();
    throw cancelled();
  }
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, frameRate: { ideal: 30 }, facingMode: "user" },
      audio: false,
    });
  } catch (error) {
    extractor.close();
    throw error;
  }
  const stopTracks = () => stream.getTracks().forEach((track) => track.stop());
  try {
    if (isCancelled()) throw cancelled();
    video.srcObject = stream;
    await video.play();
    if (isCancelled()) throw cancelled();
  } catch (error) {
    stopTracks();
    video.srcObject = null;
    extractor.close();
    throw error;
  }

  let stopped = false;
  let raf = 0;
  const timestamps = new MonotonicTimestamps();
  const throttle = new FrameThrottle();
  const fps = new FpsMeter();
  const small = document.createElement("canvas");
  small.width = 32;
  small.height = 24;
  let lastGuide = -Infinity;
  let guidance: string[] = [];
  let ready = false;
  let recording: {
    token: object;
    sequencer: FrameSequencer;
    alternate: FrameSequencer;
    startedAt: number;
    options: QualityOptions;
    limits: CaptureLimits;
    resolve: (sample: RecordedSample) => void;
  } | null = null;

  const finish = (end: CaptureEnd) => {
    if (!recording) return;
    const { sequencer, alternate, options, limits, resolve, startedAt } = recording;
    recording = null;
    const chosen = chooseSigningHand(sequencer, alternate, options);
    // Interrumpida, cancelada o demasiado corta: una captura incompleta nunca se clasifica.
    const complete = captureCheck(performance.now() - startedAt, end, limits);
    resolve(complete.ok ? chosen : { ...chosen, check: complete });
  };

  const capture = (options: QualityOptions = {}, limits: CaptureLimits = FIXED_CAPTURE): CaptureHandle => {
    finish("interrupted"); // nunca dos grabaciones a la vez
    const token = {};
    const result = new Promise<RecordedSample>((resolve) => {
      recording = {
        token,
        sequencer: new FrameSequencer(),
        alternate: new FrameSequencer(),
        startedAt: performance.now(),
        options,
        limits,
        resolve,
      };
    });
    // Solo cierra la grabación que abrió este handle (no una posterior).
    const close = (end: CaptureEnd) => {
      if (recording?.token === token) finish(end);
    };
    return { result, end: () => close("user"), cancel: () => close("cancelled") };
  };

  const tick = () => {
    if (stopped || document.hidden) return;
    const now = performance.now();
    raf = requestAnimationFrame(tick);
    if (video.readyState < 2 || !throttle.shouldProcess(now)) return;
    const timestamp = timestamps.next(now);
    if (timestamp === null) return;
    const extracted = extractor.extract(video, timestamp);
    const extractMs = performance.now() - now;
    fps.tick(now);
    if (recording) {
      const features = extracted?.features;
      recording.sequencer.push(features instanceof Float32Array ? features : null, timestamp);
      recording.alternate.push(extracted?.alternate ?? null, timestamp);
      if (timestamp - recording.startedAt >= recording.limits.maxMs) finish("limit");
    }
    if (now - lastGuide >= GUIDE_INTERVAL_MS) {
      lastGuide = now;
      const input = guideInputOf(extracted?.overlay ?? null, luminanceOf(video, small));
      guidance = guidanceMessages(input, requireFace);
      ready = readyToRecord(input, requireFace, requireHand());
    }
    onFrame({ overlay: extracted?.overlay ?? null, guidance, ready, fps: fps.fps, extractMs });
  };

  const onVisibility = () => {
    cancelAnimationFrame(raf);
    if (document.hidden) finish("interrupted"); // pestaña oculta: la muestra se cierra (y el control de calidad decide)
    else if (!stopped) raf = requestAnimationFrame(tick);
  };
  document.addEventListener("visibilitychange", onVisibility);
  raf = requestAnimationFrame(tick);

  return {
    get delegate() {
      return extractor.delegate;
    },
    record(options: QualityOptions = {}) {
      return capture(options, FIXED_CAPTURE).result;
    },
    capture,
    stop() {
      if (stopped) return;
      stopped = true;
      finish("interrupted");
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVisibility);
      stopTracks(); // R8.5: la cámara se apaga al salir
      video.srcObject = null;
      extractor.close();
    },
  };
}
