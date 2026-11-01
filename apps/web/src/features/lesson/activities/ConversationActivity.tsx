import { useState } from "react";
import { SignVideoPlayer } from "../../../components/video/SignVideoPlayer";
import type { AnswerResult } from "../lesson-api";
import { primaryButton, type ActivityProps } from "./activity-utils";
import { ContinueButton, Feedback } from "./shared";

/** Usa lo aprendido: conversación visual de 2–3 turnos con respuestas en video. */
export function ConversationActivity({ exercise, onSubmit, onContinue }: ActivityProps) {
  const [choices, setChoices] = useState<string[]>([]);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const content = exercise.content;
  if (content.type !== "CONVERSATION") return null;

  const turnIndex = Math.min(choices.length, content.turns.length - 1);
  const turn = content.turns[turnIndex];
  const finished = choices.length === content.turns.length;

  const check = async () => {
    const answer = await onSubmit({ choices });
    if (answer) setResult(answer);
  };

  return (
    <div className="space-y-3">
      <p className="font-semibold">
        Turno {turnIndex + 1} de {content.turns.length}
      </p>
      <div className="max-w-xs">
        <p className="mb-1 text-sm font-semibold text-[#45606A]">Persona A:</p>
        <SignVideoPlayer
          src={turn.prompt.src}
          poster={turn.prompt.poster}
          word="de la persona A"
          label="Video de la Persona A"
          compact
        />
      </div>
      <p className="font-semibold">Tu respuesta:</p>
      <div role="radiogroup" aria-label="Respuestas" className="grid grid-cols-3 gap-3">
        {turn.options.map((option, index) => (
          <button
            key={`${turnIndex}-${option.token}`}
            type="button"
            role="radio"
            aria-label={`Opción ${index + 1}`}
            aria-checked={choices[turnIndex] === option.token}
            disabled={finished || result !== null}
            onClick={() => setChoices([...choices.slice(0, turnIndex), option.token])}
            className="rounded-xl border-2 border-slate-200 p-1 hover:border-slate-400 disabled:opacity-60"
          >
            <SignVideoPlayer
              src={option.video.src}
              poster={option.video.poster}
              word={`respuesta ${index + 1}`}
              label={`Video de la respuesta ${index + 1}`}
              compact
            />
          </button>
        ))}
      </div>
      {result ? (
        <>
          <Feedback correct={result.correct} />
          <ContinueButton onContinue={onContinue} />
        </>
      ) : (
        <button type="button" disabled={!finished} onClick={() => void check()} className={primaryButton}>
          Comprobar respuesta
        </button>
      )}
    </div>
  );
}
