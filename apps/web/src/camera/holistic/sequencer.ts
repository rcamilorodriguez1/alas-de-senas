// Secuencias de 2 s remuestreadas a 30 cuadros (anexo A.4): la misma seña «dura» igual en cualquier
// equipo, aunque la cámara no entregue un ritmo fijo (H3).
import { HOLISTIC_V2_SIZE, LAYOUT, PRESENCE_OFFSET } from "./frame";

export const SEQUENCE_FRAMES = 30;
export const SEQUENCE_DURATION_MS = 2000;
const MAX_GAP = 3; // huecos de una mano de hasta 3 cuadros se interpolan
const MIN_TRIM_FRAMES = 3;
const HAND_BLOCK = PRESENCE_OFFSET + 1;

export const QUALITY_THRESHOLDS = { face: 0.8, dominantHand: 0.7, pose: 0.9 } as const;

export interface SequenceQuality {
  faceRatio: number;
  domHandRatio: number;
  poseRatio: number;
}

export type QualityCheck = { ok: true } | { ok: false; reason: string };

export interface QualityOptions {
  /** false para datasets sin cara visible (p. ej. LSC-54 pixelado). */
  faceRequired?: boolean;
  /** false para «NINGUNA»: las manos pueden estar abajo, fuera del cuadro. */
  handRequired?: boolean;
}

/** Motivo en español de una muestra descartada (H8), o ok. */
export function checkQuality(q: SequenceQuality, { faceRequired = true, handRequired = true }: QualityOptions = {}): QualityCheck {
  if (q.poseRatio < QUALITY_THRESHOLDS.pose) return { ok: false, reason: "No se vieron bien tus hombros." };
  if (handRequired && q.domHandRatio < QUALITY_THRESHOLDS.dominantHand) {
    return { ok: false, reason: "Tu mano salió del cuadro." };
  }
  if (faceRequired && q.faceRatio < QUALITY_THRESHOLDS.face) return { ok: false, reason: "No se vio bien tu cara." };
  return { ok: true };
}

function present(frame: Float32Array, block: number): boolean {
  return frame[block + PRESENCE_OFFSET] >= 0.5;
}

/** Rellena huecos de una mano de ≤ 3 cuadros interpolando entre los cuadros vecinos con mano. */
function fillGaps(frames: Float32Array[], times: number[], block: number): void {
  let i = 0;
  while (i < frames.length) {
    if (present(frames[i], block)) {
      i += 1;
      continue;
    }
    let end = i;
    while (end < frames.length && !present(frames[end], block)) end += 1;
    const before = i - 1;
    const after = end;
    if (before >= 0 && after < frames.length && end - i <= MAX_GAP) {
      for (let k = i; k < end; k += 1) {
        const w = (times[k] - times[before]) / (times[after] - times[before]);
        for (let j = 0; j < HAND_BLOCK; j += 1) {
          frames[k][block + j] = frames[before][block + j] * (1 - w) + frames[after][block + j] * w;
        }
        frames[k][block + PRESENCE_OFFSET] = 1;
      }
    }
    i = end;
  }
}

export class FrameSequencer {
  private readonly frames: Float32Array[] = [];
  private readonly times: number[] = [];
  /** Instantes de los cuadros sin pose: cuentan para la calidad, no entran en la secuencia. */
  private readonly missing: number[] = [];

  constructor(private readonly durationMs = SEQUENCE_DURATION_MS) {}

  /** `frame` null = cuadro sin pose (cuenta para la calidad, no para la secuencia). */
  push(frame: Float32Array | null, timestampMs: number): void {
    if (!frame) {
      this.missing.push(timestampMs);
      return;
    }
    if (this.times.length && timestampMs <= this.times[this.times.length - 1]) return; // timestamps crecientes
    this.frames.push(Float32Array.from(frame));
    this.times.push(timestampMs);
  }

  isComplete(): boolean {
    return this.times.length >= 2 && this.times[this.times.length - 1] - this.times[0] >= this.durationMs;
  }

  /** Primer y último instante con mano dominante (el tramo que conserva `trim`), o null. */
  private handSpan(): [number, number] | null {
    const first = this.frames.findIndex((f) => present(f, LAYOUT.dominant));
    const last = this.frames.findLastIndex((f) => present(f, LAYOUT.dominant));
    return first >= 0 && last - first >= MIN_TRIM_FRAMES - 1 ? [this.times[first], this.times[last]] : null;
  }

