// Importador /admin/importar (A.7.1): mapeo de etiquetas externas y agrupación de archivos.
import { describe, expect, it } from "vitest";
import mappingCsv from "../../../../../content/dataset-mapping.csv?raw";
import { groupFiles, parseMapping, resolveLabel, slugify, waitFor } from "./importer";

const file = (name: string) => new File(["x"], name);

describe("mapeo de datasets externos (A.7 regla 3)", () => {
  const mapping = parseMapping(mappingCsv);

  it("lee content/dataset-mapping.csv y traduce las señas de LSC-54", () => {
    expect(mapping.length).toBeGreaterThan(3);
    expect(resolveLabel("chao", "LSC-54", mapping)).toBe("adios");
    expect(resolveLabel("Buenas Noches", "LSC-54", mapping)).toBe("buenas-noches");
    expect(resolveLabel("por-favor", "LSC-54", mapping)).toBe("por-favor");
    expect(resolveLabel("bien", "LSC-54", mapping)).toBe("NINGUNA");
  });

  it("traduce las señas de LSC-54 S2 que están en el currículo, con el nombre de archivo preparado", () => {
    const expected: Record<string, string> = {
      Denada: "de-nada",
      "Buenos-dias": "buenos-dias",
      "Buenas-tardes": "buenas-tardes",
      "Buenas-noches": "buenas-noches",
      Gracias: "gracias",
      "Como-esta": "como-estas",
      Si: "si",
      No: "no",
      Permiso: "con-permiso",
      Seis: "numero-6",
      Siete: "numero-7",
      Ocho: "numero-8",
      Nueve: "numero-9",
      Diez: "numero-10",
    };
    for (const [fileLabel, slug] of Object.entries(expected)) {
      expect(resolveLabel(fileLabel, "LSC-54", mapping), fileLabel).toBe(slug);
    }
  });

  it("los números estáticos 1–5 no entran al modelo de movimiento (son del alfabeto)", () => {
    for (const fileLabel of ["Uno", "Dos", "Tres", "Cuatro", "Cinco"]) {
      expect(resolveLabel(fileLabel, "LSC-54", mapping), fileLabel).toBeNull();
    }
  });

  it("NINGUNA: señas de LSC-54 fuera del currículo, nunca una que el currículo enseña (D-044)", () => {
    for (const fileLabel of ["Bien", "Mal", "Sentarse", "Esperar", "Tranquilo", "Lo-siento", "Mas-o-menos"]) {
      expect(resolveLabel(fileLabel, "LSC-54", mapping), fileLabel).toBe("NINGUNA");
    }
    // «Ayudar» ≈ «Ayuda» (M3-N4) y «Baño» (M3-N2) están en el currículo; «Muchas gracias» contiene «gracias».
    for (const fileLabel of ["Ayudar", "Bano", "Muchas-gracias"]) {
      expect(resolveLabel(fileLabel, "LSC-54", mapping), fileLabel).toBeNull();
    }
  });

  it("las señas que no están en el mapeo se ignoran (null)", () => {
    expect(resolveLabel("bano", "LSC-54", mapping)).toBeNull();
    expect(resolveLabel("hola", "otra-fuente", mapping)).toBeNull();
    expect(resolveLabel("NINGUNA", "LSC-54", mapping)).toBe("NINGUNA");
  });

  it("cabecera incorrecta → sin filas; comentarios ignorados", () => {
    expect(parseMapping("a,b,c\nx,y,z")).toEqual([]);
    expect(parseMapping("fuente,etiqueta_fuente,slug\n# nota\nX,Hola,hola\n")).toEqual([
      { source: "X", sourceLabel: "Hola", slug: "hola" },
    ]);
    expect(slugify(" Buenos Días ")).toBe("buenos-dias");
  });
});

describe("agrupación de archivos", () => {
  it("un video = una muestra; imágenes con número = una secuencia ordenada", () => {
    const { items, ignored } = groupFiles([
      file("hola__p1__t0.mp4"),
      file("hola__p1__t1.mp4"),
      file("chao__p2__t0-0002.jpg"),
      file("chao__p2__t0-0001.jpg"),
      file("foto.jpg"),
      file("hola__p1__t0.txt"),
    ]);
    expect(ignored).toEqual(["foto.jpg", "hola__p1__t0.txt"]);
    expect(items.map((i) => [i.key, i.kind, i.collector, i.files.length])).toEqual([
      ["chao__p2__t0", "images", "p2", 2],
      ["hola__p1__t0.mp4", "video", "p1", 1],
      ["hola__p1__t1.mp4", "video", "p1", 1],
    ]);
    expect(items[0].files.map((f) => f.name)).toEqual(["chao__p2__t0-0001.jpg", "chao__p2__t0-0002.jpg"]);
  });
});

describe("eventos del video", () => {
  it("si «seeked» nunca llega, falla a tiempo en vez de congelar el lote", async () => {
    const video = document.createElement("video");
    await expect(waitFor(video, "seeked", 20)).rejects.toThrow(/no respondió a tiempo/);
  });

  it("resuelve con el evento y rechaza con un error del video", async () => {
    const video = document.createElement("video");
    const ok = waitFor(video, "seeked", 1000);
    video.dispatchEvent(new Event("seeked"));
    await expect(ok).resolves.toBeUndefined();
    const bad = waitFor(video, "loadeddata", 1000);
    video.dispatchEvent(new Event("error"));
    await expect(bad).rejects.toThrow(/no pudo leer/);
  });
});
