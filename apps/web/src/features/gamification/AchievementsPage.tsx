import {
  Award,
  CalendarCheck,
  Crown,
  Eye,
  Feather,
  Flag,
  Flame,
  GraduationCap,
  Hand,
  Lock,
  Trophy,
  type LucideIcon,
} from "lucide-react";
import { AppLayout } from "../../components/layout/AppLayout";
import { StatsPanel } from "./StatsPanel";
import { useAchievements } from "./gamification-api";

// Íconos de lucide-react que el seed guarda por nombre (§7.9).
const ICONS: Record<string, LucideIcon> = {
  feather: Feather,
  "graduation-cap": GraduationCap,
  flame: Flame,
  "calendar-check": CalendarCheck,
  flag: Flag,
  crown: Crown,
  award: Award,
  hand: Hand,
  eye: Eye,
};

function unlockedDate(iso: string): string {
  return new Date(iso).toLocaleDateString("es-CO", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function AchievementsPage() {
  const { data, isPending, isError, refetch } = useAchievements();
  const unlocked = data?.filter((a) => a.unlockedAt !== null).length ?? 0;
  return (
    <AppLayout aside={<StatsPanel />}>
      <h1 className="font-display text-3xl font-extrabold">Logros</h1>
      {isPending && <p role="status">Cargando tus logros…</p>}
      {isError && (
        <div role="alert" className="mt-4 rounded-2xl bg-red-50 p-4 text-red-800">
          <p>No pudimos cargar tus logros.</p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="mt-2 rounded-xl border border-red-300 px-3 py-1.5 font-semibold"
          >
            Reintentar
          </button>
        </div>
      )}
      {data && (
        <>
          <p className="mt-1 font-semibold text-[#45606A]">
            {unlocked} de {data.length} desbloqueados
          </p>
          <ul className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-3">
            {data.map((achievement) => {
              const isUnlocked = achievement.unlockedAt !== null;
              const Icon = isUnlocked ? (ICONS[achievement.icon] ?? Trophy) : Lock;
              return (
                <li
                  key={achievement.id}
                  className={`flex flex-col items-center gap-2 rounded-2xl border p-4 text-center ${
                    isUnlocked ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white opacity-70"
                  }`}
                >
                  <Icon
                    aria-hidden="true"
                    size={36}
                    className={isUnlocked ? "text-amber-600" : "text-slate-400"}
                  />
                  <h2 className="font-display font-extrabold">{achievement.title}</h2>
                  <p className="text-sm">{achievement.description}</p>
                  <p className="text-sm font-semibold text-[#047857]">
                    +{achievement.nectar} de néctar
                  </p>
                  <p className="text-xs font-semibold text-[#45606A]">
                    {achievement.unlockedAt
                      ? `Desbloqueado el ${unlockedDate(achievement.unlockedAt)}`
                      : "Bloqueado"}
                  </p>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </AppLayout>
  );
}
