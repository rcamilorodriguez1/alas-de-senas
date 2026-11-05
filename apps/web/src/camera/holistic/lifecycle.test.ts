// Ciclo de vida de la cámara holística (revisión 10B): cancelar mientras carga no enciende la cámara,
// muestras interrumpidas no se clasifican y la caché de etiquetas no guarda fallos.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const close = vi.fn();
const create = vi.fn();
vi.mock("./extractor", () => ({
  HolisticExtractorV2: { create: (...args: unknown[]) => create(...args) },
}));

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
