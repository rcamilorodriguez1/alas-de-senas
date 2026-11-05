import { withEquivalents } from "../../camera/equivalences";
import { HAND_CONNECTIONS } from "../../camera/hand-connections";
import type { Point2 } from "../../camera/recognizer";
import { Camera, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppLayout } from "../../components/layout/AppLayout";
import { Mascot } from "../../components/mascot/Mascot";
import { apiRequest } from "../../lib/api";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import type { Prediction } from "../../camera/classifier";
import {
  CAMERA_ERRORS,
  cameraErrorKind,
  displayLabel,
  startCameraSession,
  type CameraErrorKind,
  type CameraSession,
} from "../../camera/session";
import { StatsPanel } from "../gamification/StatsPanel";

const REPORT_EVERY_MS = 10_000; // el servidor tampoco cuenta la misma seña antes de 10 s

/** Solo números al servidor (R8.3): la seña, si fue correcta y la confianza. */
function reportRecognition(signId: string, confidence: number) {
  const body: components["schemas"]["RecognitionIn"] = { signId, correct: true, confidence };
  void apiRequest("POST", "/recognition/results", { body }).catch(() => undefined);
}


function drawHand(canvas: HTMLCanvasElement, points: readonly Point2[] | null) {
  const context = canvas.getContext("2d");
  if (!context) return;
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!points) return;
  context.strokeStyle = "#10B981";
  context.lineWidth = 3;
  for (const [a, b] of HAND_CONNECTIONS) {
    context.beginPath();
    context.moveTo(points[a].x * canvas.width, points[a].y * canvas.height);
    context.lineTo(points[b].x * canvas.width, points[b].y * canvas.height);
    context.stroke();
  }
  context.fillStyle = "#F59E0B";
  for (const point of points) {
    context.beginPath();
    context.arc(point.x * canvas.width, point.y * canvas.height, 4, 0, Math.PI * 2);
    context.fill();
  }
}

/** Autoevaluación cuando no hay cámara (R8.4): sin puntaje, solo para practicar. */
function SelfCheck() {
  const [answer, setAnswer] = useState<string | null>(null);
  return (
    <div className="mt-3 rounded-xl bg-emerald-50 p-3">
      <p className="font-semibold">Practica con autoevaluación: haz la seña frente a un espejo.</p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={() => setAnswer("¡Muy bien! Sigue así.")}
          className="rounded-xl bg-[#047857] px-4 py-2 font-bold text-white"
        >
          Sí, me salió
        </button>
        <button
          type="button"
          onClick={() => setAnswer("Mírala otra vez en el diccionario y vuelve a intentarlo.")}
          className="rounded-xl border border-[#047857] px-4 py-2 font-bold text-[#047857]"
        >
          Necesito repasar
        </button>
      </div>
      <p role="status" className="mt-2 font-semibold">
        {answer}
      </p>
    </div>
  );
}

