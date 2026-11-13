// Ciclo de vida de la cámara holística (revisión 10B): cancelar mientras carga no enciende la cámara,
// muestras interrumpidas no se clasifican y la caché de etiquetas no guarda fallos.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const close = vi.fn();
const create = vi.fn();
vi.mock("./extractor", () => ({
  HolisticExtractorV2: { create: (...args: unknown[]) => create(...args) },
}));

import { CAPTURE_MESSAGES, MANUAL_CAPTURE } from "./capture";
import { startGestureSession } from "./gesture-session";
import { fetchGestureLabels, resetGestureLabelsCache } from "./sequence-classifier";

const getUserMedia = vi.fn();

beforeEach(() => {
  close.mockReset();
  create.mockReset();
  getUserMedia.mockReset();
  create.mockResolvedValue({ close, extract: () => null, delegate: "CPU" });
  vi.stubGlobal("isSecureContext", true);
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("startGestureSession (R8.5)", () => {
  it("si la persona salió mientras cargaba el detector, la cámara nunca se enciende", async () => {
    const video = document.createElement("video");
    await expect(
      startGestureSession(video, { dominantHand: "right", onFrame: vi.fn(), isCancelled: () => true }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(close).toHaveBeenCalledOnce();
  });

  it("si cancela después de pedir la cámara, se apagan las pistas y se cierra el detector", async () => {
    const stop = vi.fn();
    getUserMedia.mockResolvedValue({ getTracks: () => [{ stop }] });
    let calls = 0;
    const video = document.createElement("video");
    await expect(
      startGestureSession(video, {
        dominantHand: "right",
        onFrame: vi.fn(),
        isCancelled: () => (calls += 1) > 1, // sale justo después de conceder la cámara
      }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(stop).toHaveBeenCalledOnce();
    expect(close).toHaveBeenCalledOnce();
    expect(video.srcObject).toBeNull();
  });

  it("si se niega el permiso, el detector se cierra igual", async () => {
    getUserMedia.mockRejectedValue(new DOMException("no", "NotAllowedError"));
    await expect(
      startGestureSession(document.createElement("video"), { dominantHand: "right", onFrame: vi.fn() }),
    ).rejects.toMatchObject({ name: "NotAllowedError" });
    expect(close).toHaveBeenCalledOnce();
  });

  it("una grabación interrumpida antes de 2 s no se clasifica", async () => {
    const stop = vi.fn();
    getUserMedia.mockResolvedValue({ getTracks: () => [{ stop }] });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    vi.stubGlobal("requestAnimationFrame", () => 1);
    vi.stubGlobal("cancelAnimationFrame", () => undefined);
    const session = await startGestureSession(document.createElement("video"), { dominantHand: "right", onFrame: vi.fn() });
    const recording = session.record();
    session.stop(); // apaga la cámara a mitad de la grabación
    const sample = await recording;
    expect(sample.check).toEqual({ ok: false, reason: "La grabación se interrumpió." });
    expect(stop).toHaveBeenCalled();
    expect(close).toHaveBeenCalled();
  });

  describe("captura manual (D-045)", () => {
    async function manualSession() {
      getUserMedia.mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] });
      vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
      vi.stubGlobal("requestAnimationFrame", () => 1);
      vi.stubGlobal("cancelAnimationFrame", () => undefined);
      return startGestureSession(document.createElement("video"), { dominantHand: "right", onFrame: vi.fn() });
    }

    it("«Terminar» enseguida: captura incompleta, no se clasifica", async () => {
      const now = vi.spyOn(performance, "now").mockReturnValue(1000);
      const session = await manualSession();
      const handle = session.capture({}, MANUAL_CAPTURE);
      now.mockReturnValue(1200);
      handle.end();
      expect((await handle.result).check).toEqual({ ok: false, reason: CAPTURE_MESSAGES.tooShort });
      session.stop();
    });

    it("«Terminar» después del mínimo: decide el control de calidad", async () => {
      const now = vi.spyOn(performance, "now").mockReturnValue(1000);
      const session = await manualSession();
      const handle = session.capture({}, MANUAL_CAPTURE);
      now.mockReturnValue(2500);
      handle.end();
      // Sin cuadros (el detector falso no ve a nadie): el motivo es de calidad, no de duración.
      expect((await handle.result).check).toEqual({ ok: false, reason: "No se vieron bien tus hombros." });
      session.stop();
    });

    it("«Cancelar» descarta la grabación", async () => {
      const session = await manualSession();
      const handle = session.capture({}, MANUAL_CAPTURE);
      handle.cancel();
      expect((await handle.result).check).toEqual({ ok: false, reason: CAPTURE_MESSAGES.cancelled });
      session.stop();
    });

    it("«Terminar» de una grabación vieja no cierra la siguiente", async () => {
      const now = vi.spyOn(performance, "now").mockReturnValue(1000);
      const session = await manualSession();
      const old = session.capture({}, MANUAL_CAPTURE);
      const current = session.capture({}, MANUAL_CAPTURE); // la vieja se cierra como interrumpida
      expect((await old.result).check).toEqual({ ok: false, reason: CAPTURE_MESSAGES.interrupted });
      old.end();
      old.cancel();
      let settled = false;
      void current.result.then(() => {
        settled = true;
      });
      await Promise.resolve();
      expect(settled).toBe(false);
      now.mockReturnValue(1100);
      current.end();
      expect((await current.result).check).toEqual({ ok: false, reason: CAPTURE_MESSAGES.tooShort });
      session.stop();
    });

    it("apagar la cámara a mitad de una captura manual la interrumpe", async () => {
      const session = await manualSession();
      const handle = session.capture({}, MANUAL_CAPTURE);
      session.stop();
      expect((await handle.result).check).toEqual({ ok: false, reason: CAPTURE_MESSAGES.interrupted });
    });
  });
});

describe("fetchGestureLabels", () => {
  it("un fallo de red no queda en caché: el siguiente intento puede activar el modo gestos", async () => {
    resetGestureLabelsCache();
    const meta = {
      featureVersion: "holistic-v2",
      featureSize: 159,
      frames: 30,
      mean: Array.from({ length: 159 }, () => 0),
      std: Array.from({ length: 159 }, () => 1),
      labels: ["NINGUNA", "hola"],
    };
    const failing = vi.fn().mockRejectedValue(new Error("red"));
    expect(await fetchGestureLabels(failing)).toEqual([]);
    const ok = vi.fn().mockResolvedValue(new Response(JSON.stringify(meta)));
    expect(await fetchGestureLabels(ok)).toEqual(["hola"]);
    // Un modelo válido sí queda en caché.
    expect(await fetchGestureLabels(failing)).toEqual(["hola"]);
  });
});
