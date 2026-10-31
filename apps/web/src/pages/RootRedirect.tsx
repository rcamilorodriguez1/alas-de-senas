import { Navigate } from "react-router";
import { useSessionStore } from "../lib/session-store";

export function RootRedirect() {
  const status = useSessionStore((state) => state.status);
  return <Navigate to={status === "authenticated" ? "/aprender" : "/ingresar"} replace />;
}
