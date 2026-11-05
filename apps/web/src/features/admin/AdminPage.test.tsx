// Sección «Administración» (D-030): solo el ADMIN la ve; reúne las herramientas de la cámara.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSessionStore } from "../../lib/session-store";
import { errorBody, jsonResponse, makeUser, mockFetch } from "../../test/http";
import { AdminPage } from "./AdminPage";

function renderAdmin() {
  const router = createMemoryRouter([{ path: "/admin", element: <AdminPage /> }], { initialEntries: ["/admin"] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockFetch(() => jsonResponse(404, errorBody(404, "NOT_FOUND", "No existe.")));
});

afterEach(() => {
  vi.unstubAllGlobals();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

describe("AdminPage", () => {
  it("el ADMIN ve las tres herramientas con su enlace", () => {
    useSessionStore.setState({ accessToken: "t", user: makeUser({ role: "ADMIN" }), status: "authenticated" });
    renderAdmin();
    expect(screen.getByRole("heading", { level: 1, name: "Administración" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Colector de gestos/ })).toHaveAttribute("href", "/admin/gestos");
    expect(screen.getByRole("link", { name: /Importar dataset/ })).toHaveAttribute("href", "/admin/importar");
    expect(screen.getByRole("link", { name: /Colector del alfabeto/ })).toHaveAttribute("href", "/admin/dataset");
  });

  it("un usuario que no es ADMIN no ve las herramientas", () => {
    useSessionStore.setState({ accessToken: "t", user: makeUser({ role: "LEARNER" }), status: "authenticated" });
    renderAdmin();
    expect(screen.getByRole("alert")).toHaveTextContent("solo para administradores");
    expect(screen.queryByRole("link", { name: /Colector de gestos/ })).not.toBeInTheDocument();
  });
});
