import { useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { Mascot } from "../../components/mascot/Mascot";
import { ApiError } from "../../lib/api";
import { CelebrationModal } from "../gamification/CelebrationModal";
import { achievementsKey, statsKey } from "../gamification/gamification-api";
import { NoHeartsModal } from "../gamification/NoHeartsModal";
import { learningPathKey } from "../learn/learn-api";
import { usePrefersReducedMotion } from "../../lib/motion";
import { ConversationActivity } from "./activities/ConversationActivity";
import { MemoryMatchActivity } from "./activities/MemoryMatchActivity";
import { ObserveActivity } from "./activities/ObserveActivity";
import { ProduceActivity } from "./activities/ProduceActivity";
import { SelectMeaningActivity } from "./activities/SelectMeaningActivity";
import type { ActivityProps } from "./activities/activity-utils";
import { SpellingActivity } from "./activities/SpellingActivity";
import {
  completeLessonSession,
  sendAnswer,
  startLessonSession,
  type AnswerBody,
  type Hearts,
  type LessonCompletion,
  type LessonExercise,
  type LessonStart,
} from "./lesson-api";
import { HeartIcon } from "../../components/icons/GameIcon";

const ACTIVITIES: { kind: LessonExercise["activity"]; title: string }[] = [
  { kind: "OBSERVE", title: "Actividad 1. Observa la seña" },
  { kind: "SELECT", title: "Actividad 2. Selecciona el significado" },
  { kind: "PRODUCE", title: "Actividad 3. Produce la seña" },
  { kind: "USE", title: "Actividad 4. Usa lo aprendido" },
];
const EXPIRED = "Esta lección se actualizó o pasó mucho tiempo. Empecemos de nuevo";
const EXIT_CONFIRM = "¿Salir de la lección? Perderás el avance de esta sesión.";

type Phase =
  | { kind: "loading" }
  | { kind: "blocked"; message: string }
  | { kind: "noHearts"; nextHeartAt: string | null }
  | { kind: "expired" }
  | { kind: "error" }
  | { kind: "ready"; data: LessonStart }
  | { kind: "done"; data: LessonStart; result: LessonCompletion };

function ActivityView(props: ActivityProps) {
  switch (props.exercise.content.type) {
    case "OBSERVE":
      return <ObserveActivity {...props} />;
    case "VIDEO_TO_MEANING":
    case "MEANING_TO_VIDEO":
      return <SelectMeaningActivity {...props} />;
    case "SPELLING":
      return <SpellingActivity {...props} />;
    case "MEMORY_MATCH":
      return <MemoryMatchActivity {...props} />;
    case "PRODUCE":
      return <ProduceActivity {...props} />;
    case "CONVERSATION":
      return <ConversationActivity {...props} />;
  }
}

/** Video principal de un ejercicio (para precargarlo). */
function mainVideo(exercise: LessonExercise | undefined): string | null {
  if (!exercise) return null;
  const content = exercise.content;
  switch (content.type) {
    case "OBSERVE":
    case "VIDEO_TO_MEANING":
    case "PRODUCE":
      return content.video.src;
    case "MEANING_TO_VIDEO":
      return content.options[0]?.video.src ?? null;
    case "CONVERSATION":
      return content.turns[0]?.prompt.src ?? null;
    case "SPELLING":
      return content.letters[0]?.src ?? null;
    case "MEMORY_MATCH":
      return content.videoCards[0]?.video.src ?? null;
  }
}

function Shell({ children, onExit }: { children: ReactNode; onExit?: () => void }) {
  return (
    <main className="min-h-screen bg-[#F5FAF7] px-4 py-6 font-sans text-[#0E2A2F]">
      <div className="relative mx-auto w-full max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow">
        {onExit && (
          <button
            type="button"
            onClick={onExit}
            aria-label="Salir de la lección"
            className="absolute top-4 right-4 rounded-full p-1 text-[#45606A] hover:bg-slate-100"
          >
            <X aria-hidden="true" size={22} />
          </button>
        )}
        {children}
      </div>
    </main>
  );
}

export function LessonPage() {
  const { lessonId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [index, setIndex] = useState(0);
  const [answered, setAnswered] = useState<Set<string>>(new Set());
  const [hearts, setHearts] = useState<Hearts | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [heartbeat, setHeartbeat] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  useEffect(() => {
    if (!heartbeat) return;
    const timer = window.setTimeout(() => setHeartbeat(false), 700);
    return () => window.clearTimeout(timer);
  }, [heartbeat]);
  const started = useRef<string | null>(null);
  const activeCard = useRef<HTMLLIElement>(null);
  const exerciseKey = phase.kind === "ready" ? `${phase.data.sessionId}:${index}` : "";

  // Scroll suave a la actividad activa (§9.3): video, pregunta y botón quedan a la vista.
  useEffect(() => {
    if (!exerciseKey || index === 0) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    activeCard.current?.scrollIntoView?.({ behavior: reduced ? "auto" : "smooth", block: "start" });
  }, [exerciseKey, index]);

  const handleError = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.code === "SESSION_EXPIRED") {
      setPhase({ kind: "expired" });
      return;
    }
    if (error instanceof ApiError && error.code === "LESSON_LOCKED") {
      setPhase({ kind: "blocked", message: "Esta lección aún está bloqueada" });
      return;
    }
    if (error instanceof ApiError && error.code === "NO_HEARTS") {
      setPhase({ kind: "noHearts", nextHeartAt: error.nextHeartAt });
      return;
    }
    setPhase({ kind: "error" });
  }, []);

  const start = useCallback(async () => {
    setPhase({ kind: "loading" });
    setIndex(0);
    setAnswered(new Set());
    try {
      const data = await startLessonSession(lessonId);
      setHearts(data.hearts);
      setPhase({ kind: "ready", data });
    } catch (error) {
      handleError(error);
    }
  }, [lessonId, handleError]);

  // StrictMode monta dos veces: la referencia evita un segundo POST de sesión (B34).
  useEffect(() => {
    if (started.current === lessonId) return;
    started.current = lessonId;
    void start();
  }, [lessonId, start]);

  const inProgress = phase.kind === "ready" && answered.size > 0;
  useEffect(() => {
    if (!inProgress) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [inProgress]);

  const exit = () => {
    if (inProgress && !window.confirm(EXIT_CONFIRM)) return;
    void navigate("/aprender");
  };

  if (phase.kind === "loading") {
    return (
      <Shell>
        <p role="status">Preparando tu lección…</p>
      </Shell>
    );
  }
  if (phase.kind === "blocked" || phase.kind === "error") {
    return (
      <Shell>
        <div className="flex flex-col items-center gap-4 text-center">
          <Mascot mood="thinking" />
          <p role="alert" className="text-lg font-semibold">
            {phase.kind === "blocked" ? phase.message : "No pudimos abrir la lección."}
          </p>
          <Link to="/aprender" className="font-semibold text-[#047857] underline">
            Volver a la ruta
          </Link>
        </div>
      </Shell>
    );
  }
  if (phase.kind === "noHearts") {
    return (
      <Shell>
        <NoHeartsModal nextHeartAt={phase.nextHeartAt} onRefilled={() => void start()} />
      </Shell>
    );
  }
  if (phase.kind === "expired") {
    return (
      <Shell>
        <div className="flex flex-col items-center gap-4 text-center">
          <Mascot mood="thinking" />
          <p role="alert" className="text-lg font-semibold">
            {EXPIRED}
          </p>
          <button
            type="button"
            onClick={() => void start()}
            className="rounded-xl bg-[#047857] px-5 py-2 font-bold text-white"
          >
            Empezar de nuevo
          </button>
        </div>
      </Shell>
    );
  }
  if (phase.kind === "done") {
    return (
      <Shell>
        <CelebrationModal result={phase.result} onClose={() => void navigate("/aprender")} />
      </Shell>
    );
  }

  const { data } = phase;
  const exercises = data.exercises;
  const current = exercises[Math.min(index, exercises.length - 1)];
  const groupCount = new Set(exercises.map((e) => e.group).filter((g) => g !== null)).size;
  const phaseExercises = exercises.filter((e) => e.group === current.group);
  const includedActivities = new Set(exercises.map((e) => e.activity));
  const percent = Math.floor((answered.size * 100) / exercises.length);
  const isLearn = data.lesson.type === "LEARN";
  const nextVideo = mainVideo(exercises[index + 1]);

  // Un corte de red no tumba la lección: se avisa y se puede volver a intentar.
  const recoverable = (error: unknown) =>
    !(error instanceof ApiError) || error.status >= 500 || error.code === "NETWORK_ERROR";

  const submit = async (answer: AnswerBody) => {
    setNotice(null);
    try {
      const result = await sendAnswer(data.sessionId, current.id, answer);
      // Latido del contador al perder una vida (sin animación con movimiento reducido).
      if (hearts && result.hearts.current < hearts.current && !reducedMotion) {
        setHeartbeat(true);
      }
      setHearts(result.hearts);
      setAnswered((previous) => new Set(previous).add(current.id));
      return result;
    } catch (error) {
      if (recoverable(error)) setNotice("No pudimos enviar tu respuesta. Revisa tu conexión e intenta de nuevo.");
      else handleError(error);
      return null;
    }
  };

  const next = async () => {
    if (index + 1 < exercises.length) {
      setIndex(index + 1);
      return;
    }
    try {
      const result = await completeLessonSession(data.sessionId);
      void queryClient.invalidateQueries({ queryKey: statsKey });
      void queryClient.invalidateQueries({ queryKey: achievementsKey });
      await queryClient.invalidateQueries({ queryKey: learningPathKey });
      setPhase({ kind: "done", data, result });
    } catch (error) {
      if (recoverable(error)) setNotice("No pudimos terminar la lección. Intenta de nuevo con «Continuar».");
      else handleError(error);
    }
  };

  return (
    <Shell onExit={exit}>
      <header className="mb-4 pr-10">
        <div className="flex items-center justify-between gap-4 text-xs font-bold tracking-wide text-[#45606A] uppercase">
          <span>
            MÓDULO {data.lesson.moduleOrder} · NODO {data.lesson.nodeOrder} — LECCIÓN{" "}
            {data.lesson.order} · {data.lesson.title.toUpperCase()}
          </span>
          <span className="text-sm text-[#047857]">+{data.lesson.estimatedXp} XP</span>
        </div>
        <div className="mt-2 flex items-center gap-3">
          <div
            role="progressbar"
            aria-label="Avance de la lección"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-3 flex-1 overflow-hidden rounded-full bg-slate-200"
          >
            <div
              className="h-full bg-[#10B981] transition-[width] duration-500 ease-out"
              style={{ width: `${percent}%` }}
            />
          </div>
          {current.group !== null && groupCount > 0 && (
            <span className="text-sm font-semibold">
              Seña {current.group + 1} de {groupCount}
            </span>
          )}
          {isLearn ? (
            <span className="text-sm text-[#45606A]">Sin vidas en juego</span>
          ) : (
            hearts?.enabled && (
              <span
                aria-label={`Vidas: ${hearts.current}`}
                data-testid="hearts"
                data-heartbeat={heartbeat ? "true" : undefined}
                className={`inline-flex items-center gap-1 font-semibold ${heartbeat ? "animate-heartbeat" : ""}`}
              >
                <HeartIcon size={24} /> {hearts.current}
              </span>
            )
          )}
        </div>
      </header>
      {notice && (
        <p role="alert" className="mb-3 rounded-xl bg-amber-50 p-3 text-amber-900">
          {notice}
        </p>
      )}
      <ol className="divide-y divide-slate-200">
        {ACTIVITIES.map((activity) => {
          const isActive = current.activity === activity.kind; // hasta pulsar «Continuar»
          const done =
            !isActive &&
            phaseExercises.some((e) => e.activity === activity.kind && answered.has(e.id));
          // Cada lección trae solo algunas actividades (p. ej. L1 no tiene «Usa lo aprendido»):
          // las demás no se muestran como bloqueadas, porque no hay nada que desbloquear.
          const included = includedActivities.has(activity.kind);
          const status = !included
            ? "No incluida en esta lección"
            : isActive
              ? "En curso"
              : done
                ? "✔ Completada"
                : "🔒 Pendiente";
          return (
            <li
              key={activity.kind}
              ref={isActive ? activeCard : undefined}
              className={isActive ? "scroll-mt-2 py-3" : "py-2"}
            >
              <div className="flex items-center justify-between">
                {/* Gris #45606A en vez de opacidad: sigue cumpliendo contraste AA (R10.5). */}
                <h2
                  className={`font-display text-lg font-extrabold ${included ? "" : "text-[#45606A]"}`}
                >
                  {activity.title}
                </h2>
                <span className="text-sm font-semibold text-[#45606A]">{status}</span>
              </div>
              {isActive && (
                <div className="mt-3" data-testid="active-exercise">
                  {/* Cada ejercicio nuevo entra desde la derecha: se ve que la lección avanza. */}
                  <div key={current.id} className="animate-exercise-in">
                    <ActivityView
                      exercise={current}
                      onSubmit={submit}
                      onContinue={() => void next()}
                    />
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {nextVideo && (
        // Precarga del siguiente video (§9.4, B31): <link rel=preload> no es confiable.
        <video src={nextVideo} preload="auto" muted hidden aria-hidden="true" />
      )}
    </Shell>
  );
}
