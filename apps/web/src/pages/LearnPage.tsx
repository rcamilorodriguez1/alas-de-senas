import { useNavigate } from "react-router";
import { logout } from "../lib/api";
import { useSessionStore } from "../lib/session-store";

/** Provisional hasta el Grupo 4 (ruta de aprendizaje). */
export function LearnPage() {
  const navigate = useNavigate();
  const user = useSessionStore((state) => state.user);
  const onLogout = async () => {
    await logout();
    await navigate("/ingresar", { replace: true });
  };
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-white p-8 font-sans text-slate-800">
      <h1 className="font-display text-4xl font-extrabold text-tomi-600">Hola, {user?.name}</h1>
      <p className="text-lg">Tu ruta de aprendizaje llega pronto.</p>
      <button
        type="button"
        onClick={() => void onLogout()}
        className="rounded-xl border border-slate-300 px-5 py-2 font-semibold hover:bg-slate-50"
      >
        Cerrar sesión
      </button>
    </main>
  );
}
