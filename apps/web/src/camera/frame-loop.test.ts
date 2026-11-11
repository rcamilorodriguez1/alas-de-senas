// Bucle por cuadro (D-038): solo se procesa cuando la cámara entrega un cuadro nuevo.
import { describe, expect, it, vi } from "vitest";
import { createFrameScheduler, FpsMeter, type VideoFrameSource } from "./frame-loop";

describe("createFrameScheduler", () => {
  it("usa requestVideoFrameCallback si el navegador lo tiene", () => {
    const requestVideoFrameCallback = vi.fn(() => 7);
    const cancelVideoFrameCallback = vi.fn();
    const video: VideoFrameSource = {
      requestVideoFrameCallback,
      cancelVideoFrameCallback,
    };
    const scheduler = createFrameScheduler(video);
    expect(scheduler.source).toBe("video");
    const callback = vi.fn();
    scheduler.request(callback);
    expect(requestVideoFrameCallback).toHaveBeenCalledTimes(1);
    scheduler.cancel();
    expect(cancelVideoFrameCallback).toHaveBeenCalledWith(7);
  });

  it("pasa el instante del cuadro al callback", () => {
    const pending: ((now: number) => void)[] = [];
    const video = {
      requestVideoFrameCallback: (cb: (now: number) => void) => pending.push(cb),
      cancelVideoFrameCallback: () => undefined,
    };
    const callback = vi.fn();
    createFrameScheduler(video).request(callback);
    pending[0](123.5);
    expect(callback).toHaveBeenCalledWith(123.5);
  });

  it("sin requestVideoFrameCallback cae a requestAnimationFrame", () => {
    const raf = vi.spyOn(window, "requestAnimationFrame").mockReturnValue(3);
    const caf = vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
    const scheduler = createFrameScheduler({});
    expect(scheduler.source).toBe("animation");
    scheduler.request(() => undefined);
    expect(raf).toHaveBeenCalledTimes(1);
    scheduler.cancel();
    expect(caf).toHaveBeenCalledWith(3);
    raf.mockRestore();
    caf.mockRestore();
  });

  it("cancelar sin nada pendiente no falla", () => {
    expect(() => createFrameScheduler({}).cancel()).not.toThrow();
  });
});

describe("FpsMeter", () => {
  it("sin datos suficientes no reporta nada", () => {
    const meter = new FpsMeter();
    expect(meter.tick(0, 5)).toBeNull();
  });

  it("cuenta cuadros por segundo y el tiempo medio de trabajo del último segundo", () => {
    const meter = new FpsMeter();
    let stats = null;
    // 30 cuadros cada 33,3 ms con 10 ms de trabajo.
    for (let i = 0; i <= 30; i += 1) stats = meter.tick(i * (1000 / 30), 10) ?? stats;
    expect(stats?.fps).toBeGreaterThanOrEqual(29);
    expect(stats?.fps).toBeLessThanOrEqual(31);
    expect(stats?.workMs).toBeCloseTo(10, 5);
  });

  it("se adapta cuando el equipo se pone lento", () => {
    const meter = new FpsMeter();
    let stats = null;
    for (let i = 0; i <= 30; i += 1) stats = meter.tick(i * 33, 10) ?? stats;
    const start = 30 * 33;
    for (let i = 1; i <= 12; i += 1) stats = meter.tick(start + i * 100, 60) ?? stats;
    expect(stats?.fps).toBeGreaterThanOrEqual(9);
    expect(stats?.fps).toBeLessThanOrEqual(11);
    expect(stats?.workMs).toBeCloseTo(60, 5);
  });

  it("reset borra la historia", () => {
    const meter = new FpsMeter();
    for (let i = 0; i <= 30; i += 1) meter.tick(i * 33, 10);
    meter.reset();
    expect(meter.tick(5000, 10)).toBeNull();
  });
});
