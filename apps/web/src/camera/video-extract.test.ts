// Nombres de los videos del colector «desde videos» (D-019).
import { describe, expect, it } from "vitest";
import { parseVideoName } from "./video-extract";

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
