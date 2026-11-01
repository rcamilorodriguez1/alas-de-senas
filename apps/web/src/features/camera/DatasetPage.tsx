import { useCallback, useEffect, useRef, useState } from "react";
import { AppLayout } from "../../components/layout/AppLayout";
import { buildDataset, countByLabel, downloadDataset, NONE_LABEL, type Sample } from "../../camera/dataset";
import {
  CAMERA_ERRORS,
  cameraErrorKind,
  displayLabel,
  startCameraSession,
  type CameraErrorKind,
  type CameraSession,
} from "../../camera/session";
import { useSessionStore } from "../../lib/session-store";
import { useSignSearch } from "../dictionary/dictionary-api";

const COUNTDOWN_S = 3;
const RECORD_MS = 10_000;
const SAMPLE_EVERY_MS = 100; // ~10 muestras por segundo (§10.5)

type Phase = { kind: "idle" } | { kind: "countdown"; left: number } | { kind: "recording"; until: number };

/** Colector de muestras `/admin/dataset` (§10.5): solo ADMIN, exporta `dataset.json`. */
export function DatasetPage() {
  const isAdmin = useSessionStore((state) => state.user?.role === "ADMIN");
  const letters = useSignSearch("", "alfabeto", 1);
  const video = useRef<HTMLVideoElement>(null);
  const session = useRef<CameraSession | null>(null);
  const phaseRef = useRef<Phase>({ kind: "idle" });
  const lastSample = useRef(0);
  const labelRef = useRef(NONE_LABEL);
  const [phase, setPhaseState] = useState<Phase>({ kind: "idle" });
  const [label, setLabel] = useState(NONE_LABEL);
  const [collector, setCollector] = useState("");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [cameraOn, setCameraOn] = useState(false);
  const [error, setError] = useState<CameraErrorKind | null>(null);

  const setPhase = (next: Phase) => {
    phaseRef.current = next;
    setPhaseState(next);
  };
  useEffect(() => {
    labelRef.current = label; // el bucle de la cámara lee la etiqueta actual
  }, [label]);

  const stop = useCallback(() => {
    session.current?.stop();
    session.current = null;
    setCameraOn(false);
  }, []);
  useEffect(() => stop, [stop]);

  const turnOn = async () => {
    if (!video.current) return;
    setError(null);
    try {
      session.current = await startCameraSession(video.current, ({ features }) => {
        const current = phaseRef.current;
        if (current.kind !== "recording" || !features) return;
        const now = performance.now();
        if (now >= current.until) {
          setPhase({ kind: "idle" });
          return;
        }
        if (now - lastSample.current < SAMPLE_EVERY_MS) return;
        lastSample.current = now;
        setSamples((previous) => [...previous, { label: labelRef.current, features }]);
      });
      setCameraOn(true);
    } catch (caught) {
      setError(cameraErrorKind(caught));
    }
  };

  // Cuenta regresiva de 3 s y luego 10 s de grabación.
  useEffect(() => {
    if (phase.kind !== "countdown") return;
    const timer = window.setTimeout(() => {
      if (phase.left > 1) setPhase({ kind: "countdown", left: phase.left - 1 });
      else setPhase({ kind: "recording", until: performance.now() + RECORD_MS });
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [phase]);

  if (!isAdmin) {
    return (
      <AppLayout>
        <h1 className="font-display text-3xl font-extrabold">Colector de muestras</h1>
        <p role="alert" className="mt-4">
          Esta página es solo para administradores.
        </p>
      </AppLayout>
    );
  }

  const counts = countByLabel(samples);
  const options = [NONE_LABEL, ...(letters.data?.items.map((sign) => sign.slug) ?? [])];

  return (
    <AppLayout>
      <h1 className="font-display text-3xl font-extrabold">Colector de muestras</h1>
      <p className="mt-2 text-[#45606A]">
        Solo se guardan los 63 números de la mano (nunca imágenes). Graba solo letras estáticas confirmadas por el
        intérprete; el entrenamiento rechaza las de movimiento.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <label className="flex flex-col font-semibold">
          Alias de quien graba
          <input
            value={collector}
            onChange={(event) => setCollector(event.target.value)}
            maxLength={40}
            className="mt-1 rounded-xl border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="flex flex-col font-semibold">
          Etiqueta
          <select
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            className="mt-1 rounded-xl border border-slate-300 bg-white px-3 py-2"
          >
            {options.map((slug) => (
              <option key={slug} value={slug}>
                {slug === NONE_LABEL ? "NINGUNA (sin seña)" : `${displayLabel(slug)} (${slug})`}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="relative mt-4 overflow-hidden rounded-2xl bg-[#0E2A2F]" style={{ aspectRatio: "4 / 3" }}>
        <video ref={video} muted playsInline aria-label="Vista de tu cámara" className="h-full w-full -scale-x-100" />
        {phase.kind !== "idle" && (
          <p
            role="status"
            className="absolute top-3 left-3 rounded-xl bg-white/90 px-3 py-1 font-display text-xl font-extrabold"
          >
            {phase.kind === "countdown" ? `Prepárate: ${phase.left}` : "Grabando…"}
          </p>
        )}
      </div>
      {error && (
        <p role="alert" className="mt-3 rounded-xl bg-red-50 p-3 text-red-800">
          {CAMERA_ERRORS[error]}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        {!cameraOn ? (
          <button type="button" onClick={() => void turnOn()} className="rounded-xl bg-[#047857] px-4 py-2 font-bold text-white">
            Activar cámara
          </button>
        ) : (
          <button
            type="button"
            disabled={phase.kind !== "idle"}
            onClick={() => setPhase({ kind: "countdown", left: COUNTDOWN_S })}
            className="rounded-xl bg-[#047857] px-4 py-2 font-bold text-white disabled:opacity-60"
          >
            Grabar 10 s
          </button>
        )}
        <button
          type="button"
          disabled={samples.length === 0 || !collector.trim()}
          onClick={() => downloadDataset(buildDataset(collector, samples))}
          className="rounded-xl border border-[#047857] px-4 py-2 font-bold text-[#047857] disabled:opacity-50"
        >
          Exportar dataset.json
        </button>
      </div>
      <section aria-labelledby="conteo" className="mt-6 rounded-2xl bg-white p-4 shadow">
        <h2 id="conteo" className="font-display text-xl font-extrabold">
          Muestras por clase ({samples.length})
        </h2>
        {counts.size === 0 ? (
          <p className="mt-2 text-[#45606A]">Aún no hay muestras.</p>
        ) : (
          <ul className="mt-2 grid grid-cols-3 gap-2">
            {[...counts.entries()].map(([name, count]) => (
              <li key={name} className="rounded-xl bg-slate-50 px-3 py-1 font-semibold">
                {name === NONE_LABEL ? NONE_LABEL : displayLabel(name)}: {count}
              </li>
            ))}
          </ul>
        )}
      </section>
    </AppLayout>
  );
}
