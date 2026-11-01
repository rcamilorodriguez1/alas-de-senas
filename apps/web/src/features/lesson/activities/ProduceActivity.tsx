import { useEffect, useRef, useState } from "react";
import { SignVideoPlayer } from "../../../components/video/SignVideoPlayer";
import { fetchModelLabels } from "../../../camera/labels";
import { CAMERA_ERRORS, cameraErrorKind, startCameraSession, type CameraErrorKind } from "../../../camera/session";
import { apiRequest } from "../../../lib/api";
import type { components } from "../../../lib/api-types";
import type { AnswerBody } from "../lesson-api";
import type { ActivityProps } from "./activity-utils";

/** Cámara con la seña pedida: avisa cuando la reconoce (confianza ≥ 0,70, ya suavizada). */
function CameraCheck({ target, onRecognized }: { target: string; onRecognized: (confidence: number) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const done = useRef(false);
  // En un ref: un re-render del padre no debe apagar y volver a encender la cámara.
  const onRecognizedRef = useRef(onRecognized);
  useEffect(() => {
    onRecognizedRef.current = onRecognized;
  }, [onRecognized]);
  const [error, setError] = useState<CameraErrorKind | null>(null);

  useEffect(() => {
    let stop: (() => void) | null = null;
    let cancelled = false;
    const element = video.current;
    if (!element) return;
    startCameraSession(element, ({ detected }) => {
      if (done.current || detected?.label !== target) return;
      done.current = true;
      onRecognizedRef.current(detected.confidence);
    })
      .then((session) => {
        if (cancelled) session.stop();
        else stop = () => session.stop();
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(cameraErrorKind(caught));
      });
    // R8.5: la cámara se apaga al salir del ejercicio.
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [target]);

  return (
    <div className="space-y-2">
      <div className="overflow-hidden rounded-2xl bg-[#0E2A2F]" style={{ aspectRatio: "4 / 3", maxHeight: 220 }}>
        <video ref={video} muted playsInline aria-label="Vista de tu cámara" className="h-full w-full -scale-x-100" />
      </div>
      {error ? (
        <p role="alert" className="rounded-xl bg-red-50 p-2 text-sm text-red-800">
          {CAMERA_ERRORS[error]} Usa la autoevaluación.
        </p>
      ) : (
        <p role="status" className="text-sm font-semibold text-[#45606A]">
          Haz la seña frente a la cámara…
        </p>
      )}
    </div>
  );
}

/** Produce la seña (R4.8): con cámara si el modelo conoce la seña; si no, autoevaluación. */
export function ProduceActivity({ exercise, onSubmit, onContinue }: ActivityProps) {
  const [sending, setSending] = useState(false);
  const [labels, setLabels] = useState<string[]>([]);
  const [useCamera, setUseCamera] = useState(false);
  const content = exercise.content;
  const cameraLabel = content.type === "PRODUCE" ? content.cameraLabel : null;

  useEffect(() => {
    let active = true;
    void fetchModelLabels().then((list) => {
      if (active) setLabels(list);
    });
    return () => {
      active = false;
    };
  }, []);

  if (content.type !== "PRODUCE") return null;
  const canUseCamera = cameraLabel !== null && labels.includes(cameraLabel);

  const answer = async (body: AnswerBody) => {
    setSending(true);
    const result = await onSubmit(body);
    setSending(false);
    if (result) onContinue();
  };

  const recognized = (confidence: number) => {
    setUseCamera(false);
    if (cameraLabel) {
      const report: components["schemas"]["RecognitionIn"] = { signId: cameraLabel, correct: true, confidence };
      void apiRequest("POST", "/recognition/results", { body: report }).catch(() => undefined);
    }
    void answer({ method: "camera", ok: true, confidence });
  };

  return (
    <div className="space-y-3">
      <SignVideoPlayer
        src={content.video.src}
        poster={content.video.poster}
        word={content.word}
        isPlaceholder={content.video.placeholder}
        mediaSource={content.video.source}
        maxHeight={260}
        autoPlay
      />
      <p className="font-display text-xl font-extrabold">{content.word}</p>
      {canUseCamera &&
        (useCamera && cameraLabel ? (
          <CameraCheck target={cameraLabel} onRecognized={recognized} />
        ) : (
          <button
            type="button"
            disabled={sending}
            onClick={() => setUseCamera(true)}
            className="w-full rounded-xl border-2 border-[#047857] bg-white px-4 py-3 font-bold text-[#047857] hover:bg-emerald-50"
          >
            Usar la cámara
          </button>
        ))}
      <p className="font-semibold">¿Te salió igual al video?</p>
      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          disabled={sending}
          onClick={() => void answer({ method: "self", ok: true })}
          className="rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-4 py-3 font-bold text-white hover:bg-emerald-800"
        >
          Sí, me salió
        </button>
        <button
          type="button"
          disabled={sending}
          onClick={() => void answer({ method: "self", ok: false })}
          className="rounded-xl border-2 border-slate-300 bg-white px-4 py-3 font-bold text-[#0E2A2F] hover:bg-slate-50"
        >
          Necesito repasar
        </button>
      </div>
      <p className="text-sm text-[#45606A]">🔒 Tu video no sale de tu dispositivo.</p>
    </div>
  );
}
