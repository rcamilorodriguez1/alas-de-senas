// Guía visual de captura (anexo A.5) y rendimiento (A.8.1): funciones puras, la UI solo las muestra.
import type { Overlay, Point2 } from "../recognizer";

/** Luminancia media (0–1) por debajo de la cual se avisa «Hay poca luz». */
export const LOW_LIGHT = 0.22;
const EDGE = 0.02; // margen del cuadro: una mano en el borde «sale del cuadro»
export const GUIDE_INTERVAL_MS = 500;
export const TARGET_FPS = 15; // A.2.3: procesar ~15 cuadros por segundo

export interface GuideInput {
  face: boolean;
  shoulders: boolean;
  hands: number;
  handsOutOfFrame: boolean;
  luminance: number | null;
}

export function guideInputOf(overlay: Overlay | null, luminance: number | null): GuideInput {
  const hands = [overlay?.dominant, overlay?.other].filter((h): h is readonly Point2[] => Boolean(h?.length));
  return {
    face: Boolean(overlay?.face.length),
    shoulders: (overlay?.shoulders.length ?? 0) >= 2,
    hands: hands.length,
    handsOutOfFrame: hands.some((hand) => hand.some((p) => p.x < EDGE || p.x > 1 - EDGE || p.y < EDGE || p.y > 1 - EDGE)),
    luminance,
  };
}

/** Mensajes en vivo, en orden de importancia. Vacío = todo bien. `requireFace` false si el modelo no usa la cara. */
export function guidanceMessages(input: GuideInput, requireFace = true): string[] {
  const messages: string[] = [];
  if (input.luminance !== null && input.luminance < LOW_LIGHT) messages.push("Hay poca luz");
  if (requireFace && !input.face) messages.push("No veo tu cara");
  if (!input.shoulders) messages.push("No veo tus hombros, aléjate un poco");
  if (input.handsOutOfFrame) messages.push("Tus manos salen del cuadro");
  return messages;
}

/**
 * «Grabar» solo con cara, hombros y al menos una mano visibles (A.5); sin cara si el modelo no la usa
 * y sin mano para «NINGUNA» (las manos pueden estar abajo, D-025).
 */
export function readyToRecord(input: GuideInput, requireFace = true, requireHand = true): boolean {
  return (input.face || !requireFace) && input.shoulders && (input.hands >= 1 || !requireHand);
}

/** Luminancia media de un cuadro RGBA pequeño (Rec. 601), entre 0 y 1. */
export function meanLuminance(rgba: Uint8ClampedArray): number {
  const pixels = Math.floor(rgba.length / 4);
  if (pixels === 0) return 0;
  let sum = 0;
  for (let i = 0; i < pixels * 4; i += 4) sum += 0.299 * rgba[i] + 0.587 * rgba[i + 1] + 0.114 * rgba[i + 2];
  return sum / pixels / 255;
}

/** Cuadros por segundo del último segundo. */
export class FpsMeter {
  private readonly stamps: number[] = [];

  tick(now: number): void {
    this.stamps.push(now);
    while (this.stamps.length && now - this.stamps[0] > 1000) this.stamps.shift();
  }

  get fps(): number {
    if (this.stamps.length < 2) return 0;
    const span = this.stamps[this.stamps.length - 1] - this.stamps[0];
    return span > 0 ? ((this.stamps.length - 1) * 1000) / span : 0;
  }
}

/** Salta cuadros si la cámara entrega más de `fps` por segundo (A.2.3). */
export class FrameThrottle {
  private last = -Infinity;
  constructor(private readonly fps = TARGET_FPS) {}

  shouldProcess(now: number): boolean {
    // Margen de 10 %: con una cámara a 30 fps se procesa uno de cada dos cuadros, no uno de cada tres.
    if (now - this.last < (1000 / this.fps) * 0.9) return false;
    this.last = now;
    return true;
  }
}
