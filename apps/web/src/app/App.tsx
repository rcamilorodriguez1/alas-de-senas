import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";
import { setSessionExpiredHandler } from "../lib/api";
import { createQueryClient } from "../lib/query-client";
import { safeReturnPath } from "../lib/navigation";
import { useSessionStore } from "../lib/session-store";
import { AuthBootstrap } from "./AuthBootstrap";
import { appRoutes } from "./routes";

const router = createBrowserRouter(appRoutes);

// Sesión vencida y sin renovación posible: volver a ingresar y regresar después (§9.2).
setSessionExpiredHandler((volver) => {
  const target = safeReturnPath(volver);
  const query = target === "/aprender" ? "" : `?volver=${encodeURIComponent(target)}`;
  void router.navigate(`/ingresar${query}`, { replace: true });
});

export function App() {
  const [queryClient] = useState(createQueryClient);
  // Al cerrar o perder la sesión no deben quedar en caché datos del usuario anterior.
  useEffect(
    () =>
      useSessionStore.subscribe((state, previous) => {
        if (previous.status === "authenticated" && state.status !== "authenticated") {
          queryClient.clear();
        }
      }),
    [queryClient],
  );
  return (
    <QueryClientProvider client={queryClient}>
      <AuthBootstrap>
        <RouterProvider router={router} />
      </AuthBootstrap>
    </QueryClientProvider>
  );
}
