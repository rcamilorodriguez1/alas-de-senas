import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Mascot } from "../../components/mascot/Mascot";
import { ApiError } from "../../lib/api";
import { refillHearts, statsKey, useCountdown } from "./gamification-api";

/** Sin vidas (R5.15): repasar, recargar con néctar o esperar; nunca deja atascado a nadie. */
export function NoHeartsModal({
  nextHeartAt,
  onRefilled,
}: {
  nextHeartAt: string | null;
  onRefilled: () => void;
}) {
  const queryClient = useQueryClient();
  const countdown = useCountdown(nextHeartAt);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Foco inicial en «Volver a la ruta»: siempre lleva a algo que se puede hacer (lecciones Aprende).
  const backLink = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    backLink.current?.focus();
  }, []);

  const onRefill = async () => {
    setError(null);
    setBusy(true);
    try {
      queryClient.setQueryData(statsKey, await refillHearts());
      onRefilled();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No pudimos recargar tus vidas.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#0E2A2F]/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Sin vidas"
        className="flex w-full max-w-md flex-col items-center gap-3 rounded-2xl bg-white p-6 text-center shadow-xl"
      >
        <Mascot mood="sad" message="Descansemos un momento y seguimos." size={96} />
        <h1 className="font-display text-2xl font-extrabold">Te quedaste sin vidas por ahora</h1>
        {countdown && <p className="font-semibold">Recuperas la próxima en {countdown}</p>}
        <p className="text-sm text-[#45606A]">Las lecciones «Aprende» siempre están disponibles.</p>
        <div className="mt-2 flex w-full flex-col gap-2">
          <Link
            to="/repaso"
            className="rounded-xl border-b-4 border-emerald-950 bg-[#047857] px-5 py-2.5 font-display font-bold text-white"
          >
            Repasar señas
          </Link>
          <button
            type="button"
            onClick={() => void onRefill()}
            disabled={busy}
            className="rounded-xl border border-[#047857] px-5 py-2.5 font-semibold text-[#047857] hover:bg-emerald-50 disabled:opacity-50"
          >
            Recargar vidas (30 de néctar)
          </button>
          <Link ref={backLink} to="/aprender" className="py-1 font-semibold text-[#45606A] underline">
            Volver a la ruta
          </Link>
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
