import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useSessionStore } from "../lib/session-store";

/** Rutas protegidas: sin sesión, a /ingresar con la ruta para volver. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const status = useSessionStore((state) => state.status);
  const location = useLocation();
  if (status !== "authenticated") {
    const volver = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/ingresar?volver=${volver}`} replace />;
  }
  return <>{children}</>;
}

/** Ingreso y registro: con sesión, directo a la ruta de aprendizaje. */
export function GuestOnly({ children }: { children: ReactNode }) {
  const status = useSessionStore((state) => state.status);
  if (status === "authenticated") return <Navigate to="/aprender" replace />;
  return <>{children}</>;
}
