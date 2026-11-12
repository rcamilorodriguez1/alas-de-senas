import { Link } from "react-router";
import { FolderOpen, Upload } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import mappingCsv from "../../../../../content/dataset-mapping.csv?raw";
import { AppLayout } from "../../components/layout/AppLayout";
import { buildHolisticDataset, countByLabel, downloadJson, type HolisticSample } from "../../camera/holistic/dataset-v2";
import { DATASETS, licenseFor } from "../../camera/holistic/datasets";
import { planImport, type ImportPlan, type SavedOutcome } from "../../camera/holistic/import-plan";
import { progressStore, type SavedProgress } from "../../camera/holistic/import-progress";
import { groupFiles, importItems, parseMapping } from "../../camera/holistic/importer";
import { useSessionStore } from "../../lib/session-store";

const MAPPING = parseMapping(mappingCsv);
// Solo las fuentes que tienen mapeo y licencia registrada en content/datasets.csv (D-044).
const SOURCES = DATASETS.map((d) => d.source).filter((source) => MAPPING.some((row) => row.source === source));
const MEDIA = /\.(mp4|webm|mov|m4v|jpe?g|png|webp)$/i;
const BUTTON =
  "inline-flex items-center gap-2 rounded-xl border-b-4 px-5 py-3 font-display font-bold disabled:cursor-not-allowed disabled:opacity-50";

