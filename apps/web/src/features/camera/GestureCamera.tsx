import { useEffect, useRef, useState } from "react";
import { HAND_CONNECTIONS } from "../../camera/hand-connections";
import type { DominantHand } from "../../camera/holistic/frame";
import { startGestureSession, type GestureFrame, type GestureSession, type RecordedSample } from "../../camera/holistic/gesture-session";
import type { QualityOptions } from "../../camera/holistic/sequencer";
import type { Overlay, Point2 } from "../../camera/recognizer";
import { CAMERA_ERRORS, cameraErrorKind, type CameraErrorKind } from "../../camera/session";

export const COUNTDOWN_S = 3;
export const PRIVACY_NOTICE =
  "Usaremos la cámara para ver tus manos y tu expresión facial. El análisis ocurre en tu computador; no guardamos ni enviamos tu imagen.";

type Phase = { kind: "off" } | { kind: "starting" } | { kind: "ready" } | { kind: "countdown"; left: number } | { kind: "recording" };

function drawPoints(context: CanvasRenderingContext2D, points: readonly Point2[], w: number, h: number, color: string) {
  context.strokeStyle = color;
  context.fillStyle = color;
  context.lineWidth = 2;
  if (points.length === 21) {
    for (const [a, b] of HAND_CONNECTIONS) {
      context.beginPath();
      context.moveTo(points[a].x * w, points[a].y * h);
      context.lineTo(points[b].x * w, points[b].y * h);
      context.stroke();
    }
  }
  for (const p of points) {
    context.beginPath();
    context.arc(p.x * w, p.y * h, 3, 0, Math.PI * 2);
    context.fill();
  }
}

/** Manos (dominante verde, otra naranja), hombros y contorno de la cara; nunca la malla completa (A.5). */
function drawOverlay(canvas: HTMLCanvasElement, overlay: Overlay | null) {
  const context = canvas.getContext("2d");
  if (!context) return;
  const { width: w, height: h } = canvas;
  context.clearRect(0, 0, w, h);
  if (!overlay) return;
  if (overlay.face.length) {
    context.strokeStyle = "rgba(255,255,255,0.7)";
    context.lineWidth = 2;
    context.beginPath();
    overlay.face.forEach((p, i) => (i === 0 ? context.moveTo(p.x * w, p.y * h) : context.lineTo(p.x * w, p.y * h)));
    context.closePath();
    context.stroke();
  }
  drawPoints(context, overlay.shoulders, w, h, "#38BDF8");
  if (overlay.other) drawPoints(context, overlay.other, w, h, "#F59E0B");
  if (overlay.dominant) drawPoints(context, overlay.dominant, w, h, "#34D399");
}

export interface GestureCameraProps {
  dominantHand: DominantHand;
  quality?: QualityOptions;
  /** Se llama con cada grabación de 2 s (aceptada o no por el control de calidad). */
  onSample: (sample: RecordedSample) => void;
  showStats?: boolean;
  recordText?: string;
  disabled?: boolean;
  /** false si el modelo no usa la cara (entrenado con caras pixeladas): no se exige verla. */
  requireFace?: boolean;
  /** Se llama al pulsar «Grabar» (p. ej. para fijar la etiqueta de la muestra en ese momento). */
  onRecordStart?: () => void;
}

