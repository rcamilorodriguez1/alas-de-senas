// Página /logros (tarea 6.4; R5.10; §7.9, §9.1).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import { bearer, errorBody, jsonResponse, makeUser, mockFetch, type FetchHandler } from "../../test/http";
import { containingText } from "../../test/lesson";

type AchievementStatusOut = components["schemas"]["AchievementStatusOut"];
type StatsOut = components["schemas"]["StatsOut"];

const ACHIEVEMENTS = "/api/gamification/achievements";

// Mediodía en Bogotá: la fecha local es la misma en cualquier zona horaria de América.
const UNLOCKED_FIRST_FLAP = "2026-10-15T17:00:00Z";
const UNLOCKED_FIRST_LESSON = "2026-10-20T17:00:00Z";

/** Los 9 logros de §7.9, con 2 desbloqueados. */
const ALL: AchievementStatusOut[] = [
  {
    id: "FIRST_FLAP",
    title: "Primer aleteo",
    description: "Completaste la introducción.",
    icon: "feather",
    nectar: 10,
    unlockedAt: UNLOCKED_FIRST_FLAP,
  },
  {
    id: "FIRST_LESSON",
    title: "Primeras alas",
    description: "Aprobaste tu primera lección.",
    icon: "bird",
    nectar: 10,
    unlockedAt: UNLOCKED_FIRST_LESSON,
  },
  {
    id: "STREAK_3",
    title: "Aleteo constante",
    description: "Racha de 3 días.",
    icon: "flame",
    nectar: 15,
    unlockedAt: null,
  },
  {
    id: "STREAK_7",
    title: "Vuelo de una semana",
    description: "Racha de 7 días.",
    icon: "flame",
    nectar: 30,
    unlockedAt: null,
  },
  {
    id: "NODE_DONE",
    title: "Nodo superado",
    description: "Aprobaste tu primer reto.",
    icon: "flag",
    nectar: 15,
    unlockedAt: null,
  },
  {
    id: "GOLDEN_NODE",
    title: "Nodo dorado",
    description: "Sacaste 100 % en un reto.",
    icon: "star",
    nectar: 20,
    unlockedAt: null,
  },
  {
    id: "MODULE_1",
    title: "Fundamentos dominados",
    description: "Aprobaste todas las lecciones del módulo 1.",
    icon: "trophy",
    nectar: 40,
    unlockedAt: null,
  },
  {
    id: "SIGNS_50",
    title: "Manos que hablan",
    description: "Respondiste bien 50 señas distintas.",
    icon: "hand",
    nectar: 40,
    unlockedAt: null,
  },
  {
    id: "HUMMINGBIRD_EYE",
    title: "Ojo de colibrí",
    description: "20 reconocimientos correctos con la cámara.",
    icon: "eye",
    nectar: 30,
    unlockedAt: null,
  },
];

const STATS: StatsOut = {
  totalXp: 120,
  nectar: 40,
  streak: { current: 2, longest: 2, freezesAvailable: 0, atRisk: false },
  today: { seconds: 60, goalSeconds: 600, xp: 10 },
  hearts: { enabled: true, current: 5, max: 5, nextHeartAt: null },
};

function server(achievements: () => Response): FetchHandler {
  return (r) => {
    if (r.method === "GET" && r.path === ACHIEVEMENTS) return achievements();
    if (r.method === "GET" && r.path === "/api/gamification/stats") return jsonResponse(200, STATS);
    return jsonResponse(404, errorBody(404, "NOT_FOUND", "No encontrado."));
  };
}

