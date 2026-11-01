import { useEffect } from "react";
import type { AnswerBody, AnswerResult, LessonExercise } from "../lesson-api";

export interface ActivityProps {
  exercise: LessonExercise;
  onSubmit: (answer: AnswerBody) => Promise<AnswerResult | null>;
  onContinue: () => void;
}

export const primaryButton =
  "w-full rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-4 py-3 font-display text-lg font-bold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:border-slate-400 disabled:bg-slate-300 disabled:text-slate-600";

/** Teclas 1–4 eligen opción y Enter comprueba o continúa (R4.14, §9.7). */
export function useChoiceKeys({
  count,
  onSelect,
  onEnter,
}: {
  count: number;
  onSelect: (index: number) => void;
  onEnter: () => void;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target;
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return;
      if (event.key === "Enter") {
        // El Enter sobre un botón normal ya lo activa el navegador; sobre una opción (radio)
        // sí comprueba: así funciona elegir con el mouse y confirmar con Enter (R4.14).
        const onOption = target instanceof HTMLElement && target.getAttribute("role") === "radio";
        if (!onOption && (target instanceof HTMLButtonElement || target instanceof HTMLAnchorElement)) {
          return;
        }
        event.preventDefault();
        onEnter();
        return;
      }
      const index = Number.parseInt(event.key, 10) - 1;
      if (Number.isInteger(index) && index >= 0 && index < Math.min(count, 4)) onSelect(index);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [count, onSelect, onEnter]);
}
