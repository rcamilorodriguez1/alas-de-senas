// Registro de datasets externos (`content/datasets.csv`, D-044): fuente, licencia, enlace y cita.
// La página de importación toma de aquí la licencia y /creditos muestra la atribución.
import datasetsCsv from "../../../../../content/datasets.csv?raw";

export interface DatasetInfo {
  source: string;
  license: string;
  link: string;
  citation: string;
}

const HEADER = ["fuente", "licencia", "enlace", "cita"];

/** Una línea CSV con campos opcionalmente entre comillas ("" = comilla literal). */
function splitCsvLine(line: string): string[] {
  const cells: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (quoted) {
      if (char === '"' && line[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        cell += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      cells.push(cell.trim());
      cell = "";
    } else {
      cell += char;
    }
  }
  cells.push(cell.trim());
  return cells;
}

export function parseDatasets(csv: string): DatasetInfo[] {
  const [header, ...lines] = csv.split(/\r?\n/).filter((line) => line.trim() && !line.startsWith("#"));
  if (!header || splitCsvLine(header).join(",") !== HEADER.join(",")) return [];
  const datasets: DatasetInfo[] = [];
  for (const line of lines) {
    const [source = "", license = "", link = "", citation = ""] = splitCsvLine(line);
    if (source && license && link && citation) datasets.push({ source, license, link, citation });
  }
  return datasets;
}

export const DATASETS = parseDatasets(datasetsCsv);

export function licenseFor(source: string, datasets: readonly DatasetInfo[] = DATASETS): string {
  return datasets.find((d) => d.source === source)?.license ?? "";
}
