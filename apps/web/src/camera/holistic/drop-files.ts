// Archivos soltados en /admin/importar (D-044). Al arrastrar una carpeta, `dataTransfer.files` solo trae la
// carpeta (sin contenido): hay que recorrerla con la API de entradas (`webkitGetAsEntry`), que Chrome y Edge
// soportan, leyendo cada carpeta por lotes hasta que devuelva uno vacío.

/** Lo mínimo de `FileSystemEntry` que se usa (también lo cumplen los objetos falsos de las pruebas). */
export interface DropEntry {
  readonly isFile: boolean;
  readonly isDirectory: boolean;
  file?: (success: (file: File) => void, failure?: (error: DOMException) => void) => void;
  createReader?: () => {
    readEntries: (success: (entries: DropEntry[]) => void, failure?: (error: DOMException) => void) => void;
  };
}

interface DropItem {
  readonly kind: string;
  webkitGetAsEntry: () => DropEntry | null;
}

export interface DropData {
  readonly files: ArrayLike<File>;
  readonly items?: ArrayLike<DropItem>;
}

async function collect(entry: DropEntry, out: File[]): Promise<void> {
  const { file, createReader } = entry;
  if (entry.isFile && file) {
    try {
      out.push(await new Promise<File>((resolve, reject) => file(resolve, reject)));
    } catch {
      // Un archivo ilegible no detiene el resto; simplemente no aparece en el resumen.
    }
    return;
  }
  if (!entry.isDirectory || !createReader) return;
  const reader = createReader();
  for (;;) {
    const batch = await new Promise<DropEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
    if (batch.length === 0) return;
    for (const child of batch) await collect(child, out);
  }
}

/**
 * Archivos de lo que se soltó, expandiendo carpetas y subcarpetas. Las entradas se toman antes del primer
 * `await`, porque el navegador invalida `dataTransfer` en cuanto termina el evento `drop`.
 */
export async function droppedFiles(data: DropData): Promise<File[]> {
  const entries = Array.from(data.items ?? []).flatMap((item) => {
    if (item.kind !== "file") return [];
    const entry = item.webkitGetAsEntry();
    return entry ? [entry] : [];
  });
  const loose = Array.from(data.files);
  if (entries.length === 0) return loose;
  const out: File[] = [];
  for (const entry of entries) await collect(entry, out);
  return out;
}
