import { Link } from "react-router";
import { useMemo, useRef, useState } from "react";
import { AppLayout } from "../../components/layout/AppLayout";
import { NONE } from "../../camera/classifier";
import { buildHolisticDataset, countByLabel, downloadJson, makeSample, type HolisticSample } from "../../camera/holistic/dataset-v2";
import type { RecordedSample } from "../../camera/holistic/gesture-session";
import { useSessionStore } from "../../lib/session-store";
import { useSignSearch } from "../dictionary/dictionary-api";
import { GestureCamera } from "./GestureCamera";

const LICENSE = "propio-con-autorizacion";

/** Colector `holistic-v2` `/admin/gestos` (anexo A.6, 10B.6): cuenta regresiva, 2 s, alias y autorización. */
export function GestureDatasetPage() {
  const user = useSessionStore((state) => state.user);
  const greetings = useSignSearch("", "saludos", 1);
  const courtesy = useSignSearch("", "cortesia", 1);
  const [label, setLabel] = useState(NONE);
  const [collector, setCollector] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [samples, setSamples] = useState<HolisticSample[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const labelAtStart = useRef(NONE); // la etiqueta se fija al pulsar «Grabar», no al terminar
  const quality = useMemo(() => ({ handRequired: label !== NONE }), [label]);

  if (user?.role !== "ADMIN") {
    return (
      <AppLayout>
        <h1 className="font-display text-3xl font-extrabold">Colector de gestos</h1>
        <p role="alert" className="mt-4">
          Esta página es solo para administradores.
        </p>
      </AppLayout>
    );
  }

  const options = [
    NONE,
    ...[...(greetings.data?.items ?? []), ...(courtesy.data?.items ?? [])].map((sign) => sign.slug),
  ];
  const dominantHand = user.dominantHand === "left" ? "left" : "right";
  const canRecord = authorized && collector.trim().length > 0;

  const onSample = (recorded: RecordedSample) => {
    if (!recorded.check.ok) {
      setNote(`Muestra descartada: ${recorded.check.reason}`);
      return;
    }
    const recordedLabel = labelAtStart.current;
    const sample = makeSample({
      label: recordedLabel,
      collector,
      dominantHand,
      source: "propio",
      license: LICENSE,
      quality: recorded.quality,
      frames: recorded.frames,
    });
    setSamples((previous) => [...previous, sample]);
    setNote(`Muestra de «${recordedLabel}» guardada.`);
  };

  const counts = countByLabel(samples);

  return (
    <AppLayout>
      <Link to="/admin" className="text-sm font-semibold text-[#047857] underline">
        ← Administración
      </Link>
      <h1 className="font-display text-3xl font-extrabold">Colector de gestos</h1>
      <p className="mt-2 text-[#45606A]">
        Cada muestra son 2 s después de «3, 2, 1». Solo se guardan números: la forma y la posición de las manos y 18
        valores de expresión facial. Nunca la imagen ni la malla de la cara.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <label className="flex flex-col font-semibold">
          Alias de quien graba
          <input
            value={collector}
            onChange={(event) => setCollector(event.target.value)}
            maxLength={40}
            placeholder="persona-03"
            className="mt-1 rounded-xl border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="flex flex-col font-semibold">
          Seña
          <select
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            className="mt-1 rounded-xl border border-slate-300 bg-white px-3 py-2"
          >
            {options.map((slug) => (
              <option key={slug} value={slug}>
                {slug === NONE ? "NINGUNA (manos quietas u otra cosa)" : slug}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="mt-3 flex items-start gap-2">
        <input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} className="mt-1" />
        <span>La persona que graba firmó la autorización de uso de sus datos y se identifica solo con un alias.</span>
      </label>
      <div className="mt-4">
        <GestureCamera
          dominantHand={dominantHand}
          quality={quality}
          onRecordStart={() => {
            labelAtStart.current = label;
          }}
          onSample={onSample}
          showStats
          recordText="Grabar muestra (2 s)"
          disabled={!canRecord}
        />
      </div>
      <p role="status" className="mt-2 font-semibold">
        {note ?? ""}
      </p>
      <section aria-labelledby="conteo-gestos" className="mt-6 rounded-2xl bg-white p-4 shadow">
        <h2 id="conteo-gestos" className="font-display text-xl font-extrabold">
          Muestras por seña ({samples.length})
        </h2>
        {counts.size === 0 ? (
          <p className="mt-2 text-[#45606A]">Aún no hay muestras.</p>
        ) : (
          <ul className="mt-2 grid grid-cols-3 gap-2">
            {[...counts.entries()].map(([name, count]) => (
              <li key={name} className="rounded-xl bg-slate-50 px-3 py-1 font-semibold">
                {name}: {count}
              </li>
            ))}
          </ul>
        )}
        <button
          type="button"
          disabled={samples.length === 0}
          onClick={() => downloadJson(buildHolisticDataset(samples, true), "dataset-holistic-v2.json")}
          className="mt-3 rounded-xl border border-[#047857] px-4 py-2 font-bold text-[#047857] disabled:opacity-50"
        >
          Exportar dataset.json
        </button>
      </section>
    </AppLayout>
  );
}
