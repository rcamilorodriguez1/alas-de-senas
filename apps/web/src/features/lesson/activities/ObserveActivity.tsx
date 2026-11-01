import { useState } from "react";
import { SignVideoPlayer } from "../../../components/video/SignVideoPlayer";
import { primaryButton, type ActivityProps } from "./activity-utils";

export function ObserveActivity({ exercise, onSubmit, onContinue }: ActivityProps) {
  const [sending, setSending] = useState(false);
  const content = exercise.content;
  if (content.type !== "OBSERVE") return null;
  const next = async () => {
    setSending(true);
    const result = await onSubmit({ watched: true });
    setSending(false);
    if (result) onContinue();
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
      <p className="font-display text-2xl font-extrabold">{content.word}</p>
      <p>
        <span className="font-semibold">Cómo se hace: </span>
        {content.howTo ?? "Descripción en revisión"}
      </p>
      <p className="text-[#45606A]">
        <span className="font-semibold">Ejemplo: </span>
        {content.usageExample}
      </p>
      <button type="button" onClick={() => void next()} disabled={sending} className={primaryButton}>
        Continuar
      </button>
    </div>
  );
}
