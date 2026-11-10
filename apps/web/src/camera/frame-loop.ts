// Bucle por cuadro y medidor de FPS (prueba de optimización D-038).
// `requestVideoFrameCallback` avisa solo cuando la cámara entrega un cuadro nuevo (30 por segundo);
// `requestAnimationFrame` corre al ritmo de la pantalla (60 Hz o más) y hacía que MediaPipe
// analizara la misma imagen dos veces.

export type FrameSource = "video" | "animation";

export interface FrameScheduler {
  readonly source: FrameSource;
  request(callback: (now: number) => void): void;
  cancel(): void;
}

/** Lo único que el planificador necesita del `<video>` (en navegadores sin soporte, no existe). */
export interface VideoFrameSource {
  requestVideoFrameCallback?(callback: (now: number) => void): number;
  cancelVideoFrameCallback?(handle: number): void;
}

export function createFrameScheduler(
  video: VideoFrameSource,
  options: { forceAnimationFrame?: boolean } = {},
): FrameScheduler {
  let handle: number | null = null;
  const requestFrame = video.requestVideoFrameCallback?.bind(video);
  const cancelFrame = video.cancelVideoFrameCallback?.bind(video);
  if (!options.forceAnimationFrame && requestFrame && cancelFrame) {
    return {
      source: "video",
      request(callback) {
        handle = requestFrame((now) => callback(now));
      },
      cancel() {
        if (handle !== null) cancelFrame(handle);
        handle = null;
      },
    };
  }
  return {
    source: "animation",
    request(callback) {
      handle = window.requestAnimationFrame(callback);
    },
    cancel() {
      if (handle !== null) window.cancelAnimationFrame(handle);
      handle = null;
    },
  };
}

export interface FrameStats {
  /** Cuadros procesados en el último segundo. */
  fps: number;
  /** Milisegundos promedio que tarda procesar un cuadro (MediaPipe + clasificador). */
  workMs: number;
}

const WINDOW_MS = 1000;

/** Cuenta los cuadros del último segundo; null hasta tener al menos medio segundo de datos. */
export class FpsMeter {
  private readonly samples: { at: number; workMs: number }[] = [];

  tick(nowMs: number, workMs: number): FrameStats | null {
    this.samples.push({ at: nowMs, workMs });
    while (this.samples.length > 0 && this.samples[0].at < nowMs - WINDOW_MS) this.samples.shift();
    const span = nowMs - this.samples[0].at;
    if (this.samples.length < 2 || span < WINDOW_MS / 2) return null;
    const fps = ((this.samples.length - 1) * 1000) / span;
    const work = this.samples.reduce((sum, sample) => sum + sample.workMs, 0) / this.samples.length;
    return { fps, workMs: work };
  }

  reset(): void {
    this.samples.length = 0;
  }
}
