// Diccionario (tarea 8.2; R7.1–R7.7).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import { bearer, emptyResponse, errorBody, jsonResponse, makeUser, mockFetch, type FetchHandler } from "../../test/http";
import { mockMedia } from "../../test/lesson";

type Schemas = components["schemas"];

const VIDEO: Schemas["VideoRef"] = {
  src: "/media/v/abc.mp4",
  poster: "/media/p/abc.webp",
  placeholder: true,
  source: "placeholder",
};
const SALUDOS = { id: "saludos", name: "Saludos" };
const GRACIAS: Schemas["SignCardOut"] = { slug: "gracias", word: "Gracias", category: SALUDOS, video: VIDEO };
const HOLA: Schemas["SignCardOut"] = { slug: "hola", word: "Hola", category: SALUDOS, video: VIDEO };

function detail(overrides: Partial<Schemas["SignDetailOut"]> = {}): Schemas["SignDetailOut"] {
  return {
    slug: "gracias",
    word: "Gracias",
    meaning: "Expresión de agradecimiento.",
    category: SALUDOS,
    howTo: null,
    usageExample: "Gracias por tu ayuda.",
    video: VIDEO,
    relatedLesson: { id: "M1-N1-L1", title: "Aprende", status: null },
    isFavorite: false,
    ...overrides,
  };
}

function search(items: Schemas["SignCardOut"][], suggestions: Schemas["SuggestionOut"][] = []) {
  return jsonResponse(200, { items, page: 1, pageSize: 24, total: items.length, suggestions });
}

function server(overrides: Partial<Record<string, FetchHandler>> = {}): FetchHandler {
  return (r) => {
    const path = r.path.split("?")[0];
    const custom = overrides[`${r.method} ${path}`];
    if (custom) return custom(r);
    if (path === "/api/dictionary/categories") return jsonResponse(200, [{ ...SALUDOS, count: 2 }]);
    if (path === "/api/dictionary/signs") return search([GRACIAS, HOLA]);
    if (path === "/api/dictionary/signs/gracias") return jsonResponse(200, detail());
    if (path === "/api/dictionary/favorites" && r.method === "GET") return jsonResponse(200, []);
    return jsonResponse(404, errorBody(404, "NOT_FOUND", "No encontrado."));
  };
}

