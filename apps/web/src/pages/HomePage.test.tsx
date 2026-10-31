import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomePage } from "./HomePage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <HomePage />
    </QueryClientProvider>,
  );
}

function mockFetch(status: number, body: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status }))),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HomePage", () => {
  it("muestra el nombre de la plataforma en español", () => {
    mockFetch(200, { ok: true, db: true });
    renderPage();
    expect(screen.getByRole("heading", { name: "Alas de Señas" })).toBeInTheDocument();
  });

  it("indica que el servidor funciona cuando /api/health responde", async () => {
    mockFetch(200, { ok: true, db: true });
    renderPage();
    expect(await screen.findByText("Servidor y base de datos funcionando.")).toBeInTheDocument();
  });

  it("avisa cuando la base de datos no responde", async () => {
    mockFetch(503, { ok: false, db: false });
    renderPage();
    expect(
      await screen.findByText("El servidor o la base de datos no responden."),
    ).toBeInTheDocument();
  });
});
