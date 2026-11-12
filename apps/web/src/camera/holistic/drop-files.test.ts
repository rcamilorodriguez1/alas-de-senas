// Archivos soltados en /admin/importar (D-044): archivos sueltos y carpetas completas, con subcarpetas.
import { describe, expect, it } from "vitest";
import { droppedFiles, type DropEntry } from "./drop-files";

const video = (name: string) => new File(["x"], name, { type: "video/mp4" });

function fileEntry(file: File): DropEntry {
  return { isFile: true, isDirectory: false, file: (ok) => ok(file) };
}

/** Carpeta que entrega sus hijos en lotes, como Chrome (máximo 100 por llamada). */
function folderEntry(children: DropEntry[], batch = 2): DropEntry {
  return {
    isFile: false,
    isDirectory: true,
    createReader: () => {
      let next = 0;
      return {
        readEntries: (ok) => {
          ok(children.slice(next, next + batch));
          next += batch;
        },
      };
    },
  };
}

const item = (entry: DropEntry | null) => ({ kind: "file", webkitGetAsEntry: () => entry });

describe("droppedFiles", () => {
  it("sin items (navegador antiguo o pruebas) usa la lista de archivos", async () => {
    const files = [video("a.mp4"), video("b.mp4")];
    expect((await droppedFiles({ files })).map((f) => f.name)).toEqual(["a.mp4", "b.mp4"]);
  });

  it("expande una carpeta con subcarpetas y lee todos los lotes", async () => {
    const tree = folderEntry([
      fileEntry(video("Hola__p1__1.mp4")),
      fileEntry(video("Hola__p1__2.mp4")),
      folderEntry([fileEntry(video("Chao__p2__1.mp4"))]),
      fileEntry(video("Si__p3__1.mp4")),
    ]);
    const files = await droppedFiles({ files: [], items: [item(tree)] });
    expect(files.map((f) => f.name)).toEqual([
      "Hola__p1__1.mp4",
      "Hola__p1__2.mp4",
      "Chao__p2__1.mp4",
      "Si__p3__1.mp4",
    ]);
  });

  it("mezcla archivos sueltos y carpetas; ignora lo que no es archivo", async () => {
    const files = await droppedFiles({
      files: [],
      items: [
        item(fileEntry(video("a.mp4"))),
        { kind: "string", webkitGetAsEntry: () => null },
        item(folderEntry([fileEntry(video("b.mp4"))])),
      ],
    });
    expect(files.map((f) => f.name)).toEqual(["a.mp4", "b.mp4"]);
  });

  it("si un archivo no se puede leer, sigue con los demás", async () => {
    const broken: DropEntry = { isFile: true, isDirectory: false, file: (_ok, fail) => fail?.(new DOMException("x")) };
    const files = await droppedFiles({ files: [], items: [item(folderEntry([broken, fileEntry(video("b.mp4"))]))] });
    expect(files.map((f) => f.name)).toEqual(["b.mp4"]);
  });
});
