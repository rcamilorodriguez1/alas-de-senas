import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSessionStore } from "../../lib/session-store";
import { emptyResponse, errorBody, jsonResponse, makeUser, mockFetch } from "../../test/http";
import { AppLayout } from "./AppLayout";

const NAV_LINKS = [
  ["Aprender", "/aprender"],
  ["Diccionario", "/diccionario"],
  ["Cámara beta", "/camara"],
  ["Repasar", "/repaso"],
  ["Progreso", "/progreso"],
  ["Logros", "/logros"],
  ["Perfil", "/perfil"],
] as const;

function renderLayout(entry: string) {
  const page = (
    <AppLayout aside={<p>Panel de prueba</p>}>
      <p>Contenido central</p>
    </AppLayout>
  );
  const router = createMemoryRouter(
    [
      { path: "/ingresar", element: <p>Página de ingreso</p> },
      { path: "*", element: page },
    ],
    { initialEntries: [entry] },
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function nav(): HTMLElement {
  return screen.getByRole("navigation", { name: "Principal" });
}

function navLink(label: string): HTMLElement {
  return within(nav()).getByRole("link", { name: new RegExp(label) });
}

let http: ReturnType<typeof mockFetch>;

beforeEach(() => {
  useSessionStore.setState({
    accessToken: "t",
    user: makeUser({ name: "Camilo" }),
    status: "authenticated",
  });
  http = mockFetch((r) =>
    r.path === "/api/auth/logout"
      ? emptyResponse(204)
      : jsonResponse(404, errorBody(404, "NOT_FOUND", "No existe.")),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

describe("AppLayout (§9.7, mockup 3.1)", () => {
  it.each(NAV_LINKS)("la barra lateral enlaza «%s» a %s", (label, href) => {
    renderLayout("/aprender");
    expect(navLink(label)).toHaveAttribute("href", href);
  });

  it("la barra lateral tiene exactamente los 7 enlaces en el orden del mockup", () => {
    renderLayout("/aprender");
    const hrefs = within(nav())
      .getAllByRole("link")
      .map((a) => a.getAttribute("href"));
    expect(hrefs.filter((h) => NAV_LINKS.some(([, href]) => href === h))).toEqual(
      NAV_LINKS.map(([, href]) => href),
    );
  });

  it("marca con aria-current=page solo el enlace de la ruta actual", () => {
    renderLayout("/aprender");
    expect(navLink("Aprender")).toHaveAttribute("aria-current", "page");
    for (const [label] of NAV_LINKS.slice(1)) {
      expect(navLink(label)).not.toHaveAttribute("aria-current", "page");
    }
  });

  it("en /repaso el enlace activo es «Repasar»", () => {
    renderLayout("/repaso");
    expect(navLink("Repasar")).toHaveAttribute("aria-current", "page");
    expect(navLink("Aprender")).not.toHaveAttribute("aria-current", "page");
  });

  it("al pulsar «Diccionario» navega y cambia el enlace activo", async () => {
    const user = userEvent.setup();
    const router = renderLayout("/aprender");
    await user.click(navLink("Diccionario"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/diccionario"));
    expect(navLink("Diccionario")).toHaveAttribute("aria-current", "page");
    expect(navLink("Aprender")).not.toHaveAttribute("aria-current", "page");
  });

  it("pone los hijos dentro de <main>", () => {
    renderLayout("/aprender");
    expect(within(screen.getByRole("main")).getByText("Contenido central")).toBeInTheDocument();
  });

  it("pone `aside` en el panel lateral derecho, fuera de <main>", () => {
    renderLayout("/aprender");
    const aside = screen.getByRole("complementary", { name: "Panel lateral" });
    expect(within(aside).getByText("Panel de prueba")).toBeInTheDocument();
    expect(within(screen.getByRole("main")).queryByText("Panel de prueba")).toBeNull();
  });

  it("la barra superior muestra el nombre del usuario de la sesión", () => {
    renderLayout("/aprender");
    expect(screen.getByText(/Camilo/)).toBeInTheDocument();
  });

  it("«Cerrar sesión» llama a /api/auth/logout y borra la sesión en memoria", async () => {
    const user = userEvent.setup();
    renderLayout("/aprender");
    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    await waitFor(() => expect(http.to("/api/auth/logout", "POST")).toHaveLength(1));
    await waitFor(() => expect(useSessionStore.getState().status).toBe("anonymous"));
    expect(useSessionStore.getState().accessToken).toBeNull();
  });
});
