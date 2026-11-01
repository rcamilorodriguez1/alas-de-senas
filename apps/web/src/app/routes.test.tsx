import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSessionStore } from "../lib/session-store";
import { emptyResponse, errorBody, jsonResponse, makeUser, mockFetch } from "../test/http";
import { appRoutes } from "./routes";

function renderApp(entry: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [entry] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function signIn(name = "Ana") {
  useSessionStore.getState().setSession("token", makeUser({ name }));
}

function signOut() {
  useSessionStore.getState().clearSession();
}

let http: ReturnType<typeof mockFetch>;

beforeEach(() => {
  useSessionStore.setState(useSessionStore.getInitialState(), true);
  http = mockFetch((r) =>
    r.path === "/api/auth/logout"
      ? emptyResponse(204)
      : jsonResponse(404, errorBody(404, "NOT_FOUND", "No existe.")),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("appRoutes", () => {
  it("/ sin sesión y sin intro lleva a /bienvenida (R1.1)", async () => {
    signOut();
    window.localStorage.removeItem("alas.introCompleted");
    const router = renderApp("/");
    await waitFor(() => expect(router.state.location.pathname).toBe("/bienvenida"));
    expect(screen.getByRole("link", { name: "Ya tengo cuenta" })).toHaveAttribute("href", "/ingresar");
  });

  it("/ sin sesión con el intro completado lleva a /ingresar", async () => {
    signOut();
    window.localStorage.setItem("alas.introCompleted", "1");
    const router = renderApp("/");
    await waitFor(() => expect(router.state.location.pathname).toBe("/ingresar"));
    expect(await screen.findByRole("button", { name: "Ingresar" })).toBeInTheDocument();
  });

  it("/ con sesión lleva a /aprender", async () => {
    signIn("Ana");
    const router = renderApp("/");
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
    expect(await screen.findByText(/Hola, Ana/)).toBeInTheDocument();
  });

  it("/aprender con sesión saluda por el nombre y ofrece «Cerrar sesión»", async () => {
    signIn("Valentina");
    renderApp("/aprender");
    expect(await screen.findByText(/Hola, Valentina/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
  });

  it("/aprender sin sesión redirige a /ingresar?volver=%2Faprender", async () => {
    signOut();
    const router = renderApp("/aprender");
    await waitFor(() => expect(router.state.location.pathname).toBe("/ingresar"));
    expect(router.state.location.search).toBe("?volver=%2Faprender");
    expect(screen.queryByText(/Hola,/)).not.toBeInTheDocument();
  });

  it("/ingresar sin sesión muestra el formulario de ingreso", async () => {
    signOut();
    renderApp("/ingresar");
    expect(await screen.findByRole("button", { name: "Ingresar" })).toBeInTheDocument();
  });

  it("/registro sin sesión muestra el formulario de registro", async () => {
    signOut();
    renderApp("/registro");
    expect(await screen.findByRole("button", { name: "Crear cuenta" })).toBeInTheDocument();
  });

  it("/ingresar con sesión redirige a /aprender", async () => {
    signIn();
    const router = renderApp("/ingresar");
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
  });

  it("/registro con sesión redirige a /aprender", async () => {
    signIn();
    const router = renderApp("/registro");
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
  });

  it("una ruta inexistente muestra «No encontramos esta página»", async () => {
    signOut();
    renderApp("/esto-no-existe");
    expect(await screen.findByText("No encontramos esta página")).toBeInTheDocument();
  });

  it("la página 404 también aparece con sesión", async () => {
    signIn();
    renderApp("/otra/ruta/rara");
    expect(await screen.findByText("No encontramos esta página")).toBeInTheDocument();
  });

  it("«Cerrar sesión» llama a /api/auth/logout, limpia la sesión y lleva a /ingresar", async () => {
    const user = userEvent.setup();
    signIn("Ana");
    const router = renderApp("/aprender");

    await user.click(await screen.findByRole("button", { name: "Cerrar sesión" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/ingresar"));
    expect(http.to("/api/auth/logout", "POST")).toHaveLength(1);
    expect(useSessionStore.getState().status).toBe("anonymous");
    expect(useSessionStore.getState().accessToken).toBeNull();
  });
});