  /** Proporciones del control de calidad; con `trim`, medidas en el mismo tramo que se guarda. */
  quality({ trim = false }: { trim?: boolean } = {}): SequenceQuality {
    const span = trim ? this.handSpan() : null;
    const inside = (t: number) => !span || (t >= span[0] && t <= span[1]);
    const frames = this.frames.filter((_, i) => inside(this.times[i]));
    const total = Math.max(1, frames.length + this.missing.filter(inside).length);
    return {
      poseRatio: frames.length / total,
      domHandRatio: frames.filter((f) => present(f, LAYOUT.dominant)).length / total,
      faceRatio: frames.filter((f) => f[LAYOUT.facePresence] >= 0.5).length / total,
    };
  }

  /**
   * 30 cuadros equiespaciados (primero y último conservados), con interpolación lineal.
   * `trim`: solo el tramo entre el primer y el último cuadro con mano dominante, igual en la cámara y
   * en el importador (los videos de datasets duran 1–5 s; la seña es lo que importa).
   */
  toFrames({ trim = false }: { trim?: boolean } = {}): Float32Array[] {
    if (this.frames.length === 0) return [];
    let frames = this.frames.map((f) => Float32Array.from(f));
    let times = [...this.times];
    fillGaps(frames, times, LAYOUT.dominant);
    fillGaps(frames, times, LAYOUT.nonDominant);
    const span = trim ? this.handSpan() : null;
    if (span) {
      const first = times.indexOf(span[0]);
      const last = times.indexOf(span[1]);
      frames = frames.slice(first, last + 1);
      times = times.slice(first, last + 1);
    }
    return resample(frames, times);
  }

  reset(): void {
    this.frames.length = 0;
    this.times.length = 0;
    this.missing.length = 0;
  }
}

function resample(frames: Float32Array[], times: number[]): Float32Array[] {
  const first = times[0];
  const last = times[times.length - 1];
  const out: Float32Array[] = [];
  let j = 0;
  for (let k = 0; k < SEQUENCE_FRAMES; k += 1) {
    const t = frames.length === 1 ? first : first + ((last - first) * k) / (SEQUENCE_FRAMES - 1);
    while (j < frames.length - 2 && times[j + 1] < t) j += 1;
    const a = frames[j];
    const b = frames[Math.min(j + 1, frames.length - 1)];
    const span = times[Math.min(j + 1, frames.length - 1)] - times[j];
    const w = span > 0 ? Math.min(1, Math.max(0, (t - times[j]) / span)) : 0;
    const frame = new Float32Array(HOLISTIC_V2_SIZE);
    for (let i = 0; i < HOLISTIC_V2_SIZE; i += 1) frame[i] = a[i] * (1 - w) + b[i] * w;
    // Presencias binarias: si la mano (o la cara) no está, su bloque va en ceros.
    for (const block of [LAYOUT.dominant, LAYOUT.nonDominant]) {
      if (frame[block + PRESENCE_OFFSET] >= 0.5) frame[block + PRESENCE_OFFSET] = 1;
      else frame.fill(0, block, block + HAND_BLOCK);
    }
    frame[LAYOUT.facePresence] = frame[LAYOUT.facePresence] >= 0.5 ? 1 : 0;
    out.push(frame);
  }
  return out;
}

export interface ChosenSequence {
  frames: Float32Array[];
  quality: SequenceQuality;
  check: QualityCheck;
  /** true si se usó la otra mano (la persona firmó con la mano que no es la del perfil). */
  switchedHand: boolean;
}

/**
 * La mano del perfil manda (A.3.2); si con ella la muestra no pasa el control de calidad y con la otra
 * sí, se usa la otra (D-028): en los datasets no se sabe quién es zurdo y en vivo no todos configuran el
 * perfil. Con el reflejo de `buildHolisticFrame`, el modelo ve la misma forma en los dos casos.
 */
export function chooseSigningHand(
  primary: FrameSequencer,
  alternate: FrameSequencer,
  options: QualityOptions = {},
): ChosenSequence {
  const build = (sequencer: FrameSequencer, switchedHand: boolean): ChosenSequence => {
    const quality = sequencer.quality({ trim: true });
    return { frames: sequencer.toFrames({ trim: true }), quality, check: checkQuality(quality, options), switchedHand };
  };
  const first = build(primary, false);
  if (first.check.ok || options.handRequired === false) return first;
  const second = build(alternate, true);
  return second.check.ok ? second : first;
}
