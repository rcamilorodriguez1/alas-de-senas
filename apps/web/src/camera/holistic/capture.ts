// Captura de señas con movimiento (plan de mejora de la cámara, etapa 6; D-045): la ventana fija de 2 s de
// siempre, o inicio y fin marcados por la persona con duración limitada. Las dos terminan en la misma
// secuencia de 30 cuadros recortada al tramo con mano (`FrameSequencer`), igual que el importador: el
// modelo publicado no cambia.
import { SEQUENCE_DURATION_MS, type QualityCheck } from "./sequencer";

export interface CaptureLimits {
  /** Por debajo de esto, «Terminar» deja la captura incompleta. */
  readonly minMs: number;
  /** Al llegar aquí la grabación se cierra sola. */
  readonly maxMs: number;
}

export const FIXED_CAPTURE: CaptureLimits = { minMs: SEQUENCE_DURATION_MS, maxMs: SEQUENCE_DURATION_MS };
/** Los videos de LSC-54 duran entre 1 y 5 s; una seña completa cabe en 4 s y ninguna dura menos de 0,5 s. */
export const MANUAL_CAPTURE: CaptureLimits = { minMs: 500, maxMs: 4000 };

/** Cómo terminó la grabación. */
export type CaptureEnd = "limit" | "user" | "interrupted" | "cancelled";

export const CAPTURE_MESSAGES = {
  interrupted: "La grabación se interrumpió.",
  tooShort: "La grabación fue muy corta: pulsa «Terminar» cuando acabes la seña.",
  cancelled: "Cancelaste la grabación.",
} as const;

/**
 * ¿La captura está completa? Una incompleta nunca se clasifica: distingue «captura incompleta» de «no
 * reconocida». Si está completa, decide después el control de calidad.
 */
export function captureCheck(elapsedMs: number, end: CaptureEnd, limits: CaptureLimits): QualityCheck {
  switch (end) {
    case "cancelled":
      return { ok: false, reason: CAPTURE_MESSAGES.cancelled };
    case "interrupted":
      return elapsedMs >= limits.maxMs ? { ok: true } : { ok: false, reason: CAPTURE_MESSAGES.interrupted };
    case "user":
      return elapsedMs >= limits.minMs ? { ok: true } : { ok: false, reason: CAPTURE_MESSAGES.tooShort };
    case "limit":
      return { ok: true };
  }
}
