import { useState } from "react";
import { SignVideoPlayer } from "../../../components/video/SignVideoPlayer";
import type { AnswerResult } from "../lesson-api";
import { primaryButton, type ActivityProps } from "./activity-utils";
import { ContinueButton, Feedback } from "./shared";

interface Pair {
  videoToken: string;
  wordToken: string;
}

/** Juego de memoria: une cada video con su palabra; se evalúa en el servidor. */
export function MemoryMatchActivity({ exercise, onSubmit, onContinue }: ActivityProps) {
  const [video, setVideo] = useState<string | null>(null);
  const [word, setWord] = useState<string | null>(null);
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const content = exercise.content;
  if (content.type !== "MEMORY_MATCH") return null;

  const usedVideos = new Set(pairs.map((p) => p.videoToken));
  const usedWords = new Set(pairs.map((p) => p.wordToken));
  const complete = pairs.length === content.videoCards.length;

  // Se puede elegir primero el video o primero la palabra.
  const addPair = (videoToken: string, wordToken: string) => {
    setPairs([...pairs, { videoToken, wordToken }]);
    setVideo(null);
    setWord(null);
  };
  const pickVideo = (videoToken: string) => {
    if (usedVideos.has(videoToken)) return;
    if (word) addPair(videoToken, word);
    else setVideo(videoToken);
  };
  const pickWord = (wordToken: string) => {
    if (usedWords.has(wordToken)) return;
    if (video) addPair(video, wordToken);
    else setWord(wordToken);
  };

  const check = async () => {
    const answer = await onSubmit({ attempts: pairs.map((p) => ({ ...p })) });
    if (answer) setResult(answer);
  };

  return (
    <div className="space-y-3">
      <p className="font-semibold">Une cada seña con su significado.</p>
      <div className="grid grid-cols-2 gap-4">
        <ul className="space-y-2" aria-label="Videos">
          {content.videoCards.map((card, index) => (
            <li key={card.token}>
              <button
                type="button"
                aria-label={`Video ${index + 1}`}
                aria-pressed={video === card.token}
                disabled={usedVideos.has(card.token) || result !== null}
                onClick={() => pickVideo(card.token)}
                className={`w-full rounded-xl border-2 p-1 ${video === card.token ? "border-[#047857]" : "border-slate-200"} disabled:opacity-50`}
              >
                <SignVideoPlayer
                  src={card.video.src}
                  poster={card.video.poster}
                  word={`video ${index + 1}`}
                  label={`Video de la tarjeta ${index + 1}`}
                  compact
                />
              </button>
            </li>
          ))}
        </ul>
        <ul className="space-y-2" aria-label="Palabras">
          {content.wordCards.map((card) => (
            <li key={card.token}>
              <button
                type="button"
                aria-pressed={word === card.token}
                disabled={usedWords.has(card.token) || result !== null}
                onClick={() => pickWord(card.token)}
                className={`w-full rounded-xl border-2 p-3 font-semibold disabled:opacity-50 ${word === card.token ? "border-[#047857]" : "border-slate-200"}`}
              >
                {card.word}
              </button>
            </li>
          ))}
        </ul>
      </div>
      <p className="text-sm text-[#45606A]">
        Parejas: {pairs.length} de {content.videoCards.length}
      </p>
      {result ? (
        <>
          <Feedback correct={result.correct} />
          <ContinueButton onContinue={onContinue} />
        </>
      ) : (
        <button type="button" disabled={!complete} onClick={() => void check()} className={primaryButton}>
          Comprobar respuesta
        </button>
      )}
    </div>
  );
}
