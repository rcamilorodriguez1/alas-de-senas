import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { Mascot } from "../../components/mascot/Mascot";
import { ApiError } from "../../lib/api";
import { useSessionStore } from "../../lib/session-store";
import { useReviewQueue } from "../review/review-api";
import { buyStreakFreeze, statsKey, streakLabel, useCountdown, useStats } from "./gamification-api";

const MAX_FREEZES = 2;


/** Panel derecho (§9.5, mockup «Aprender»): racha, meta diaria, néctar, vidas y protector. */
export function StatsPanel() {
  const user = useSessionStore((state) => state.user);
  const queryClient = useQueryClient();
  const { data: stats } = useStats();
  const { data: queue } = useReviewQueue();
  const [buying, setBuying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const countdown = useCountdown(stats?.hearts.enabled ? stats.hearts.nextHeartAt : null);

  const greeting = user?.name ? `¡Hola, ${user.name}! Sigue tu ruta.` : "¡Hola! Sigue tu ruta.";
  if (!stats) {
    return (
      <section aria-label="Tu día" className="sticky top-8 rounded-2xl bg-white p-4 shadow">
        <Mascot mood="happy" message={greeting} />
      </section>
    );
  }

  const { streak, today, hearts } = stats;
  const goalMinutes = Math.floor(today.goalSeconds / 60);
  const percent =
    today.goalSeconds > 0 ? Math.min(100, Math.floor((today.seconds * 100) / today.goalSeconds)) : 0;

  const onBuy = async () => {
    setError(null);
    setBuying(true);
    try {
      queryClient.setQueryData(statsKey, await buyStreakFreeze());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No pudimos comprar el protector.");
    } finally {
      setBuying(false);
    }
  };

  return (
    <section aria-label="Tu día" className="sticky top-8 flex flex-col gap-4 rounded-2xl bg-white p-4 shadow">
      <Mascot
        mood={streak.atRisk ? "sleeping" : "happy"}
        message={streak.atRisk ? "Tu racha está en riesgo: practica hoy" : greeting}
      />
      <div>
        <p className="font-display text-lg font-extrabold">🔥 {streakLabel(streak.current)} de racha</p>
        <p className="text-sm text-[#45606A]">
          Protectores: {streak.freezesAvailable} de {MAX_FREEZES}
        </p>
        <button
          type="button"
          onClick={() => void onBuy()}
          disabled={buying || streak.freezesAvailable >= MAX_FREEZES}
          className="mt-2 rounded-xl border border-[#047857] px-3 py-1.5 text-sm font-semibold text-[#047857] hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Comprar protector (50 de néctar)
        </button>
        {error && (
          <p role="alert" className="mt-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </div>
      <div>
        <div className="flex justify-between text-sm font-semibold">
          <span>Meta diaria</span>
          <span>
            {Math.floor(today.seconds / 60)} de {goalMinutes} min
          </span>
        </div>
        <div
          role="progressbar"
          aria-label="Meta diaria"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          className="mt-1 h-3 overflow-hidden rounded-full bg-slate-200"
        >
          <div className="h-full bg-[#10B981]" style={{ width: `${percent}%` }} />
        </div>
      </div>
      <p className="font-semibold">🌸 {stats.nectar} de néctar</p>
      {queue && queue.due > 0 && (
        <div className="rounded-xl bg-emerald-50 p-3">
          <p className="font-semibold">Señas por repasar: {queue.due}</p>
          <p className="text-sm text-[#45606A]">{queue.signs.map((sign) => sign.word).join(", ")}</p>
          <Link to="/repaso" className="text-sm font-bold text-[#047857] underline">
            Repasar ahora
          </Link>
        </div>
      )}
      {hearts.enabled && (
        <div>
          <p className="font-semibold">
            ❤️ {hearts.current} de {hearts.max}
          </p>
          {countdown && <p className="text-sm text-[#45606A]">Próxima vida en {countdown}</p>}
        </div>
      )}
    </section>
  );
}
