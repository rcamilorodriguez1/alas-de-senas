// Créditos (D-044): cada dataset de content/datasets.csv aparece con su licencia, cita y enlace.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../app/routes";
import { DATASETS } from "../camera/holistic/datasets";
import { jsonResponse, mockFetch } from "../test/http";

function renderCredits() {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/creditos"] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockFetch(() => jsonResponse(401, { statusCode: 401, code: "UNAUTHORIZED", message: "x" }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("/creditos", () => {
  it("lista cada dataset registrado con su licencia, cita y enlace", async () => {
    renderCredits();
    const section = await screen.findByRole("region", { name: "Datasets de la cámara" });
    expect(DATASETS.length).toBeGreaterThanOrEqual(2);
    for (const dataset of DATASETS) {
      const item = within(section).getByRole("listitem", { name: dataset.source });
      expect(within(item).getByText(dataset.license)).toBeInTheDocument();
      expect(within(item).getByText(dataset.citation)).toBeInTheDocument();
      expect(within(item).getByRole("link")).toHaveAttribute("href", dataset.link);
    }
  });
});
