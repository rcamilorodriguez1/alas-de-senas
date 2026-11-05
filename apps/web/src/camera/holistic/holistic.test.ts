// Pruebas obligatorias del anexo A.12 (buildHolisticFrame y FrameSequencer) y H1–H4, H8.
import { describe, expect, it } from "vitest";
import {
  BLENDSHAPES,
  buildHolisticFrame,
  HOLISTIC_V2_SIZE,
  LAYOUT,
  missingBlendshapes,
  mirrorFrame,
  PRESENCE_OFFSET,
  type HolisticInput,
  type Point,
} from "./frame";
import { checkQuality, chooseSigningHand, FrameSequencer, SEQUENCE_FRAMES } from "./sequencer";

const p = (x: number, y: number, z = 0): Point => ({ x, y, z });

function hand(cx: number, cy: number): Point[] {
  return Array.from({ length: 21 }, (_, i) => (i === 9 ? p(cx, cy - 0.05) : p(cx + i * 0.002, cy - i * 0.001, i * 0.001)));
}

function pose(): Point[] {
  return Array.from({ length: 33 }, (_, i) => (i === 11 ? p(0.6, 0.5) : i === 12 ? p(0.4, 0.5) : p(0.5, 0.4)));
}

function input(overrides: Partial<HolisticInput> = {}): HolisticInput {
  return {
    poseLandmarks: [pose()],
    rightHandLandmarks: [hand(0.45, 0.45)],
    leftHandLandmarks: [hand(0.62, 0.6)],
    faceLandmarks: [Array.from({ length: 478 }, () => p(0.5, 0.3))],
    faceBlendshapes: [{ categories: BLENDSHAPES.map((name, i) => ({ categoryName: name, score: i / 100 })) }],
    ...overrides,
  };
}

function moved(data: HolisticInput, dx: number, dy: number, s: number): HolisticInput {
  const f = (pts: readonly Point[]) => pts.map((q) => p(0.5 + dx + (q.x - 0.5) * s, 0.5 + dy + (q.y - 0.5) * s, q.z * s));
  return {
    ...data,
    poseLandmarks: data.poseLandmarks.map(f),
    rightHandLandmarks: data.rightHandLandmarks.map(f),
    leftHandLandmarks: data.leftHandLandmarks.map(f),
    faceLandmarks: data.faceLandmarks.map(f),
  };
}

function close(a: Float32Array, b: Float32Array, tol = 1e-5) {
  expect(a.length).toBe(b.length);
  a.forEach((v, i) => expect(Math.abs(v - b[i])).toBeLessThanOrEqual(tol));
}

