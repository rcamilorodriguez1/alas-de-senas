// Registro de datasets externos (D-044): fuente, licencia, enlace y cita.
import { describe, expect, it } from "vitest";
import { DATASETS, licenseFor, parseDatasets } from "./datasets";

describe("content/datasets.csv", () => {
  it("el archivo real trae LSC-54 con su licencia CC BY-NC 4.0", () => {
    const lsc54 = DATASETS.find((d) => d.source === "LSC-54");
    expect(lsc54?.license).toBe("CC BY-NC 4.0");
    expect(lsc54?.link).toMatch(/^https:\/\//);
    expect(lsc54?.citation).toContain("Mora-Zarate");
  });

  it("lee citas entre comillas aunque tengan comas, y comillas dobles escapadas", () => {
    const parsed = parseDatasets(
      'fuente,licencia,enlace,cita\n# comentario\nX,CC BY 4.0,https://x.org,"Pérez, Gómez y otros (2024), «Título»"\nY,CC0,https://y.org,"Dijo ""hola"""\n',
    );
    expect(parsed).toEqual([
      { source: "X", license: "CC BY 4.0", link: "https://x.org", citation: "Pérez, Gómez y otros (2024), «Título»" },
      { source: "Y", license: "CC0", link: "https://y.org", citation: 'Dijo "hola"' },
    ]);
  });

  it("con otra cabecera no devuelve nada y salta filas incompletas", () => {
    expect(parseDatasets("fuente,licencia\nX,CC BY\n")).toEqual([]);
    expect(parseDatasets("fuente,licencia,enlace,cita\nX,,https://x.org,cita\n")).toEqual([]);
  });

  it("licenseFor devuelve la licencia de la fuente o vacío", () => {
    expect(licenseFor("LSC-54")).toBe("CC BY-NC 4.0");
    expect(licenseFor("desconocida")).toBe("");
  });
});
