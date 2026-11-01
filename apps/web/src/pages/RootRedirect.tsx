import { Navigate } from "react-router";
import { isIntroCompleted } from "../features/intro/intro-storage";
import { useSessionStore } from "../lib/session-store";

/** `/`: con sesión, a la ruta; sin sesión, a la bienvenida la primera vez (R1.1) y luego al ingreso. */
export function RootRedirect() {
  const status = useSessionStore((state) => state.status);
  if (status === "authenticated") return <Navigate to="/aprender" replace />;
  return <Navigate to={isIntroCompleted() ? "/ingresar" : "/bienvenida"} replace />;
}
