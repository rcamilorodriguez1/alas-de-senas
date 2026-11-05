import { useEffect, useRef, useState } from "react";
import mappingCsv from "../../../../../content/dataset-mapping.csv?raw";
import { AppLayout } from "../../components/layout/AppLayout";
import { buildHolisticDataset, countByLabel, downloadJson, type HolisticSample } from "../../camera/holistic/dataset-v2";
import { groupFiles, importItems, parseMapping, type ImportItem } from "../../camera/holistic/importer";
import { useSessionStore } from "../../lib/session-store";

const MAPPING = parseMapping(mappingCsv);
const SOURCES = [...new Set(MAPPING.map((row) => row.source))];
const LICENSES: Record<string, string> = { "LSC-54": "CC BY-NC 4.0" };

/** Importador `/admin/importar` (anexo A.7.1): datasets externos con el mismo pipeline del navegador. */
export function ImportPage() {
  const isAdmin = useSessionStore((state) => state.user?.role === "ADMIN");
  const [source, setSource] = useState(SOURCES[0] ?? "");
  const [license, setLicense] = useState(LICENSES[SOURCES[0] ?? ""] ?? "");
  const [faceFeatures, setFaceFeatures] = useState(false);
  const [items, setItems] = useState<ImportItem[]>([]);
  const [ignored, setIgnored] = useState<string[]>([]);
  const [samples, setSamples] = useState<HolisticSample[]>([]);
  const [rejected, setRejected] = useState<{ item: string; reason: string }[]>([]);
  const [done, setDone] = useState(0);
  const [running, setRunning] = useState(false);
  const pause = useRef(false);
  // Al salir de la página se detiene el lote (y se liberan los detectores de MediaPipe).
  useEffect(
    () => () => {
      pause.current = true;
    },
    [],
  );

  if (!isAdmin) {
    return (
      <AppLayout>
        <h1 className="font-display text-3xl font-extrabold">Importar dataset</h1>
        <p role="alert" className="mt-4">
          Esta página es solo para administradores.
        </p>
      </AppLayout>
    );
  }

  const choose = (files: FileList | null) => {
    const grouped = groupFiles(files ? [...files] : []);
    setItems(grouped.items);
    setIgnored(grouped.ignored);
    setSamples([]);
    setRejected([]);
    setDone(0);
  };

  const run = async () => {
    pause.current = false;
    setRunning(true);
    const pending = items.slice(done);
    try {
      await importItems(
        pending,
        { source, license, faceFeatures, dominantHand: "right", mapping: MAPPING },
        (outcome) => {
          setDone((n) => n + 1);
          const accepted = outcome.sample;
          if (accepted) setSamples((previous) => [...previous, accepted]);
          else setRejected((previous) => [...previous, { item: outcome.item, reason: outcome.reason ?? "" }]);
        },
        () => pause.current,
      );
    } finally {
      setRunning(false);
    }
  };

  const reasons = countByLabel(rejected.map((r) => ({ label: r.reason })));
  const counts = countByLabel(samples);

  return (
    <AppLayout>
      <h1 className="font-display text-3xl font-extrabold">Importar dataset (gestos)</h1>
      <p className="mt-2 text-[#45606A]">
        Videos nombrados <code>etiqueta__persona__toma.mp4</code> o fotos <code>etiqueta__persona__toma-0001.jpg</code>.
        La etiqueta se traduce con <code>content/dataset-mapping.csv</code>; las señas que no están se ignoran. Se
        procesan en este navegador y no se suben.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <label className="flex flex-col font-semibold">
          Fuente
          <select
            value={source}
            onChange={(event) => {
              setSource(event.target.value);
              setLicense(LICENSES[event.target.value] ?? "");
            }}
            className="mt-1 rounded-xl border border-slate-300 bg-white px-3 py-2"
          >
            {SOURCES.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col font-semibold">
          Licencia
          <input value={license} onChange={(event) => setLicense(event.target.value)} className="mt-1 rounded-xl border border-slate-300 px-3 py-2" />
        </label>
      </div>
      <label className="mt-3 flex items-start gap-2">
        <input type="checkbox" checked={faceFeatures} onChange={(event) => setFaceFeatures(event.target.checked)} className="mt-1" />
        <span>Las caras se ven bien (si vienen pixeladas, déjalo sin marcar: no se usa la expresión facial).</span>
      </label>
      <label className="mt-3 block font-semibold">
        Archivos
        <input
          type="file"
          multiple
          accept="video/mp4,video/webm,image/jpeg,image/png,image/webp"
          disabled={running}
          onChange={(event) => choose(event.target.files)}
          className="mt-1 block"
        />
      </label>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={running || items.length === 0 || done >= items.length || !license.trim()}
          onClick={() => void run()}
          className="rounded-xl bg-[#047857] px-4 py-2 font-bold text-white disabled:opacity-60"
        >
          {done > 0 && done < items.length ? "Continuar" : "Procesar"}
        </button>
        <button
          type="button"
          disabled={!running}
          onClick={() => {
            pause.current = true;
          }}
          className="rounded-xl border border-slate-300 px-4 py-2 font-semibold disabled:opacity-50"
        >
          Pausar
        </button>
        <button
          type="button"
          disabled={samples.length === 0 || running}
          onClick={() => downloadJson(buildHolisticDataset(samples, faceFeatures), `dataset-${source.toLowerCase()}-holistic-v2.json`)}
          className="rounded-xl border border-[#047857] px-4 py-2 font-bold text-[#047857] disabled:opacity-50"
        >
          Exportar dataset.json
        </button>
      </div>
      <p role="status" className="mt-3 font-semibold">
        {items.length > 0
          ? `${done} de ${items.length} procesados · ${samples.length} aceptadas · ${rejected.length} descartadas${
              ignored.length ? ` · ${ignored.length} archivos con nombre inválido` : ""
            }`
          : ""}
      </p>
      {(counts.size > 0 || reasons.size > 0) && (
        <section className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl bg-white p-4 shadow">
            <h2 className="font-display text-lg font-extrabold">Aceptadas por seña</h2>
            <ul className="mt-2">
              {[...counts.entries()].map(([name, count]) => (
                <li key={name}>
                  {name}: {count}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl bg-white p-4 shadow">
            <h2 className="font-display text-lg font-extrabold">Descartadas y por qué</h2>
            <ul className="mt-2">
              {[...reasons.entries()].map(([reason, count]) => (
                <li key={reason}>
                  {reason}: {count}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </AppLayout>
  );
}
