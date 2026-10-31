import { motion, type TargetAndTransition } from "framer-motion";
import { usePrefersReducedMotion } from "../../lib/motion";
import { TomiSvg, type MascotMood } from "./Tomi";

// Movimiento por estado de ánimo (§9.6): nunca regaña; «sad» solo baja y se inclina.
const ANIMATIONS: Record<MascotMood, TargetAndTransition> = {
  happy: { y: [0, -6, 0], transition: { duration: 2.4, repeat: Infinity, ease: "easeInOut" } },
  cheer: { y: [0, -18, 0], rotate: [0, -8, 0], transition: { duration: 0.6, repeat: 2 } },
  sad: { y: 6, rotate: 8, transition: { duration: 0.6 } },
  thinking: { rotate: [0, 4, -4, 0], transition: { duration: 2, repeat: Infinity } },
  sleeping: { y: [0, 2, 0], transition: { duration: 3, repeat: Infinity } },
};

interface MascotProps {
  mood?: MascotMood;
  message?: string;
  size?: number;
}

export function Mascot({ mood = "happy", message, size = 96 }: MascotProps) {
  const reducedMotion = usePrefersReducedMotion();
  return (
    <div className="flex items-end gap-3" data-animated={reducedMotion ? "false" : "true"}>
      <motion.div animate={reducedMotion ? undefined : ANIMATIONS[mood]} className="shrink-0">
        <TomiSvg size={size} mood={mood} />
      </motion.div>
      {message && (
        <p
          role="status"
          className="relative rounded-2xl bg-white px-4 py-3 font-display text-base font-bold text-slate-800 shadow-md"
        >
          {message}
        </p>
      )}
    </div>
  );
}
