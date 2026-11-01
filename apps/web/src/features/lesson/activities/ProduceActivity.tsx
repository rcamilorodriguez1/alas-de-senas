import { useState } from "react";
import { SignVideoPlayer } from "../../../components/video/SignVideoPlayer";
import type { ActivityProps } from "./activity-utils";

/** Produce la seña: por ahora autoevaluación (R4.8); la cámara llega en el Grupo 10. */
export function ProduceActivity({ exercise, onSubmit, onContinue }: ActivityProps) {
  const [sending, setSending] = useState(false);
  const content = exercise.content;
  if (content.type !== "PRODUCE") return null;
  const answer = async (ok: boolean) => {
    setSending(true);
    const result = await onSubmit({ method: "self", ok });
    setSending(false);
    if (result) onContinue();
  };
  return (
    <div className="space-y-3">
      <SignVideoPlayer
        src={content.video.src}
        poster={content.video.poster}
        word={content.word}
        maxHeight={260}
        autoPlay
      />
      <p className="font-display text-xl font-extrabold">{content.word}</p>
      <p className="font-semibold">¿Te salió igual al video?</p>
      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          disabled={sending}
          onClick={() => void answer(true)}
          className="rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-4 py-3 font-bold text-white hover:bg-emerald-800"
        >
          Sí, me salió
        </button>
        <button
          type="button"
          disabled={sending}
          onClick={() => void answer(false)}
          className="rounded-xl border-2 border-slate-300 bg-white px-4 py-3 font-bold text-[#0E2A2F] hover:bg-slate-50"
        >
          Necesito repasar
        </button>
      </div>
      <p className="text-sm text-[#45606A]">🔒 Tu video no sale de tu dispositivo.</p>
    </div>
  );
}
