import { useEffect, useRef } from "react";
import { Link } from "react-router";
import type { LearningLesson } from "./learn-api";
import { isOpenable } from "./status";

interface LessonPopoverProps {
  lesson: LearningLesson;
  id: string;
  onClose: () => void;
}

/** Detalle de una lección de la ruta: XP posible y «Empezar», o por qué está bloqueada. */
export function LessonPopover({ lesson, id, onClose }: LessonPopoverProps) {
  const ref = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  // El foco entra una sola vez al abrir; los renders siguientes no lo roban.
  useEffect(() => {
    ref.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const titleId = `${id}-title`;
  return (
    <div
      ref={ref}
      id={id}
      role="dialog"
      aria-labelledby={titleId}
      tabIndex={-1}
      className="mt-3 w-72 origin-top animate-pop-in rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-xl focus:outline-none"
    >
      <h3 id={titleId} className="font-display text-lg font-extrabold">
        Lección {lesson.order} · {lesson.title}
      </h3>
      <p className="mt-1 font-semibold text-[#047857]">+{lesson.estimatedXp} XP</p>
      {lesson.bestScore !== null && lesson.bestScore !== undefined && (
        <p className="text-sm text-[#45606A]">Tu mejor puntaje: {lesson.bestScore} %</p>
      )}
      {isOpenable(lesson) ? (
        <Link
          to={`/leccion/${lesson.id}`}
          className="mt-3 block rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-4 py-2 text-center font-display font-bold text-white hover:bg-emerald-800"
        >
          Empezar
        </Link>
      ) : (
        <p className="mt-3 rounded-xl bg-slate-100 p-2 text-[#45606A]">
          <span aria-hidden="true">🔒 </span>Esta lección aún está bloqueada
        </p>
      )}
      <button
        type="button"
        onClick={() => onCloseRef.current()}
        className="mt-2 w-full rounded-xl px-3 py-1.5 text-sm font-semibold text-[#45606A] hover:bg-slate-100"
      >
        Cerrar
      </button>
    </div>
  );
}
