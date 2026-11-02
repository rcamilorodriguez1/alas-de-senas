// Perfil (D-022): datos editables, resumen y privacidad (Ley 1581 de 2012).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import { useSessionStore } from "../../lib/session-store";
import { emptyResponse, errorBody, jsonResponse, makeUser, mockFetch, type FetchHandler } from "../../test/http";

const STATS = {
  totalXp: 120,
  nectar: 35,
  streak: { current: 3, longest: 7, freezesAvailable: 1, atRisk: false },
  today: { seconds: 0, goalSeconds: 600, xp: 0 },
  hearts: { enabled: true, current: 5, max: 5, nextHeartAt: null },
};
const SUMMARY = { percent: 10, modules: [], totalXp: 120, streak: 3, signsLearned: 9 };

function server(overrides: Partial<Record<string, FetchHandler>> = {}): FetchHandler {
  return (r) => {
    const custom = overrides[`${r.method} ${r.path}`];
    if (custom) return custom(r);
    if (r.path === "/api/gamification/stats") return jsonResponse(200, STATS);
    if (r.path === "/api/progress/summary") return jsonResponse(200, SUMMARY);
    if (r.path === "/api/gamification/achievements") {
      return jsonResponse(200, [
        { id: "A", title: "A", description: "", icon: "x", nectar: 10, unlockedAt: "2026-11-01T10:00:00Z" },
        { id: "B", title: "B", description: "", icon: "x", nectar: 10, unlockedAt: null },
      ]);
    }
    if (r.path === "/api/reviews/queue") return jsonResponse(200, { due: 0, signs: [] });
    return jsonResponse(404, errorBody(404, "NOT_FOUND", "No encontrado."));
  };
}

function renderProfile() {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/perfil"] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

beforeEach(() => {
  useSessionStore.setState({
    accessToken: "t",
    user: makeUser({ name: "Ana", dailyGoalMinutes: 10, dominantHand: "right" }),
    status: "authenticated",
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("/perfil", () => {
  it("muestra el resumen con XP, rachas, néctar, señas aprendidas y logros", async () => {
    mockFetch(server());
    renderProfile();
    expect(await screen.findByRole("heading", { name: "Perfil" })).toBeInTheDocument();
    expect(await screen.findByText("120")).toBeInTheDocument();
    expect(screen.getByText("7 días")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(await screen.findByText("1 de 2")).toBeInTheDocument();
  });

  it("guarda nombre, meta y mano dominante con PATCH /me y actualiza la sesión", async () => {
    const user = userEvent.setup();
    const api = mockFetch(
      server({
        "PATCH /api/me": (r) =>
          jsonResponse(200, { ...makeUser(), ...(r.body as object), id: makeUser().id, email: makeUser().email }),
      }),
    );
    renderProfile();
    const name = await screen.findByRole("textbox", { name: "Nombre" });
    await user.clear(name);
    await user.type(name, "Ana María");
    await user.click(screen.getByRole("radio", { name: "15 min" }));
    await user.click(screen.getByRole("radio", { name: "Izquierda" }));
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect(await screen.findByText("Cambios guardados.")).toBeInTheDocument();
    expect(api.to("/api/me", "PATCH")[0].body).toEqual({
      name: "Ana María",
      dailyGoalMinutes: 15,
      dominantHand: "left",
    });
    expect(useSessionStore.getState().user?.name).toBe("Ana María");
  });

  it("enlaza la política de tratamiento de datos", async () => {
    mockFetch(server());
    renderProfile();
    expect(await screen.findByRole("link", { name: "Política de tratamiento de datos" })).toHaveAttribute(
      "href",
      "/privacidad",
    );
  });

  it("eliminar la cuenta pide escribir ELIMINAR y la contraseña", async () => {
    const user = userEvent.setup();
    const api = mockFetch(server({ "DELETE /api/me": () => emptyResponse(204) }));
    const router = renderProfile();
    await user.click(await screen.findByRole("button", { name: "Quiero eliminar mi cuenta" }));
    const confirm = screen.getByRole("button", { name: "Eliminar definitivamente" });

    await user.click(confirm);
    expect(api.to("/api/me", "DELETE")).toHaveLength(0); // sin confirmar no se envía nada

    await user.type(screen.getByLabelText("Escribe ELIMINAR para confirmar"), "ELIMINAR");
    await user.type(screen.getByLabelText("Tu contraseña"), "Clave-Segura-1");
    await user.click(confirm);

    await waitFor(() => expect(router.state.location.pathname).toBe("/bienvenida"));
    expect(api.to("/api/me", "DELETE")[0].body).toEqual({ password: "Clave-Segura-1" });
    expect(useSessionStore.getState().status).toBe("anonymous");
  });

  it("con contraseña incorrecta avisa y no cierra la sesión", async () => {
    const user = userEvent.setup();
    mockFetch(
      server({
        "DELETE /api/me": () => jsonResponse(403, errorBody(403, "WRONG_PASSWORD", "La contraseña no es correcta.")),
      }),
    );
    renderProfile();
    await user.click(await screen.findByRole("button", { name: "Quiero eliminar mi cuenta" }));
    await user.type(screen.getByLabelText("Escribe ELIMINAR para confirmar"), "ELIMINAR");
    await user.type(screen.getByLabelText("Tu contraseña"), "otra");
    await user.click(screen.getByRole("button", { name: "Eliminar definitivamente" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La contraseña no es correcta.");
    expect(useSessionStore.getState().status).toBe("authenticated");
  });
});

describe("/privacidad", () => {
  it("es pública y explica qué se guarda y los derechos", async () => {
    useSessionStore.setState({ accessToken: null, user: null, status: "anonymous" });
    mockFetch(server());
    const router = createMemoryRouter(appRoutes, { initialEntries: ["/privacidad"] });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Política de tratamiento de datos" })).toBeInTheDocument();
    expect(screen.getByText(/tu video y tus imágenes no salen de tu dispositivo/)).toBeInTheDocument();
  });
});
