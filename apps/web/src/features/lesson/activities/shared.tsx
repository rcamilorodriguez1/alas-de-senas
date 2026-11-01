import { Mascot } from "../../../components/mascot/Mascot";
import { primaryButton } from "./activity-utils";

/** Mensaje amable de Tomi después de comprobar (nunca regaña). */
export function Feedback({ correct, word }: { correct: boolean; word?: string | null }) {
  const message = correct
    ? word
      ? `¡Exacto! Así se dice «${word}».`
      : "¡Exacto!"
    : "Casi. Mira de nuevo la seña.";
  return (
    <div className="mt-3">
      <Mascot mood={correct ? "cheer" : "thinking"} size={56} message={message} />
    </div>
  );
}

export function ContinueButton({ onContinue }: { onContinue: () => void }) {
  return (
    <button type="button" onClick={onContinue} className={`mt-3 ${primaryButton}`}>
      Continuar
    </button>
  );
}
