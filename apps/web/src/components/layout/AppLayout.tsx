import {
  BarChart3,
  BookOpen,
  Camera,
  Home,
  RotateCcw,
  Settings,
  Trophy,
  User,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { logout } from "../../lib/api";
import { useSessionStore } from "../../lib/session-store";
import { streakLabel, useStats } from "../../features/gamification/gamification-api";
import { AvatarImage } from "../../features/profile/AvatarImage";
import { TomiSvg } from "../mascot/Tomi";

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/aprender", label: "Aprender", icon: Home },
  { to: "/diccionario", label: "Diccionario", icon: BookOpen },
  { to: "/camara", label: "Cámara beta", icon: Camera },
  { to: "/repaso", label: "Repasar", icon: RotateCcw },
  { to: "/progreso", label: "Progreso", icon: BarChart3 },
  { to: "/logros", label: "Logros", icon: Trophy },
  { to: "/perfil", label: "Perfil", icon: User },
];

/**
 * Escritorio (§9.7): barra lateral fija de 240 px, contenido central de 720 px como máximo y
 * panel derecho de 320 px, que se oculta por debajo de 1280 px (nunca hay scroll horizontal).
 */
export function AppLayout({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const user = useSessionStore((state) => state.user);
  const { data: stats } = useStats();
  const onLogout = async () => {
    await logout();
    await navigate("/ingresar", { replace: true });
  };
  return (
    <div className="flex min-h-screen bg-[#F5FAF7] font-sans text-[#0E2A2F]">
      <nav
        aria-label="Principal"
        className="sticky top-0 flex h-screen w-60 shrink-0 flex-col gap-1 border-r border-slate-200 bg-white p-4"
      >
        <div className="mb-6 flex items-center gap-2 px-2">
          <TomiSvg size={40} />
          <span className="font-display text-lg font-extrabold leading-tight text-[#047857]">
            Alas de Señas
          </span>
        </div>
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2 font-semibold ${
                isActive ? "bg-emerald-100 text-[#047857]" : "text-[#45606A] hover:bg-slate-100"
              }`
            }
          >
            <Icon aria-hidden="true" size={20} />
            {label}
          </NavLink>
        ))}
        {user?.role === "ADMIN" && (
          // Solo el ADMIN ve la sección (D-030); las páginas también lo comprueban.
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `mt-4 flex items-center gap-3 rounded-xl border-t border-slate-200 px-3 py-2 pt-4 font-semibold ${
                isActive ? "bg-emerald-100 text-[#047857]" : "text-[#45606A] hover:bg-slate-100"
              }`
            }
          >
            <Settings aria-hidden="true" size={20} />
            Administración
          </NavLink>
        )}
        <NavLink to="/creditos" className="mt-auto px-3 py-2 text-sm font-semibold text-[#45606A] underline">
          Créditos
        </NavLink>
      </nav>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-end gap-4 border-b border-slate-200 bg-white px-6 py-3">
          {stats && (
            <div className="mr-auto flex items-center gap-4 font-semibold">
              <span aria-label={`Racha: ${streakLabel(stats.streak.current)}`}>
                🔥 {stats.streak.current}
              </span>
              <span aria-label={`Néctar: ${stats.nectar}`}>🌸 {stats.nectar}</span>
              {stats.hearts.enabled && (
                <span data-testid="hearts" aria-label={`Vidas: ${stats.hearts.current}`}>❤️ {stats.hearts.current}</span>
              )}
            </div>
          )}
          {user ? (
            <>
              <NavLink to="/perfil" className="flex items-center gap-2 font-semibold">
                <AvatarImage size={32} label={`Foto de perfil de ${user.name}`} />
                {user.name}
              </NavLink>
              <button
                type="button"
                onClick={() => void onLogout()}
                className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm font-semibold hover:bg-slate-50"
              >
                Cerrar sesión
              </button>
            </>
          ) : (
            <NavLink
              to="/ingresar"
              className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm font-semibold hover:bg-slate-50"
            >
              Ingresar
            </NavLink>
          )}
        </header>
        <div className="flex flex-1 justify-center gap-6 px-6 py-8">
          {/* Fundido corto al cambiar de sección: se nota que la pantalla cambió. */}
          <main key={pathname} className="w-full max-w-[720px] min-w-0 animate-fade-in">
            {children}
          </main>
          <aside aria-label="Panel lateral" className="hidden w-80 shrink-0 xl:block">
            {aside}
          </aside>
        </div>
      </div>
    </div>
  );
}