/** Importador `/admin/importar` (anexo A.7.1, D-044): datasets externos con el mismo pipeline del navegador. */
export function ImportPage() {
  const isAdmin = useSessionStore((state) => state.user?.role === "ADMIN");
  const [source, setSource] = useState(SOURCES[0] ?? "");
  const [faceFeatures, setFaceFeatures] = useState(false);
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [chosen, setChosen] = useState({ files: 0, invalid: 0 });
  const [samples, setSamples] = useState<HolisticSample[]>([]);
  const [rejected, setRejected] = useState<{ item: string; reason: string }[]>([]);
  const [done, setDone] = useState(0);
  const [running, setRunning] = useState(false);
  const [saved, setSaved] = useState<SavedProgress | null>(null);
  const [dragging, setDragging] = useState(false);
  const pause = useRef(false);
  const processed = useRef(new Set<string>());
  const filesInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const license = licenseFor(source);

  // Al salir de la página se detiene el lote (y se liberan los detectores de MediaPipe).
  useEffect(
    () => () => {
      pause.current = true;
    },
    [],
  );

  // ¿Quedó una importación sin terminar (se apagó el equipo o se cerró la pestaña)?
  useEffect(() => {
    let active = true;
    progressStore
      .load()
      .then((progress) => {
        if (!active || !progress) return;
        setSaved(progress);
        if (SOURCES.includes(progress.session.source)) setSource(progress.session.source);
        setFaceFeatures(progress.session.faceFeatures);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  // «Elegir carpeta»: el atributo no existe en los tipos de React; se pone directo en el elemento.
  useEffect(() => {
    folderInput.current?.setAttribute("webkitdirectory", "");
    folderInput.current?.setAttribute("directory", "");
  });

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

  const choose = (selection: readonly File[]) => {
    const media = selection.filter((file) => MEDIA.test(file.name));
    const grouped = groupFiles(media);
    const previous: readonly SavedOutcome[] = saved?.session.source === source ? saved.outcomes : [];
    const next = planImport(grouped.items, source, MAPPING, previous);
    processed.current = new Set(next.restored.map((outcome) => outcome.item));
    setPlan(next);
    setChosen({ files: media.length, invalid: grouped.ignored.length });
    setSamples(next.restored.flatMap((outcome) => (outcome.sample ? [outcome.sample] : [])));
    setRejected(
      next.restored.flatMap((outcome) => (outcome.sample ? [] : [{ item: outcome.item, reason: outcome.reason ?? "" }])),
    );
    setDone(next.restored.length);
    if (next.restored.length === 0 && next.importable.length > 0) {
      // Importación nueva: lo guardado antes ya no aplica.
      const session = { source, license, faceFeatures, total: next.importable.length };
      setSaved({ session, outcomes: [] });
      void progressStore.start(session).catch(() => undefined);
    }
  };

  const run = async () => {
    if (!plan) return;
    pause.current = false;
    setRunning(true);
    const pending = plan.importable.filter((item) => !processed.current.has(item.key));
    try {
      await importItems(
        pending,
        { source, license, faceFeatures, dominantHand: "right", mapping: MAPPING },
        (outcome) => {
          processed.current.add(outcome.item);
          setDone((n) => n + 1);
          const accepted = outcome.sample;
          if (accepted) setSamples((previous) => [...previous, accepted]);
          else setRejected((previous) => [...previous, { item: outcome.item, reason: outcome.reason ?? "" }]);
          void progressStore.add(outcome).catch(() => undefined);
        },
        () => pause.current,
      );
    } finally {
      setRunning(false);
    }
  };

  const discard = () => {
    void progressStore.clear().catch(() => undefined);
    setSaved(null);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!running) choose([...event.dataTransfer.files]);
  };

  const total = plan?.importable.length ?? 0;
  const reasons = countByLabel(rejected.map((r) => ({ label: r.reason })));
  const counts = countByLabel(samples);
  const summary = plan
    ? [
        `${chosen.files} archivos`,
        `${total} se importarán`,
        `${plan.outsideMapping.length} fuera del mapeo`,
        ...(chosen.invalid ? [`${chosen.invalid} con nombre inválido`] : []),
        ...(plan.restored.length ? [`${plan.restored.length} ya procesados`] : []),
      ].join(" · ")
    : null;

  return (
    <AppLayout>
      <Link to="/admin" className="text-sm font-semibold text-[#047857] underline">
        ← Administración
      </Link>
      <h1 className="font-display text-3xl font-extrabold">Importar dataset (gestos)</h1>
      <p className="mt-2 text-[#45606A]">
        Videos nombrados <code>etiqueta__persona__toma.mp4</code> o fotos <code>etiqueta__persona__toma-0001.jpg</code>.
        La etiqueta se traduce con <code>content/dataset-mapping.csv</code>; las señas que no están se ignoran. Se
        procesan en este navegador y no se suben.
      </p>

      {saved && !plan && saved.outcomes.length > 0 && (
        <div role="status" className="mt-4 rounded-2xl bg-amber-50 p-4 text-amber-950">
          <p className="font-semibold">
            Tienes una importación sin terminar: {saved.outcomes.length} de {saved.session.total} procesados (
            {saved.session.source}).
          </p>
          <p className="mt-1">Vuelve a elegir los mismos archivos o la misma carpeta para continuar donde ibas.</p>
          <button
            type="button"
            onClick={discard}
            className="mt-2 rounded-xl border border-amber-800 px-3 py-1.5 text-sm font-semibold"
          >
            Descartar progreso
          </button>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-3">
        <label className="flex flex-col font-semibold">
          Fuente
          <select
            value={source}
            disabled={running}
            onChange={(event) => {
              setSource(event.target.value);
              setPlan(null);
            }}
            className="mt-1 rounded-xl border border-slate-300 bg-white px-3 py-2"
          >
            {SOURCES.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <div className="flex flex-col font-semibold">
          Licencia
          <span className="mt-1 rounded-xl bg-slate-100 px-3 py-2 font-normal">
            {license || "Sin licencia: regístrala en content/datasets.csv"}
          </span>
        </div>
      </div>
      <label className="mt-3 flex items-start gap-2">
        <input
          type="checkbox"
          checked={faceFeatures}
          disabled={running}
          onChange={(event) => setFaceFeatures(event.target.checked)}
          className="mt-1"
        />
        <span>Las caras se ven bien (si vienen pixeladas, déjalo sin marcar: no se usa la expresión facial).</span>
      </label>

      <div
        data-testid="zona-soltar"
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`mt-4 rounded-2xl border-2 border-dashed p-6 text-center transition-colors ${
          dragging ? "border-[#047857] bg-emerald-50" : "border-slate-300 bg-white"
        }`}
      >
        <div className="flex flex-wrap justify-center gap-3">
          <button
            type="button"
            disabled={running}
            onClick={() => filesInput.current?.click()}
            className={`${BUTTON} border-emerald-950 bg-[#047857] text-white`}
          >
            <Upload aria-hidden="true" size={20} />
            Elegir archivos
          </button>
          <button
            type="button"
            disabled={running}
            onClick={() => folderInput.current?.click()}
            className={`${BUTTON} border-slate-400 bg-white text-[#0E2A2F]`}
          >
            <FolderOpen aria-hidden="true" size={20} />
            Elegir carpeta
          </button>
        </div>
        <p className="mt-3 text-sm text-[#45606A]">…o arrastra aquí los videos o las fotos.</p>
        <input
          ref={filesInput}
          data-testid="elegir-archivos"
          type="file"
          multiple
          accept="video/mp4,video/webm,video/quicktime,image/jpeg,image/png,image/webp"
          tabIndex={-1}
          aria-hidden="true"
          className="sr-only"
          onChange={(event) => {
            choose(event.target.files ? [...event.target.files] : []);
            event.target.value = ""; // permite volver a elegir lo mismo
          }}
        />
        <input
          ref={folderInput}
          data-testid="elegir-carpeta"
          type="file"
          multiple
          tabIndex={-1}
          aria-hidden="true"
          className="sr-only"
          onChange={(event) => {
            choose(event.target.files ? [...event.target.files] : []);
            event.target.value = "";
          }}
        />
      </div>
      {summary && <p className="mt-3 font-semibold">{summary}</p>}

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={running || total === 0 || done >= total || !license}
          onClick={() => void run()}
          className="rounded-xl bg-[#047857] px-4 py-2 font-bold text-white disabled:opacity-60"
        >
          {done > 0 && done < total ? "Continuar" : "Procesar"}
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
        {plan ? `${done} de ${total} procesados · ${samples.length} aceptadas · ${rejected.length} descartadas` : ""}
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