function renderAt(path = "/logros") {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function esCO(iso: string): string {
  return new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" });
}

function itemOf(title: string): HTMLElement {
  const main = screen.getByRole("main");
  const item = within(main)
    .getAllByRole("listitem")
    .find((li) => within(li).queryByText(containingText(title)) !== null);
  if (item === undefined) throw new Error(`No hay un logro «${title}»`);
  return item;
}

beforeEach(() => {
  useSessionStore.setState({ accessToken: "t", user: makeUser({ name: "Camilo" }), status: "authenticated" });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

describe("ruta /logros", () => {
  it("está protegida: sin sesión lleva a /ingresar con la ruta para volver", async () => {
    useSessionStore.setState({ accessToken: null, user: null, status: "anonymous" });
    const api = mockFetch(server(() => jsonResponse(200, ALL)));
    const router = renderAt();
    await waitFor(() => expect(router.state.location.pathname).toBe("/ingresar"));
    expect(router.state.location.search).toBe(`?volver=${encodeURIComponent("/logros")}`);
    expect(api.to(ACHIEVEMENTS)).toHaveLength(0);
  });

  it("existe en appRoutes", () => {
    expect(appRoutes.some((r) => r.path === "/logros")).toBe(true);
  });

  it("se muestra dentro del AppLayout (barra lateral con «Logros» activo)", async () => {
    mockFetch(server(() => jsonResponse(200, ALL)));
    renderAt();
    await screen.findByRole("heading", { level: 1, name: "Logros" });
    const nav = screen.getByRole("navigation", { name: "Principal" });
    expect(within(nav).getByRole("link", { name: /Logros/ })).toHaveAttribute("aria-current", "page");
  });
});

describe("AchievementsPage — lista (R5.10, §7.9)", () => {
  it("pide GET /api/gamification/achievements con el token y muestra el título «Logros»", async () => {
    const api = mockFetch(server(() => jsonResponse(200, ALL)));
    renderAt();
    expect(await screen.findByRole("heading", { level: 1, name: "Logros" })).toBeInTheDocument();
    await waitFor(() => expect(api.to(ACHIEVEMENTS, "GET")).toHaveLength(1));
    expect(bearer(api.to(ACHIEVEMENTS, "GET")[0])).toBe("Bearer t");
  });

  it("resume «2 de 9 desbloqueados»", async () => {
    mockFetch(server(() => jsonResponse(200, ALL)));
    renderAt();
    expect(await screen.findByText(containingText("2 de 9 desbloqueados"))).toBeInTheDocument();
  });

  it("muestra un elemento de lista por logro, en el orden del servidor", async () => {
    mockFetch(server(() => jsonResponse(200, ALL)));
    renderAt();
    await screen.findByText(containingText("2 de 9 desbloqueados"));
    const items = within(screen.getByRole("main")).getAllByRole("listitem");
    expect(items).toHaveLength(9);
    ALL.forEach((a, i) => expect(items[i]).toHaveTextContent(a.title));
  });

  it("cada logro muestra título, descripción y su néctar «+N de néctar»", async () => {
    mockFetch(server(() => jsonResponse(200, ALL)));
    renderAt();
    await screen.findByText(containingText("2 de 9 desbloqueados"));
    for (const a of ALL) {
      const item = itemOf(a.title);
      expect(within(item).getByText(containingText(a.description))).toBeInTheDocument();
      expect(within(item).getByText(containingText(`+${a.nectar} de néctar`))).toBeInTheDocument();
    }
  });

  it("desbloqueado: «Desbloqueado el <fecha es-CO>»", async () => {
    mockFetch(server(() => jsonResponse(200, ALL)));
    renderAt();
    await screen.findByText(containingText("2 de 9 desbloqueados"));
    const flap = itemOf("Primer aleteo");
    expect(within(flap).getByText(containingText(`Desbloqueado el ${esCO(UNLOCKED_FIRST_FLAP)}`))).toBeInTheDocument();
    expect(within(flap).queryByText(containingText("Bloqueado"))).not.toBeInTheDocument();
    const lesson = itemOf("Primeras alas");
    expect(
      within(lesson).getByText(containingText(`Desbloqueado el ${esCO(UNLOCKED_FIRST_LESSON)}`)),
    ).toBeInTheDocument();
  });

  it("bloqueado: «Bloqueado» y sin fecha", async () => {
    mockFetch(server(() => jsonResponse(200, ALL)));
    renderAt();
    await screen.findByText(containingText("2 de 9 desbloqueados"));
    const eye = itemOf("Ojo de colibrí");
    expect(within(eye).getByText(containingText("Bloqueado"))).toBeInTheDocument();
    expect(within(eye).queryByText(containingText("Desbloqueado el"))).not.toBeInTheDocument();
  });

  it("sin ninguno desbloqueado: «0 de 9 desbloqueados»", async () => {
    const none = ALL.map((a) => ({ ...a, unlockedAt: null }));
    mockFetch(server(() => jsonResponse(200, none)));
    renderAt();
    expect(await screen.findByText(containingText("0 de 9 desbloqueados"))).toBeInTheDocument();
    expect(within(screen.getByRole("main")).queryByText(containingText("Desbloqueado el"))).not.toBeInTheDocument();
  });
});

describe("AchievementsPage — error de carga", () => {
  it("muestra «No pudimos cargar tus logros.» y «Reintentar» vuelve a pedirlos", async () => {
    const user = userEvent.setup();
    let calls = 0;
    const api = mockFetch(
      server(() => {
        calls += 1;
        return calls === 1
          ? jsonResponse(500, errorBody(500, "INTERNAL_ERROR", "Algo salió mal."))
          : jsonResponse(200, ALL);
      }),
    );
    renderAt();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No pudimos cargar tus logros.");
    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText(containingText("2 de 9 desbloqueados"))).toBeInTheDocument();
    expect(api.to(ACHIEVEMENTS, "GET").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("No pudimos cargar tus logros.")).not.toBeInTheDocument();
  });
});
