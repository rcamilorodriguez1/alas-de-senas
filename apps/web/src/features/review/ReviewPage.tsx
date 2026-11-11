import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { AppLayout } from "../../components/layout/AppLayout";
import { Mascot } from "../../components/mascot/Mascot";
import { ApiError } from "../../lib/api";
import { statsKey, streakLabel } from "../gamification/gamification-api";
import { StatsPanel } from "../gamification/StatsPanel";
import { SelectMeaningActivity } from "../lesson/activities/SelectMeaningActivity";
import type { AnswerBody, LessonExercise } from "../lesson/lesson-api";
import { progressKey } from "../progress/progress-api";
import {
  completeReview,
  reviewQueueKey,
  sendReviewAnswer,
  startReview,
  useReviewQueue,
  type ReviewCompletion,
  type ReviewExercise,
  type ReviewStart,
} from "./review-api";
import { HeartIcon, StreakIcon } from "../../components/icons/GameIcon";

type Phase =
  | { kind: "idle" }
  | { kind: "starting" }
  | { kind: "ready"; data: ReviewStart; index: number }
  | { kind: "done"; result: ReviewCompletion };

/** Un ejercicio de repaso con la forma que espera la tarjeta de la actividad 2. */
function asActivity(exercise: ReviewExercise, index: number): LessonExercise {
  return {
    id: exercise.id,
    order: index + 1,
    activity: "SELECT",
    type: exercise.type,
    scored: true,
    group: null,
    content: exercise.content,
  };
}

function AllDone() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl bg-white p-6 text-center shadow">
      <Mascot mood="happy" message="¡Todo al día! Vuelve mañana." />
      <p className="text-lg font-semibold">No tienes señas por repasar hoy.</p>
      <Link to="/aprender" className="font-semibold text-[#047857] underline">
        Seguir aprendiendo
      </Link>
    </div>
  );
}

export function ReviewPage() {
  const queryClient = useQueryClient();
  const queue = useReviewQueue();
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [nothingDue, setNothingDue] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const begin = async () => {
    setNotice(null);
    setPhase({ kind: "starting" });
    try {
      setPhase({ kind: "ready", data: await startReview(), index: 0 });
    } catch (error) {
      if (error instanceof ApiError && error.code === "NO_REVIEWS_DUE") setNothingDue(true);
      else setNotice("No pudimos empezar el repaso. Intenta de nuevo.");
      setPhase({ kind: "idle" });
    }
  };

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: reviewQueueKey });
    void queryClient.invalidateQueries({ queryKey: statsKey });
    void queryClient.invalidateQueries({ queryKey: progressKey });
  };

  let body;
  if (phase.kind === "done") {
    const { result } = phase;
    body = (
      <div className="flex flex-col items-center gap-3 rounded-2xl bg-white p-6 text-center shadow">
        <Mascot mood="cheer" message="¡Tus señas siguen frescas!" size={100} />
        <h2 className="font-display text-3xl font-extrabold">¡Repaso terminado!</h2>
        <p className="text-2xl font-bold">{result.score} %</p>
        <p className="font-semibold">
          {result.correct} de {result.total} correctas
        </p>
        <p className="flex items-center gap-2 font-semibold">
          <StreakIcon size={24} /> Racha: {streakLabel(result.streak.current)}
        </p>
        {result.heartsGained > 0 && (
          <p className="flex items-center gap-2 font-semibold">
            <HeartIcon size={24} /> +1 vida
          </p>
        )}
        {result.newAchievements.map((achievement) => (
          <p key={achievement.id} className="rounded-xl bg-amber-50 p-3 font-semibold">
            ¡Logro desbloqueado! {achievement.title} (+{achievement.nectar} de néctar)
          </p>
        ))}
        <Link
          to="/aprender"
          className="mt-2 rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-6 py-3 font-display font-bold text-white"
        >
          Volver a la ruta
        </Link>
      </div>
    );
  } else if (phase.kind === "ready") {
    const { data, index } = phase;
    const exercise = data.exercises[index];
    const percent = Math.floor((index * 100) / data.exercises.length);
    const submit = async (answer: AnswerBody) => {
      setNotice(null);
      try {
        return await sendReviewAnswer(data.sessionId, exercise.id, answer);
      } catch {
        setNotice("No pudimos enviar tu respuesta. Revisa tu conexión e intenta de nuevo.");
        return null;
      }
    };
    const next = async () => {
      if (index + 1 < data.exercises.length) {
        setPhase({ kind: "ready", data, index: index + 1 });
        return;
      }
      try {
        const result = await completeReview(data.sessionId);
        refresh();
        setPhase({ kind: "done", result });
      } catch {
        setNotice("No pudimos terminar el repaso. Intenta de nuevo con «Continuar».");
      }
    };
    body = (
      <div className="rounded-2xl bg-white p-6 shadow">
        <div className="mb-4 flex items-center gap-3">
          <div
            role="progressbar"
            aria-label="Avance del repaso"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-3 flex-1 overflow-hidden rounded-full bg-slate-200"
          >
            <div className="h-full bg-[#10B981]" style={{ width: `${percent}%` }} />
          </div>
          <span className="text-sm font-semibold">
            Seña {index + 1} de {data.exercises.length}
          </span>
        </div>
        <p className="mb-3 text-sm text-[#45606A]">El repaso no quita vidas.</p>
        <SelectMeaningActivity
          key={exercise.id}
          exercise={asActivity(exercise, index)}
          onSubmit={submit}
          onContinue={() => void next()}
        />
      </div>
    );
  } else if (nothingDue || queue.data?.due === 0) {
    body = <AllDone />;
  } else {
    body = (
      <div className="flex flex-col gap-4 rounded-2xl bg-white p-6 shadow">
        {queue.isPending && <p role="status">Buscando tus señas por repasar…</p>}
        {queue.isError && <p role="alert">No pudimos cargar tus señas por repasar.</p>}
        {queue.data && (
          <>
            <Mascot mood="thinking" message="Repasar a tiempo hace que no se te olviden." />
            <p className="text-lg font-semibold">
              Tienes {queue.data.due} {queue.data.due === 1 ? "seña" : "señas"} por repasar
            </p>
            <ul className="flex flex-wrap gap-2">
              {queue.data.signs.map((sign) => (
                <li key={sign.word} className="rounded-full bg-emerald-50 px-3 py-1 font-semibold">
                  {sign.word}
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => void begin()}
              disabled={phase.kind === "starting"}
              className="rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-6 py-3 font-display text-lg font-bold text-white disabled:opacity-60"
            >
              Empezar repaso
            </button>
          </>
        )}
      </div>
    );
  }

  return (
    <AppLayout aside={<StatsPanel />}>
      <h1 className="mb-4 font-display text-3xl font-extrabold">Repasar</h1>
      {notice && (
        <p role="alert" className="mb-3 rounded-xl bg-amber-50 p-3 text-amber-900">
          {notice}
        </p>
      )}
      {body}
    </AppLayout>
  );
}
