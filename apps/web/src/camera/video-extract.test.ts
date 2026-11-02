// Nombres de los videos del colector «desde videos» (D-019).
import { describe, expect, it } from "vitest";
import { HOLD_END, HOLD_START, parseVideoName, sampleTimes } from "./video-extract";

describe("parseVideoName", () => {
  it("lee etiqueta y persona del nombre", () => {
    expect(parseVideoName("numero-3__p17__t0.mp4")).toEqual({ label: "numero-3", collector: "p17" });
    expect(parseVideoName("NINGUNA__p1__gracias-t2.mp4")).toEqual({ label: "NINGUNA", collector: "p1" });
    expect(parseVideoName("letra-a__ana__t1.webm")).toEqual({ label: "letra-a", collector: "ana" });
  });

  it("rechaza nombres que no siguen el formato o extensiones que el navegador no lee", () => {
    expect(parseVideoName("numero-3.mp4")).toBeNull();
    expect(parseVideoName("numero-3__p17__t0.avi")).toBeNull();
    expect(parseVideoName("Número 3__p17__t0.mp4")).toBeNull();
  });
});

describe("sampleTimes", () => {
  it("las señas se muestrean solo en la parte central del clip (sin subir ni bajar la mano)", () => {
    const times = sampleTimes(4, "numero-3");
    expect(times.length).toBeGreaterThan(0);
    expect(Math.min(...times)).toBeGreaterThanOrEqual(4 * HOLD_START);
    expect(Math.max(...times)).toBeLessThan(4 * HOLD_END);
  });

  it("NINGUNA usa el clip completo", () => {
    const times = sampleTimes(2, "NINGUNA");
    expect(Math.min(...times)).toBeLessThan(0.1);
    expect(times.length).toBe(20);
  });
});

describe("parseImageName", () => {
  it("lee etiqueta y persona de fotos (letras estáticas)", async () => {
    const { parseImageName, isImageFile } = await import("./video-extract");
    expect(parseImageName("letra-a__p12__foto3.jpg")).toEqual({ label: "letra-a", collector: "p12" });
    expect(parseImageName("NINGUNA__p1__x.png")).toEqual({ label: "NINGUNA", collector: "p1" });
    expect(parseImageName("letra-a__p12__foto3.mp4")).toBeNull();
    expect(parseImageName("Letra-A__p12__foto3.jpg")).toBeNull();
    expect(isImageFile("a.JPG")).toBe(true);
    expect(isImageFile("a.mp4")).toBe(false);
  });
});