function renderAt(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function anonymous() {
  useSessionStore.setState({ accessToken: null, user: null, status: "anonymous" });
}

function signedIn() {
  useSessionStore.setState({ accessToken: "t", user: makeUser(), status: "authenticated" });
}

beforeEach(() => {
  mockMedia();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("/diccionario", () => {
  it("se puede usar sin iniciar sesión y no pide datos de la cuenta", async () => {
    anonymous();
    const api = mockFetch(server());
    renderAt("/diccionario");
    expect(await screen.findByRole("link", { name: /Gracias/ })).toHaveAttribute("href", "/diccionario/gracias");
    expect(screen.getByRole("link", { name: "Crear cuenta" })).toBeInTheDocument();
    expect(api.requests.some((r) => r.path.startsWith("/api/gamification"))).toBe(false);
    expect(api.requests.some((r) => r.path.startsWith("/api/dictionary/favorites"))).toBe(false);
    expect(api.requests.some((r) => r.path.startsWith("/api/reviews"))).toBe(false);
  });

  it("busca lo que se escribe (después de una pausa) y lo deja en la URL", async () => {
    anonymous();
    const user = userEvent.setup();
    const api = mockFetch(server());
    const router = renderAt("/diccionario");
    await user.type(await screen.findByRole("searchbox", { name: "Buscar una palabra" }), "GRACÍAS");
    await waitFor(() => expect(router.state.location.search).toContain("q=GRAC"));
    await waitFor(() =>
      expect(api.requests.some((r) => r.path.includes("q=GRAC%C3%8DAS"))).toBe(true),
    );
  });

  it("sin resultados sugiere palabras parecidas", async () => {
    anonymous();
    mockFetch(
      server({ "GET /api/dictionary/signs": () => search([], [{ slug: "gracias", word: "Gracias" }]) }),
    );
    renderAt("/diccionario?q=grasias");
    expect(await screen.findByText("No encontramos «grasias».")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Gracias" })).toHaveAttribute("href", "/diccionario/gracias");
  });

  it("filtra por categoría con las categorías que tienen señas", async () => {
    anonymous();
    const user = userEvent.setup();
    const api = mockFetch(server());
    renderAt("/diccionario");
    const select = await screen.findByRole("combobox", { name: "Categoría" });
    await screen.findByRole("option", { name: "Saludos (2)" });
    await user.selectOptions(select, "saludos");
    await waitFor(() => expect(api.requests.some((r) => r.path.includes("category=saludos"))).toBe(true));
  });

  it("con sesión muestra la sección de favoritos", async () => {
    signedIn();
    mockFetch(server({ "GET /api/dictionary/favorites": () => jsonResponse(200, [HOLA]) }));
    renderAt("/diccionario");
    expect(await screen.findByRole("heading", { name: "Tus favoritos" })).toBeInTheDocument();
  });
});

describe("/diccionario/:slug", () => {
  it("muestra video, significado, «Descripción en revisión», ejemplo y práctica rápida", async () => {
    anonymous();
    const user = userEvent.setup();
    mockFetch(server());
    renderAt("/diccionario/gracias");
    expect(await screen.findByRole("heading", { name: "Gracias" })).toBeInTheDocument();
    expect(screen.getByLabelText("Video de la seña Gracias")).toBeInTheDocument();
    expect(screen.getByText("Expresión de agradecimiento.")).toBeInTheDocument();
    expect(screen.getByText("Descripción en revisión")).toBeInTheDocument();
    expect(screen.getByText("Gracias por tu ayuda.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "«Aprende»" })).toHaveAttribute("href", "/leccion/M1-N1-L1");
    expect(screen.queryByRole("button", { name: "Guardar en favoritos" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sí, me salió" }));
    expect(screen.getByText("¡Muy bien! Sigue así.")).toBeInTheDocument();
  });

  it("si la lección está bloqueada lo indica y no la enlaza", async () => {
    signedIn();
    mockFetch(
      server({
        "GET /api/dictionary/signs/gracias": () =>
          jsonResponse(200, detail({ relatedLesson: { id: "M1-N2-L1", title: "Aprende", status: "LOCKED" } })),
      }),
    );
    renderAt("/diccionario/gracias");
    expect(await screen.findByText("(bloqueada por ahora)")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "«Aprende»" })).not.toBeInTheDocument();
  });

  it("guarda y quita favoritos con sesión", async () => {
    signedIn();
    const user = userEvent.setup();
    let favorite = false;
    const api = mockFetch(
      server({
        "GET /api/dictionary/signs/gracias": () => jsonResponse(200, detail({ isFavorite: favorite })),
        "POST /api/dictionary/favorites/gracias": () => {
          favorite = true;
          return emptyResponse(204);
        },
        "DELETE /api/dictionary/favorites/gracias": () => {
          favorite = false;
          return emptyResponse(204);
        },
      }),
    );
    renderAt("/diccionario/gracias");
    await user.click(await screen.findByRole("button", { name: "Guardar en favoritos" }));
    const remove = await screen.findByRole("button", { name: "Quitar de favoritos" });
    expect(remove).toHaveFocus(); // no se pierde el foco mientras guarda
    expect(bearer(api.to("/api/dictionary/favorites/gracias", "POST")[0])).toBe("Bearer t");
    await user.click(remove);
    expect(await screen.findByRole("button", { name: "Guardar en favoritos" })).toBeInTheDocument();
    expect(api.to("/api/dictionary/favorites/gracias", "DELETE")).toHaveLength(1);
  });

  it("una seña que no existe muestra un aviso", async () => {
    anonymous();
    mockFetch(
      server({
        "GET /api/dictionary/signs/nada": () =>
          jsonResponse(404, errorBody(404, "SIGN_NOT_FOUND", "No encontramos esta seña.")),
      }),
    );
    renderAt("/diccionario/nada");
    expect(await screen.findByRole("alert")).toHaveTextContent("No encontramos esta seña.");
  });
});
