// Captura flexible de señas con movimiento (plan de mejora, etapa 6; D-045).
import { describe, expect, it } from "vitest";
import { CAPTURE_MESSAGES, captureCheck, FIXED_CAPTURE, MANUAL_CAPTURE } from "./capture";
import { SEQUENCE_DURATION_MS } from "./sequencer";

const fail = (reason: string) => ({ ok: false, reason });

describe("límites de captura", () => {
  it("el modo fijo es la ventana de 2 s de siempre; el manual dura entre 0,5 y 4 s", () => {
    expect(FIXED_CAPTURE).toEqual({ minMs: SEQUENCE_DURATION_MS, maxMs: SEQUENCE_DURATION_MS });
    expect(MANUAL_CAPTURE).toEqual({ minMs: 500, maxMs: 4000 });
  });
});

describe("captureCheck", () => {
  it("al llegar al máximo la muestra sigue al control de calidad", () => {
    expect(captureCheck(2000, "limit", FIXED_CAPTURE)).toEqual({ ok: true });
    expect(captureCheck(4000, "limit", MANUAL_CAPTURE)).toEqual({ ok: true });
  });

  it("«Terminar» después del mínimo vale; antes, la captura queda incompleta", () => {
    expect(captureCheck(1200, "user", MANUAL_CAPTURE)).toEqual({ ok: true });
    expect(captureCheck(500, "user", MANUAL_CAPTURE)).toEqual({ ok: true });
    expect(captureCheck(499, "user", MANUAL_CAPTURE)).toEqual(fail(CAPTURE_MESSAGES.tooShort));
  });

  it("interrumpida (pestaña oculta o cámara apagada) antes del máximo nunca se clasifica", () => {
    expect(captureCheck(1999, "interrupted", FIXED_CAPTURE)).toEqual(fail(CAPTURE_MESSAGES.interrupted));
    // En el modo manual, quien no pulsó «Terminar» no acabó la seña aunque hayan pasado 3 s.
    expect(captureCheck(3000, "interrupted", MANUAL_CAPTURE)).toEqual(fail(CAPTURE_MESSAGES.interrupted));
    expect(captureCheck(2000, "interrupted", FIXED_CAPTURE)).toEqual({ ok: true });
  });

  it("cancelada siempre se descarta", () => {
    expect(captureCheck(3000, "cancelled", MANUAL_CAPTURE)).toEqual(fail(CAPTURE_MESSAGES.cancelled));
  });

  it("el mensaje de interrupción es el que ya conocían las lecciones", () => {
    expect(CAPTURE_MESSAGES.interrupted).toBe("La grabación se interrumpió.");
  });
});