describe("buildHolisticFrame (A.12)", () => {
  it("siempre 159 valores, con y sin manos o cara", () => {
    expect(HOLISTIC_V2_SIZE).toBe(159);
    expect(buildHolisticFrame(input())?.length).toBe(159);
    expect(buildHolisticFrame(input({ rightHandLandmarks: [], leftHandLandmarks: [], faceLandmarks: [] }))?.length).toBe(159);
  });

  it("es invariante a trasladar o escalar todo el cuerpo", () => {
    const a = buildHolisticFrame(input());
    const b = buildHolisticFrame(moved(input(), 0.05, -0.03, 1.4));
    expect(a && b).toBeTruthy();
    if (a && b) close(a, b);
  });

  it("reflejo para zurdos: dos veces devuelve el original e intercambia blendshapes L/R", () => {
    const frame = buildHolisticFrame(input());
    expect(frame).not.toBeNull();
    if (!frame) return;
    close(mirrorFrame(mirrorFrame(frame)), frame, 0);
    const mirrored = mirrorFrame(frame);
    const i = BLENDSHAPES.indexOf("browDownLeft");
    const j = BLENDSHAPES.indexOf("browDownRight");
    expect(mirrored[LAYOUT.blendshapes + i]).toBeCloseTo(frame[LAYOUT.blendshapes + j]);
    expect(mirrored[LAYOUT.dominant + 3]).toBeCloseTo(-frame[LAYOUT.dominant + 3]);
  });

  it("zurdo: la mano izquierda va al slot dominante y el vector queda reflejado", () => {
    const data = input();
    const lefty = buildHolisticFrame({ ...data, rightHandLandmarks: data.leftHandLandmarks, leftHandLandmarks: data.rightHandLandmarks }, "left");
    const righty = buildHolisticFrame(data, "right");
    expect(lefty && righty).toBeTruthy();
    if (lefty && righty) close(mirrorFrame(lefty).subarray(LAYOUT.dominant, LAYOUT.dominant + 63), righty.subarray(0, 63));
  });

  it("mano ausente: bloque en ceros y presencia 0", () => {
    const frame = buildHolisticFrame(input({ leftHandLandmarks: [] }));
    expect(frame?.[LAYOUT.nonDominant + PRESENCE_OFFSET]).toBe(0);
    expect(Array.from(frame?.subarray(LAYOUT.nonDominant, LAYOUT.nonDominant + PRESENCE_OFFSET) ?? []).every((v) => v === 0)).toBe(true);
    expect(frame?.[LAYOUT.dominant + PRESENCE_OFFSET]).toBe(1);
  });

  it("pose ausente o hombros superpuestos: null", () => {
    expect(buildHolisticFrame(input({ poseLandmarks: [] }))).toBeNull();
    const flat = pose().map(() => p(0.5, 0.5));
    expect(buildHolisticFrame(input({ poseLandmarks: [flat] }))).toBeNull();
  });

  it("los blendshapes se buscan por nombre, no por posición (H4)", () => {
    const shuffled = [...BLENDSHAPES].reverse().map((name) => ({ categoryName: name, score: name === "jawOpen" ? 0.9 : 0 }));
    const frame = buildHolisticFrame(input({ faceBlendshapes: [{ categories: shuffled }] }));
    expect(frame?.[LAYOUT.blendshapes + BLENDSHAPES.indexOf("jawOpen")]).toBeCloseTo(0.9);
    expect(missingBlendshapes(["jawOpen"])).toHaveLength(BLENDSHAPES.length - 1);
    expect(missingBlendshapes([...BLENDSHAPES])).toEqual([]);
  });
});

