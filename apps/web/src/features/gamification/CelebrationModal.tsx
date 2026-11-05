import confetti from "canvas-confetti";
import { useEffect, useRef } from "react";
import { Mascot } from "../../components/mascot/Mascot";
import { usePrefersReducedMotion } from "../../lib/motion";
import type { LessonCompletion } from "../lesson/lesson-api";
import { streakLabel } from "./gamification-api";

/** Celebración al terminar una lección (R4.9): puntaje, XP, néctar, racha y logros nuevos. */
export function CelebrationModal({
  result,
  onClose,
}: {
  result: LessonCompletion;
  onClose: () => void;
}) {
  const reducedMotion = usePrefersReducedMotion();
  const closeButton = useRef<HTMLButtonElement>(null);
  const celebrated = useRef(false);

  useEffect(() => {
    closeButton.current?.focus();
  }, []);

  useEffect(() => {
    // El confeti se lanza una sola vez y nunca con «movimiento reducido» (R10.5).
    if (!result.passed || reducedMotion || celebrated.current) return;
    celebrated.current = true;
    void confetti({ particleCount: 120, spread: 75, origin: { y: 0.6 }, disableForReducedMotion: true });
  }, [result.passed, reducedMotion]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex animate-fade-in items-center justify-center bg-[#0E2A2F]/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Resultado de la lección"
        className="flex w-full max-w-md animate-pop-in flex-col items-center gap-3 rounded-2xl bg-white p-6 text-center shadow-xl"
      >
        <Mascot mood={result.mascotMood} message={result.mascotMessage} size={110} />
        <h1 className="font-display text-3xl font-extrabold">
          {result.passed ? "¡Lección completada!" : "¡Buen intento!"}
        </h1>
        <p className="text-2xl font-bold">{result.score} %</p>
        <div className="flex gap-6 font-semibold">
          <p className="text-[#047857]">+{result.xpEarned} XP</p>
          <p className="text-[#45606A]">+{result.nectarEarned} de néctar</p>
        </div>
        <p className="font-semibold">🔥 Racha: {streakLabel(result.streak.current)}</p>
        {result.streak.extended && (
          <p className="font-bold text-orange-600">
            {result.streak.current === 1 ? "¡Empezaste una racha!" : "¡Racha extendida!"}
          </p>
        )}
        {result.newAchievements.length > 0 && (
          <ul className="flex w-full flex-col gap-2">
            {result.newAchievements.map((achievement) => (
              <li key={achievement.id} className="rounded-xl bg-amber-50 p-3">
                <p className="text-sm font-bold text-amber-800">¡Logro desbloqueado!</p>
                <p className="font-display font-extrabold">{achievement.title}</p>
                <p className="text-sm">+{achievement.nectar} de néctar</p>
              </li>
            ))}
          </ul>
        )}
        <button
          ref={closeButton}
          type="button"
          onClick={onClose}
          className="mt-2 rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-6 py-3 font-display font-bold text-white"
        >
          Volver a la ruta
        </button>
      </div>
    </div>
  );
}