/** Cámara holística con guía visual, cuenta regresiva «3, 2, 1… ¡haz la seña!» y grabación de 2 s. */
export function GestureCamera({
  dominantHand,
  quality,
  onSample,
  showStats = false,
  recordText = "Grabar",
  disabled,
  requireFace = true,
  onRecordStart,
}: GestureCameraProps) {
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const session = useRef<GestureSession | null>(null);
  const mounted = useRef(true);
  const onSampleRef = useRef(onSample);
  // En una ref: un objeto `quality` nuevo en cada render del padre no reinicia la cuenta regresiva.
  const qualityRef = useRef(quality);
  useEffect(() => {
    onSampleRef.current = onSample;
    qualityRef.current = quality;
  }, [onSample, quality]);
  const [phase, setPhase] = useState<Phase>({ kind: "off" });
  const [frame, setFrame] = useState<Pick<GestureFrame, "guidance" | "ready" | "fps" | "extractMs">>({
    guidance: [],
    ready: false,
    fps: 0,
    extractMs: 0,
  });
  const [error, setError] = useState<CameraErrorKind | null>(null);
  const lastUi = useRef(0);

  useEffect(() => {
    mounted.current = true;
    // R8.5: la cámara se apaga al salir.
    return () => {
      mounted.current = false;
      session.current?.stop();
      session.current = null;
    };
  }, []);

  const turnOn = async () => {
    if (!video.current) return;
    setError(null);
    setPhase({ kind: "starting" });
    try {
      const started = await startGestureSession(video.current, {
        dominantHand,
        requireFace,
        requireHand: () => qualityRef.current?.handRequired !== false,
        isCancelled: () => !mounted.current,
        onFrame: (next) => {
          if (canvas.current) drawOverlay(canvas.current, next.overlay);
          const now = performance.now();
          if (now - lastUi.current < 250) return; // la interfaz no necesita 15 renders por segundo
          lastUi.current = now;
          setFrame({ guidance: next.guidance, ready: next.ready, fps: next.fps, extractMs: next.extractMs });
        },
      });
      if (!mounted.current) {
        started.stop(); // salió de la página mientras arrancaba
        return;
      }
      session.current = started;
      setPhase({ kind: "ready" });
    } catch (caught) {
      if (!mounted.current) return;
      setError(cameraErrorKind(caught));
      setPhase({ kind: "off" });
    }
  };

  const turnOff = () => {
    session.current?.stop();
    session.current = null;
    setPhase({ kind: "off" });
    if (canvas.current) drawOverlay(canvas.current, null);
  };

  useEffect(() => {
    if (phase.kind !== "countdown") return;
    const timer = window.setTimeout(() => {
      if (phase.left > 1) {
        setPhase({ kind: "countdown", left: phase.left - 1 });
        return;
      }
      const current = session.current;
      if (!current) return;
      setPhase({ kind: "recording" });
      void current.record(qualityRef.current).then((sample) => {
        if (!mounted.current || session.current !== current) return;
        setPhase({ kind: "ready" });
        onSampleRef.current(sample);
      });
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [phase]);

  const status =
    phase.kind === "countdown"
      ? `${phase.left}…`
      : phase.kind === "recording"
        ? "¡Haz la seña!"
        : phase.kind === "starting"
          ? "Encendiendo la cámara…"
          : "";

  return (
    <div className="space-y-2">
      <div className="relative overflow-hidden rounded-2xl bg-[#0E2A2F]" style={{ aspectRatio: "4 / 3", maxHeight: 360 }}>
        <video ref={video} muted playsInline aria-label="Vista de tu cámara" className="h-full w-full -scale-x-100" />
        <canvas ref={canvas} width={640} height={480} aria-hidden="true" className="absolute inset-0 h-full w-full -scale-x-100" />
        {phase.kind !== "off" && (
          // Silueta guía (cabeza y hombros): «Ubícate dentro de la silueta» (A.5).
          <svg viewBox="0 0 400 300" aria-hidden="true" className="pointer-events-none absolute inset-0 h-full w-full">
            <ellipse cx="200" cy="105" rx="48" ry="60" fill="none" stroke="white" strokeOpacity="0.55" strokeWidth="3" strokeDasharray="8 6" />
            <path d="M80 300 C 90 215, 140 190, 200 190 C 260 190, 310 215, 320 300" fill="none" stroke="white" strokeOpacity="0.55" strokeWidth="3" strokeDasharray="8 6" />
          </svg>
        )}
        <p role="status" className={`absolute top-3 left-3 rounded-xl px-3 py-1 font-display text-2xl font-extrabold ${status ? "bg-white/90" : ""}`}>
          {status}
        </p>
        {showStats && phase.kind !== "off" && (
          <p className="absolute right-3 bottom-3 rounded-lg bg-black/60 px-2 py-1 font-mono text-xs text-white">
            {frame.fps.toFixed(0)} FPS · {frame.extractMs.toFixed(0)} ms
          </p>
        )}
      </div>
      {phase.kind === "off" && <p className="text-sm text-[#45606A]">🔒 {PRIVACY_NOTICE}</p>}
      {phase.kind !== "off" && phase.kind !== "starting" && (
        <ul aria-live="polite" className="min-h-6 text-sm font-semibold text-amber-800">
          {frame.guidance.length === 0 ? (
            <li className="text-[#047857]">{frame.ready ? "¡Todo listo! Ubícate dentro de la silueta." : "Ubícate dentro de la silueta"}</li>
          ) : (
            frame.guidance.map((message) => <li key={message}>{message}</li>)
          )}
        </ul>
      )}
      {error && (
        <p role="alert" className="rounded-xl bg-red-50 p-2 text-sm text-red-800">
          {CAMERA_ERRORS[error]}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {phase.kind === "off" || phase.kind === "starting" ? (
          <button
            type="button"
            disabled={phase.kind === "starting" || disabled}
            onClick={() => void turnOn()}
            className="rounded-xl bg-[#047857] px-4 py-2 font-bold text-white disabled:opacity-60"
          >
            Activar cámara
          </button>
        ) : (
          <>
            <button
              type="button"
              disabled={phase.kind !== "ready" || !frame.ready || disabled}
              onClick={() => {
                onRecordStart?.();
                setPhase({ kind: "countdown", left: COUNTDOWN_S });
              }}
              className="rounded-xl bg-[#047857] px-4 py-2 font-bold text-white disabled:opacity-60"
            >
              {recordText}
            </button>
            <button type="button" onClick={turnOff} className="rounded-xl border border-slate-300 px-4 py-2 font-semibold">
              Apagar cámara
            </button>
          </>
        )}
      </div>
    </div>
  );
}