/** Cámara beta (R8): video en espejo, puntos de la mano, seña detectada y confianza. */
export function CameraPage() {
  const isAdmin = useSessionStore((state) => state.user?.role === "ADMIN");
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const session = useRef<CameraSession | null>(null);
  const [state, setState] = useState<"off" | "starting" | "on">("off");
  const [error, setError] = useState<CameraErrorKind | null>(null);
  const [detected, setDetected] = useState<Prediction | null>(null);
  const [handVisible, setHandVisible] = useState(false);
  const [simulated, setSimulated] = useState(false);
  const reported = useRef(new Map<string, number>());
  const mounted = useRef(true);
  const lastShown = useRef("");

  // Cada seña detectada suma para «Ojo de colibrí» (máximo una vez cada 10 s).
  useEffect(() => {
    if (!detected || simulated) return;
    const now = Date.now();
    const last = reported.current.get(detected.label) ?? 0;
    if (now - last < REPORT_EVERY_MS) return;
    reported.current.set(detected.label, now);
    reportRecognition(detected.label, detected.confidence);
  }, [detected, simulated]);

  const stop = useCallback(() => {
    session.current?.stop();
    session.current = null;
    setState("off");
    setDetected(null);
    setHandVisible(false);
  }, []);

  // R8.5: al salir de la pantalla la cámara se apaga (también si aún se estaba encendiendo).
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      stop();
    };
  }, [stop]);

  const start = async () => {
    if (!video.current) return;
    setError(null);
    setState("starting");
    try {
      const started = await startCameraSession(video.current, ({ points, detected: found }) => {
        if (canvas.current) drawHand(canvas.current, points);
        setHandVisible(points !== null);
        // Solo re-renderiza si cambia la etiqueta o el porcentaje mostrado (no 60 veces por segundo).
        const key = found ? `${found.label}:${Math.floor(found.confidence * 100)}` : "";
        if (key !== lastShown.current) {
          lastShown.current = key;
          setDetected(found);
        }
      });
      if (!mounted.current) {
        started.stop(); // salió mientras se encendía: B40, R8.5
        return;
      }
      session.current = started;
      setSimulated(started.classifier.simulated);
      setState("on");
    } catch (caught) {
      if (!mounted.current) return;
      setError(cameraErrorKind(caught));
      setState("off");
    }
  };

  // Señas con la misma forma (D-027): sin contexto se muestran las dos, p. ej. «B / 4».
  const shown = detected ? withEquivalents(detected.label).map(displayLabel).join(" / ") : null;
  const tomi = shown
    ? `¡Eso es una «${shown}»!`
    : handVisible
      ? "Mantén la mano quieta frente a la cámara."
      : "Acerca la mano a la cámara para empezar.";

  return (
    <AppLayout aside={<StatsPanel />}>
      <h1 className="font-display text-3xl font-extrabold">Cámara beta</h1>
      <p className="mt-2 inline-flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2 font-semibold text-[#047857]">
        <ShieldCheck aria-hidden="true" size={18} />
        Tu video no sale de tu dispositivo
      </p>
      {simulated && isAdmin && (
        <p role="status" className="mt-3 rounded-xl bg-amber-50 p-3 text-amber-900">
          Modelo en entrenamiento: por ahora solo se dibujan los puntos de la mano.
        </p>
      )}
      <div className="relative mt-4 overflow-hidden rounded-2xl bg-[#0E2A2F]" style={{ aspectRatio: "4 / 3" }}>
        {/* Vista espejo solo con CSS; los puntos se dibujan con el mismo reflejo (§10.4). */}
        <video
          ref={video}
          muted
          playsInline
          aria-label="Vista de tu cámara"
          className="h-full w-full -scale-x-100 object-cover"
        />
        <canvas
          ref={canvas}
          width={640}
          height={480}
          aria-hidden="true"
          className="absolute inset-0 h-full w-full -scale-x-100"
        />
        {state !== "on" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <button
              type="button"
              onClick={() => void start()}
              disabled={state === "starting"}
              className="inline-flex items-center gap-2 rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-5 py-3 font-display font-bold text-white disabled:opacity-60"
            >
              <Camera aria-hidden="true" size={20} />
              {state === "starting" ? "Encendiendo…" : "Activar cámara"}
            </button>
          </div>
        )}
      </div>
      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-red-800">
          <p className="font-semibold">{CAMERA_ERRORS[error]}</p>
          <SelfCheck />
        </div>
      )}
      {state === "on" && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-[#45606A]">Seña detectada</p>
            {/* Solo la letra se anuncia; la confianza cambia muy seguido. */}
            <p aria-live="polite" className="font-display text-4xl font-extrabold">
              {shown ?? "—"}
            </p>
            {detected && (
              <p className="font-semibold">Confianza: {Math.floor(detected.confidence * 100)} %</p>
            )}
          </div>
          <Mascot mood={detected ? "cheer" : "thinking"} message={tomi} />
          <button
            type="button"
            onClick={stop}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2 font-semibold"
          >
            Apagar cámara
          </button>
        </div>
      )}
    </AppLayout>
  );
}
