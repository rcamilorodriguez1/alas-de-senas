import { useEffect, type ReactNode } from "react";
import { refreshSession } from "../lib/api";
import { useSessionStore } from "../lib/session-store";

export function LoadingScreen() {
  return (
    <div
      role="status"
      className="flex min-h-screen items-center justify-center bg-white font-sans text-lg text-slate-600"
    >
      Cargando…
    </div>
  );
}

/** Restaura la sesión con la cookie de renovación antes de mostrar la app (R2.6, B24). */
export function AuthBootstrap({ children }: { children: ReactNode }) {
  const status = useSessionStore((state) => state.status);
  useEffect(() => {
    // refreshSession es single-flight: el doble montaje de StrictMode comparte la petición.
    void refreshSession();
  }, []);
  if (status === "loading") return <LoadingScreen />;
  return <>{children}</>;
}
