import { useCallback, useState } from "react";
import { SignVideoPlayer } from "../../../components/video/SignVideoPlayer";
import type { AnswerResult } from "../lesson-api";
import { primaryButton, useChoiceKeys, type ActivityProps } from "./activity-utils";
import { ContinueButton, Feedback } from "./shared";

interface Option {
  token: string;
  word?: string;
  video?: { src: string; poster: string };
}

function correctTokens(result: AnswerResult): string[] {
  if (result.correctTokens.length > 0) return result.correctTokens;
  return result.correctToken ? [result.correctToken] : [];
}

/** Selecciona el significado (VIDEO_TO_MEANING, MEANING_TO_VIDEO) y deletreo (SPELLING). */
export function SelectMeaningActivity({ exercise, onSubmit, onContinue }: ActivityProps) {
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [sending, setSending] = useState(false);
  const content = exercise.content;

  let prompt: React.ReactNode = null;
  let question = "¿Qué significa esta seña?";
  let options: Option[] = [];
  if (content.type === "VIDEO_TO_MEANING") {
    prompt = (
      <SignVideoPlayer
        src={content.video.src}
        poster={content.video.poster}
        word="por adivinar"
        label="Video de la seña"
        maxHeight={220}
        autoPlay
      />
    );
    options = content.options.map((o) => ({ token: o.token, word: o.word }));
  } else if (content.type === "MEANING_TO_VIDEO") {
    question = `¿Cuál es la seña de «${content.word}»?`;
    options = content.options.map((o) => ({ token: o.token, video: o.video }));
  } else if (content.type === "SPELLING") {
    question = "¿Qué palabra se deletrea?";
    prompt = (
      <div className="flex flex-wrap justify-center gap-2">
        {content.letters.map((letter, index) => (
          <div key={`${letter.src}-${index}`} className="w-28">
            <SignVideoPlayer
              src={letter.src}
              poster={letter.poster}
              word={`letra ${index + 1}`}
              label={`Letra ${index + 1}`}
              compact
            />
          </div>
        ))}
      </div>
    );
    options = content.options.map((o) => ({ token: o.token, word: o.word }));
  }

  const check = useCallback(async () => {
    if (selected === null || result || sending) return;
    setSending(true);
    const answer = await onSubmit({ optionToken: options[selected].token });
    setSending(false);
    if (answer) setResult(answer);
    // options se recalcula en cada render a partir del mismo contenido.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, result, sending, onSubmit]);

  const onEnter = useCallback(() => {
    if (result) onContinue();
    else void check();
  }, [result, onContinue, check]);
  const onSelect = useCallback((index: number) => {
    if (!result) setSelected(index);
  }, [result]);
  useChoiceKeys({ count: options.length, onSelect, onEnter });

  return (
    <div className="space-y-3">
      {prompt}
      <p className="font-semibold">{question}</p>
      <div role="radiogroup" aria-label="Opciones" className="grid grid-cols-2 gap-2">
        {options.map((option, index) => {
          const isCorrect = result !== null && correctTokens(result).includes(option.token);
          const isWrong = result !== null && selected === index && !result.correct;
          const tone = isCorrect
            ? "border-emerald-600 bg-emerald-50"
            : isWrong
              ? "border-red-600 bg-red-50"
              : selected === index
                ? "border-[#047857] bg-emerald-50"
                : "border-slate-200 bg-white hover:border-slate-400";
          return (
            <button
              key={option.token}
              type="button"
              role="radio"
              aria-checked={selected === index}
              aria-label={option.video ? `Opción ${index + 1}` : undefined}
              disabled={result !== null}
              onClick={() => setSelected(index)}
              className={`flex w-full items-center gap-3 rounded-xl border-2 px-3 py-2 text-left font-semibold ${tone}`}
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-300 text-sm">
                {index + 1}
              </span>
              {option.video ? (
                <span className="flex-1">
                  <SignVideoPlayer
                    src={option.video.src}
                    poster={option.video.poster}
                    word={`opción ${index + 1}`}
                    label={`Video de la opción ${index + 1}`}
                    compact
                  />
                </span>
              ) : (
                <span className="flex-1">{option.word}</span>
              )}
              {isCorrect && <span className="text-emerald-700">✔ Correcta</span>}
              {isWrong && <span className="text-red-700">✖ Incorrecta</span>}
            </button>
          );
        })}
      </div>
      {result ? (
        <>
          <Feedback correct={result.correct} word={result.correctWord} />
          <ContinueButton onContinue={onContinue} />
        </>
      ) : (
        <button
          type="button"
          onClick={() => void check()}
          disabled={selected === null || sending}
          className={primaryButton}
        >
          Comprobar respuesta
        </button>
      )}
    </div>
  );
}
