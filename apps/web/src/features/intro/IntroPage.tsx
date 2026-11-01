import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Mascot } from "../../components/mascot/Mascot";
import { SignVideoPlayer } from "../../components/video/SignVideoPlayer";
import { apiRequest } from "../../lib/api";
import type { components } from "../../lib/api-types";
import { markIntroCompleted } from "./intro-storage";

type Intro = components["schemas"]["IntroOut"];

// Un mensaje de Tomi por tarjeta (R1.2): anima, nunca regaña.
const TOMI_MESSAGES = [
  "¡Hola! Soy Tomi. Mira cómo se saluda en LSC.",
  "Dar las gracias abre muchas puertas.",
  "Con «por favor» todo vuela mejor.",
  "Fíjate en el movimiento de la mano.",
  "¡Vas muy bien! Ya casi conoces seis señas.",
  "Última seña antes del mini-quiz. ¡Tú puedes!",
];

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[#F5FAF7] px-4 py-6 font-sans text-[#0E2A2F]">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
        <div className="flex justify-end">
          <Link
            to="/ingresar"
            className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 font-semibold hover:bg-slate-50"
          >
            Ya tengo cuenta
          </Link>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow">{children}</div>
      </div>
    </main>
  );
}

/** Bienvenida (R1): 6 tarjetas con video en bucle y un mini-quiz de 3 preguntas. */
export function IntroPage() {
  const navigate = useNavigate();
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["intro"],
    queryFn: () => apiRequest<Intro>("GET", "/intro", { auth: false }),
  });
  const [step, setStep] = useState(0);
  const [chosen, setChosen] = useState<number | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  // Cada tarjeta o pregunta nueva lleva el foco a su título: teclado y lector no se pierden.
  useEffect(() => {
    if (step > 0) heading.current?.focus();
  }, [step]);

  if (isPending) {
    return (
      <Frame>
        <p role="status">Preparando la bienvenida…</p>
      </Frame>
    );
  }
  if (isError || !data) {
    return (
      <Frame>
        <p role="alert">No pudimos cargar la bienvenida.</p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="mt-2 rounded-xl border border-slate-300 px-3 py-1.5 font-semibold"
        >
          Reintentar
        </button>
      </Frame>
    );
  }

  const cards = data.cards.length;
  const questions = data.quiz.length;
  const finish = () => {
    void navigate("/registro");
  };

  if (step < cards) {
    const card = data.cards[step];
    return (
      <Frame>
        <p className="text-sm font-bold tracking-wide text-[#45606A] uppercase">
          Seña {step + 1} de {cards}
        </p>
        <h1 ref={heading} tabIndex={-1} className="mt-1 font-display text-3xl font-extrabold outline-none">
          {card.word}
        </h1>
        <div className="mt-4">
          <SignVideoPlayer
            key={card.slug}
            src={card.video.src}
            poster={card.video.poster}
            word={card.word}
            isPlaceholder={card.video.placeholder}
            mediaSource={card.video.source}
            compact
            maxHeight={300}
          />
        </div>
        <div className="mt-4">
          <Mascot mood="happy" message={TOMI_MESSAGES[step % TOMI_MESSAGES.length]} />
        </div>
        <button
          type="button"
          autoFocus={step === 0}
          onClick={() => setStep(step + 1)}
          className="mt-4 w-full rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-4 py-3 font-display text-lg font-bold text-white"
        >
          {step + 1 < cards ? "Siguiente" : "Ir al mini-quiz"}
        </button>
      </Frame>
    );
  }

  const index = step - cards;
  if (index < questions) {
    const question = data.quiz[index];
    const answered = chosen !== null;
    const right = answered && question.options[chosen].correct;
    return (
      <Frame>
        <p className="text-sm font-bold tracking-wide text-[#45606A] uppercase">
          Mini-quiz · Pregunta {index + 1} de {questions}
        </p>
        <h1 ref={heading} tabIndex={-1} className="mt-1 font-display text-2xl font-extrabold outline-none">
          ¿Qué significa esta seña?
        </h1>
        <div className="mt-4">
          <SignVideoPlayer
            key={question.slug}
            src={question.video.src}
            poster={question.video.poster}
            word="del mini-quiz"
            isPlaceholder={question.video.placeholder}
            mediaSource={question.video.source}
            compact
            maxHeight={260}
          />
        </div>
        <div role="group" aria-label="Opciones" className="mt-4 grid gap-2">
          {question.options.map((option, i) => {
            const style = !answered
              ? "border-slate-300 hover:border-[#047857]"
              : option.correct
                ? "border-[#047857] bg-emerald-50"
                : i === chosen
                  ? "border-amber-500 bg-amber-50"
                  : "border-slate-200 opacity-70";
            return (
              <button
                key={option.word}
                type="button"
                disabled={answered}
                onClick={() => {
                  setChosen(i);
                  // R1.4: al terminar el mini-quiz queda marcado, aunque salga por «Ya tengo cuenta».
                  if (index + 1 === questions) markIntroCompleted();
                }}
                className={`rounded-xl border-2 px-4 py-3 text-left font-semibold ${style}`}
              >
                {option.word}
              </button>
            );
          })}
        </div>
        {/* Región siempre montada: los lectores de pantalla anuncian el cambio de texto. */}
        <p role="status" className="mt-4 font-semibold">
          {answered &&
            (right ? "¡Correcto! 🎉" : `Casi. Era «${question.options.find((o) => o.correct)?.word ?? ""}».`)}
        </p>
        {answered && (
          <div className="mt-3 flex flex-col gap-3">
            <button
              type="button"
              autoFocus
              onClick={() => {
                setChosen(null);
                if (index + 1 < questions) setStep(step + 1);
                else finish();
              }}
              className="w-full rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-4 py-3 font-display text-lg font-bold text-white"
            >
              {index + 1 < questions ? "Continuar" : "Crear mi cuenta"}
            </button>
          </div>
        )}
      </Frame>
    );
  }
  return null;
}