describe("FrameSequencer (A.12)", () => {
  const frame = (handPresent = true) => {
    const f = buildHolisticFrame(handPresent ? input() : input({ rightHandLandmarks: [] }));
    if (!f) throw new Error("cuadro inválido");
    return f;
  };

  it("23 cuadros con timestamps irregulares → exactamente 30, primero y último conservados", () => {
    const s = new FrameSequencer();
    const first = frame();
    const last = frame();
    last[LAYOUT.dominant + 64] = 0.77; // marca en la posición y del último cuadro
    let t = 0;
    for (let i = 0; i < 23; i += 1) {
      s.push(i === 22 ? last : first, t);
      t += 50 + (i % 4) * 40; // 50–170 ms: ritmo irregular
    }
    const out = s.toFrames();
    expect(out).toHaveLength(SEQUENCE_FRAMES);
    close(out[0], first);
    expect(out[SEQUENCE_FRAMES - 1][LAYOUT.dominant + 64]).toBeCloseTo(0.77);
  });

  it("interpola huecos de la mano de hasta 3 cuadros; huecos mayores marcan ausencia", () => {
    const short = new FrameSequencer();
    [true, false, false, false, true].forEach((h, i) => short.push(frame(h), i * 100));
    expect(short.toFrames().every((f) => f[LAYOUT.dominant + PRESENCE_OFFSET] === 1)).toBe(true);

    const long = new FrameSequencer();
    [true, false, false, false, false, true].forEach((h, i) => long.push(frame(h), i * 100));
    const out = long.toFrames();
    expect(out.some((f) => f[LAYOUT.dominant + PRESENCE_OFFSET] === 0)).toBe(true);
  });

  it("control de calidad: rechaza con el motivo correcto (H8)", () => {
    expect(checkQuality({ faceRatio: 1, domHandRatio: 1, poseRatio: 0.5 })).toEqual({ ok: false, reason: "No se vieron bien tus hombros." });
    expect(checkQuality({ faceRatio: 1, domHandRatio: 0.5, poseRatio: 1 })).toEqual({ ok: false, reason: "Tu mano salió del cuadro." });
    expect(checkQuality({ faceRatio: 0.5, domHandRatio: 1, poseRatio: 1 })).toEqual({ ok: false, reason: "No se vio bien tu cara." });
    expect(checkQuality({ faceRatio: 0, domHandRatio: 1, poseRatio: 1 }, { faceRequired: false })).toEqual({ ok: true });
    // «NINGUNA»: las manos pueden estar abajo.
    expect(checkQuality({ faceRatio: 1, domHandRatio: 0, poseRatio: 1 }, { handRequired: false })).toEqual({ ok: true });
  });

  it("trim: remuestrea solo el tramo entre el primer y el último cuadro con mano dominante", () => {
    const s = new FrameSequencer();
    const marked = frame();
    marked[LAYOUT.dominant + 64] = 0.5;
    const flags = [false, false, false, false, false, true, true, true, true, false, false, false, false, false];
    flags.forEach((h, i) => s.push(h ? (i === 5 ? marked : frame()) : frame(false), i * 100));
    const trimmed = s.toFrames({ trim: true });
    expect(trimmed).toHaveLength(SEQUENCE_FRAMES);
    expect(trimmed.every((f) => f[LAYOUT.dominant + PRESENCE_OFFSET] === 1)).toBe(true);
    expect(trimmed[0][LAYOUT.dominant + 64]).toBeCloseTo(0.5);
    expect(s.toFrames().some((f) => f[LAYOUT.dominant + PRESENCE_OFFSET] === 0)).toBe(true);
  });

  it("con trim, la calidad se mide en el tramo con mano (subir y bajar las manos no descarta la seña)", () => {
    const s = new FrameSequencer();
    const flags = [false, false, false, false, true, true, true, true, true, true, false, false, false, false];
    flags.forEach((h, i) => s.push(frame(h), i * 100));
    s.push(null, 1500);
    expect(s.quality().domHandRatio).toBeCloseTo(6 / 15);
    expect(s.quality({ trim: true }).domHandRatio).toBe(1);
    expect(s.quality({ trim: true }).poseRatio).toBe(1);
  });

  it("cuadros sin pose cuentan para la calidad y la secuencia está completa a los 2 s", () => {
    const s = new FrameSequencer();
    s.push(null, 0);
    s.push(frame(), 10);
    expect(s.isComplete()).toBe(false);
    s.push(frame(), 2100);
    expect(s.isComplete()).toBe(true);
    expect(s.quality().poseRatio).toBeCloseTo(2 / 3);
  });

  it("elige la mano que firma: la del perfil si pasa; si no, la otra (D-028)", () => {
    const filled = (withHand: boolean) => {
      const s = new FrameSequencer();
      for (let i = 0; i < 10; i += 1) s.push(frame(withHand), i * 100);
      return s;
    };
    const right = chooseSigningHand(filled(true), filled(false));
    expect(right.switchedHand).toBe(false);
    expect(right.check.ok).toBe(true);
    const left = chooseSigningHand(filled(false), filled(true));
    expect(left.switchedHand).toBe(true);
    expect(left.check.ok).toBe(true);
    expect(left.frames).toHaveLength(SEQUENCE_FRAMES);
    const none = chooseSigningHand(filled(false), filled(false));
    expect(none).toMatchObject({ switchedHand: false, check: { ok: false, reason: "Tu mano salió del cuadro." } });
    // «NINGUNA» no exige mano: siempre la del perfil.
    expect(chooseSigningHand(filled(false), filled(true), { handRequired: false }).switchedHand).toBe(false);
  });
});
