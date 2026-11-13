import { useEffect, useState } from "react";
import { NONE, type Prediction } from "../../camera/classifier";
import type { RecordedSample } from "../../camera/holistic/gesture-session";
import { loadSequenceClassifier, type SequenceClassifier } from "../../camera/holistic/sequence-classifier";
import { Mascot } from "../../components/mascot/Mascot";
import { apiRequest } from "../../lib/api";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import { useSignSearch } from "../dictionary/dictionary-api";
import { GestureCamera } from "./GestureCamera";

const FACE_REQUIRED = { faceRequired: true } as const;
const FACE_OPTIONAL = { faceRequired: false } as const;

type Outcome = { kind: "recognized"; prediction: Prediction } | { kind: "none" } | { kind: "rejected"; reason: string };

/**
 * Práctica libre de señas con movimiento en Cámara beta (D-031): la misma cámara holística y el mismo
 * modelo de las lecciones, sin ejercicio. Solo reconoce las señas del modelo publicado.
 */
export function GesturePractice() {
  const user = useSessionStore((state) => state.user);
  const dominantHand = user?.dominantHand === "left" ? "left" : "right";
  const isAdmin = user?.role === "ADMIN";
  // Los nombres de las señas salen del diccionario (las del modelo son de saludos y cortesía).
  const greetings = useSignSearch("", "saludos", 1);
  const courtesy = useSignSearch("", "cortesia", 1);
  const [model, setModel] = useState<SequenceClassifier | null | undefined>(undefined);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  // D-045: el modo de 2 s sigue siendo el predeterminado mientras se evalúa el manual.
  const [manual, setManual] = useState(false);

  useEffect(() => {
    let active = true;
    const pending = loadSequenceClassifier();
    void pending.then((loaded) => {
      if (active) setModel(loaded);
    });
    return () => {
      active = false;
      void pending.then((loaded) => loaded?.dispose()); // la memoria de tfjs se libera al salir
    };
  }, []);

  const words = new Map(
    [...(greetings.data?.items ?? []), ...(courtesy.data?.items ?? [])].map((sign) => [sign.slug, sign.word]),
  );
  const wordOf = (slug: string) => words.get(slug) ?? slug;

  if (model === undefined) {
    return (
      <p role="status" className="mt-4 font-semibold text-[#45606A]">
        Preparando el reconocimiento…
      </p>
    );
  }
  if (model === null) {
    return (
      <p role="status" className="mt-4 rounded-xl bg-amber-50 p-3 text-amber-900">
        El modelo de señas con movimiento aún no está disponible. Usa la pestaña «Alfabeto y números».
      </p>
    );
  }

  const known = model.labels.filter((label) => label !== NONE);

  const onSample = (sample: RecordedSample) => {
    if (!sample.check.ok) {
      setOutcome({ kind: "rejected", reason: sample.check.reason });
      return;
    }
    const prediction = model.classify(sample.frames);
    if (prediction.label === NONE) {
      setOutcome({ kind: "none" });
      return;
    }
    setOutcome({ kind: "recognized", prediction });
    // Solo números al servidor (R8.3): suma para «Ojo de colibrí», como el alfabeto.
    const body: components["schemas"]["RecognitionIn"] = {
      signId: prediction.label,
      correct: true,
      confidence: prediction.confidence,
    };
    void apiRequest("POST", "/recognition/results", { body }).catch(() => undefined);
  };

  const tomi =
    outcome?.kind === "recognized"
      ? `¡Eso es «${wordOf(outcome.prediction.label)}»!`
      : outcome?.kind === "none"
        ? manual
          ? "No reconocí ninguna de las señas que conozco. Prueba una de la lista, completa, y pulsa «Terminar» al acabar."
          : "No reconocí ninguna de las señas que conozco. Prueba una de la lista, completa y en 2 segundos."
        : outcome?.kind === "rejected"
          ? `${outcome.reason} Inténtalo otra vez.`
          : manual
            ? "Pulsa «Hacer la seña»: cuento 3, 2, 1, haces la seña a tu ritmo y pulsas «Terminar» (máximo 4 segundos)."
            : "Pulsa «Hacer la seña»: cuento 3, 2, 1 y miro 2 segundos.";

  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-2xl bg-white p-4 shadow">
        <p className="font-semibold">
          Esta cámara conoce {known.length} señas. Si haces otra, te dirá que no la reconoce.
        </p>
        <ul aria-label="Señas que reconoce" className="mt-2 flex flex-wrap gap-2">
          {known.map((label) => (
            <li key={label} className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-semibold">
              {wordOf(label)}
            </li>
          ))}
        </ul>
      </div>
      <fieldset className="rounded-2xl bg-white p-4 shadow">
        <legend className="sr-only">Cómo grabar</legend>
        <p className="font-semibold">Cómo grabar</p>
        <div className="mt-2 flex flex-wrap gap-4">
          <label className="flex items-center gap-2">
            <input type="radio" name="modo-captura" checked={!manual} onChange={() => setManual(false)} />
            2 segundos (automático)
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name="modo-captura" checked={manual} onChange={() => setManual(true)} />
            Yo marco el inicio y el fin (máximo 4 s)
          </label>
        </div>
      </fieldset>
      <GestureCamera
        manual={manual}
        dominantHand={dominantHand}
        requireFace={model.meta.faceFeatures}
        quality={model.meta.faceFeatures ? FACE_REQUIRED : FACE_OPTIONAL}
        onSample={onSample}
        recordText="Hacer la seña"
        showStats={isAdmin}
      />
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[#45606A]">Seña detectada</p>
          <p aria-live="polite" className="font-display text-4xl font-extrabold">
            {outcome?.kind === "recognized" ? wordOf(outcome.prediction.label) : "—"}
          </p>
          {outcome?.kind === "recognized" && (
            <p className="font-semibold">Confianza: {Math.floor(outcome.prediction.confidence * 100)} %</p>
          )}
        </div>
        <Mascot mood={outcome?.kind === "recognized" ? "cheer" : "thinking"} message={tomi} />
      </div>
    </div>
  );
}
