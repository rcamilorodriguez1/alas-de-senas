import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";
import { setSessionExpiredHandler } from "../lib/api";
import { createQueryClient } from "../lib/query-client";
import { AuthBootstrap } from "./AuthBootstrap";
import { appRoutes } from "./routes";

const router = createBrowserRouter(appRoutes);

// Sesión vencida y sin renovación posible: volver a ingresar y regresar después (§9.2).
setSessionExpiredHandler((volver) => {
  void router.navigate(`/ingresar?volver=${encodeURIComponent(volver)}`, { replace: true });
});

export function App() {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <AuthBootstrap>
        <RouterProvider router={router} />
      </AuthBootstrap>
    </QueryClientProvider>
  );
}
