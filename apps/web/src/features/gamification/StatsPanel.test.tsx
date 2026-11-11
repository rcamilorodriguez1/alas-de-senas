// Panel derecho «Tu día» y barra superior (tarea 6.3; R5.9, R5.11, R5.13–R5.14; §7.5, §7.10, §9).
// Los datos vienen de GET /api/gamification/stats; los tipos, de `api-types.ts` (generado).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppLayout } from "../../components/layout/AppLayout";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import { bearer, deferred, errorBody, jsonResponse, makeUser, mockFetch } from "../../test/http";
import { containingText } from "../../test/lesson";
import { StatsPanel } from "./StatsPanel";

type StatsOut = components["schemas"]["StatsOut"];
type StreakStatsOut = components["schemas"]["StreakStatsOut"];
type TodayOut = components["schemas"]["TodayOut"];
type HeartsOut = components["schemas"]["HeartsOut"];

const STATS = "/api/gamification/stats";
const FREEZE = "/api/gamification/streak-freeze";

/** 2026-11-01 10:00 en Bogotá (UTC−5). */
const NOW = new Date("2026-11-01T15:00:00.000Z");

function makeStats(
  overrides: {
    totalXp?: number;
    nectar?: number;
    streak?: Partial<StreakStatsOut>;
    today?: Partial<TodayOut>;
    hearts?: Partial<HeartsOut>;
  } = {},
): StatsOut {
  return {
    totalXp: overrides.totalXp ?? 1240,
    nectar: overrides.nectar ?? 85,
    streak: { current: 5, longest: 7, freezesAvailable: 0, atRisk: false, ...overrides.streak },
    today: { seconds: 420, goalSeconds: 600, xp: 30, ...overrides.today },
    hearts: { enabled: true, current: 5, max: 5, nextHeartAt: null, ...overrides.hearts },
  };
}

function withProviders(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/aprender"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

function serveStats(stats: StatsOut) {
  return mockFetch((r) =>
    r.method === "GET" && r.path === STATS
      ? jsonResponse(200, stats)
      : jsonResponse(404, errorBody(404, "NOT_FOUND", "No encontrado.")),
  );
}

async function renderPanel(): Promise<HTMLElement> {
  render(withProviders(<StatsPanel />));
  const panel = await screen.findByRole("region", { name: "Tu día" });
  // Espera a que lleguen los datos (la racha siempre se muestra).
  await within(panel).findByText(containingText("de racha"));
  return panel;
}

function hms(text: string): number {
  const match = /(\d+):(\d{2}):(\d{2})/.exec(text);
  if (match === null) throw new Error(`Sin cuenta regresiva H:MM:SS en «${text}»`);
  return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]);
}

beforeEach(() => {
  useSessionStore.setState({ accessToken: "t", user: makeUser({ name: "Camilo" }), status: "authenticated" });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

describe("StatsPanel — carga", () => {
  it("es una sección «Tu día» que pide GET /api/gamification/stats con el token", async () => {
    const api = serveStats(makeStats());
    await renderPanel();
    expect(api.to(STATS, "GET")).toHaveLength(1);
    expect(bearer(api.to(STATS, "GET")[0])).toBe("Bearer t");
  });
});

describe("StatsPanel — racha (R5.5–R5.8, §7.5)", () => {
  it("muestra «5 días de racha» con el icono de la llama", async () => {
    serveStats(makeStats({ streak: { current: 5 } }));
    const panel = await renderPanel();
    expect(within(panel).getByText(containingText("5 días de racha"))).toBeInTheDocument();
    expect(panel.querySelector('img[data-icon="racha"]')).not.toBeNull();
  });

  it("en singular: «1 día de racha»", async () => {
    serveStats(makeStats({ streak: { current: 1, longest: 1 } }));
    const panel = await renderPanel();
    expect(within(panel).getByText(containingText("1 día de racha"))).toBeInTheDocument();
    expect(within(panel).queryByText(containingText("1 días"))).not.toBeInTheDocument();
  });

  it("sin racha: «0 días de racha»", async () => {
    serveStats(makeStats({ streak: { current: 0, longest: 0 } }));
    const panel = await renderPanel();
    expect(within(panel).getByText(containingText("0 días de racha"))).toBeInTheDocument();
  });

  it("si la racha está en riesgo avisa «Tu racha está en riesgo: practica hoy»", async () => {
    serveStats(makeStats({ streak: { current: 4, atRisk: true } }));
    const panel = await renderPanel();
    expect(within(panel).getByText(containingText("Tu racha está en riesgo: practica hoy"))).toBeInTheDocument();
  });

  it("si no está en riesgo no muestra el aviso", async () => {
    serveStats(makeStats({ streak: { current: 4, atRisk: false } }));
    const panel = await renderPanel();
    expect(within(panel).queryByText(containingText("Tu racha está en riesgo"))).not.toBeInTheDocument();
  });
});

describe("StatsPanel — meta diaria (R5.11)", () => {
  function goalBar(panel: HTMLElement): HTMLElement {
    return within(panel).getByRole("progressbar", { name: "Meta diaria" });
  }

  it("7 de 10 minutos: barra al 70 % y texto «7 de 10 min»", async () => {
    serveStats(makeStats({ today: { seconds: 420, goalSeconds: 600 } }));
    const panel = await renderPanel();
    expect(goalBar(panel)).toHaveAttribute("aria-valuenow", "70");
    expect(within(panel).getByText(containingText("7 de 10 min"))).toBeInTheDocument();
  });

  it("trunca, no redondea: 359 s de 600 s → 59 % y «5 de 10 min»", async () => {
    serveStats(makeStats({ today: { seconds: 359, goalSeconds: 600 } }));
    const panel = await renderPanel();
    expect(goalBar(panel)).toHaveAttribute("aria-valuenow", "59");
    expect(within(panel).getByText(containingText("5 de 10 min"))).toBeInTheDocument();
    expect(within(panel).queryByText(containingText("6 de 10 min"))).not.toBeInTheDocument();
  });

  it("superada la meta la barra se queda en 100 y el texto muestra los minutos reales", async () => {
    serveStats(makeStats({ today: { seconds: 900, goalSeconds: 600 } }));
    const panel = await renderPanel();
    expect(goalBar(panel)).toHaveAttribute("aria-valuenow", "100");
    expect(within(panel).getByText(containingText("15 de 10 min"))).toBeInTheDocument();
  });

  it("sin práctica hoy (meta de 5 min): 0 % y «0 de 5 min»", async () => {
    serveStats(makeStats({ today: { seconds: 0, goalSeconds: 300, xp: 0 } }));
    const panel = await renderPanel();
    expect(goalBar(panel)).toHaveAttribute("aria-valuenow", "0");
    expect(within(panel).getByText(containingText("0 de 5 min"))).toBeInTheDocument();
  });
});

describe("StatsPanel — néctar", () => {
  it("muestra «85 de néctar» con el icono de la flor", async () => {
    serveStats(makeStats({ nectar: 85 }));
    const panel = await renderPanel();
    expect(within(panel).getByText(containingText("85 de néctar"))).toBeInTheDocument();
    expect(panel.querySelector('img[data-icon="nectar"]')).not.toBeNull();
  });
});

describe("StatsPanel — vidas (R5.13–R5.14, §7.10)", () => {
  it("con vidas activas y llenas: «5 de 5» con el corazón, sin cuenta regresiva", async () => {
    serveStats(makeStats({ hearts: { enabled: true, current: 5, nextHeartAt: null } }));
    const panel = await renderPanel();
    expect(within(panel).getByText(containingText("5 de 5"))).toBeInTheDocument();
    expect(panel.querySelector('img[data-icon="vida"]')).not.toBeNull();
    expect(within(panel).queryByText(containingText("Próxima vida en"))).not.toBeInTheDocument();
  });

  it("con 3 vidas muestra «3 de 5» y la cuenta regresiva H:MM:SS baja cada segundo", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(NOW);
    // 3 h 25 min 10,5 s: el medio segundo deja margen a floor/ceil.
    const next = new Date(NOW.getTime() + (3 * 3600 + 25 * 60 + 10) * 1000 + 500).toISOString();
    serveStats(makeStats({ hearts: { enabled: true, current: 3, nextHeartAt: next } }));
    const panel = await renderPanel();

    expect(within(panel).getByText(containingText("3 de 5"))).toBeInTheDocument();
    const countdown = await within(panel).findByText(containingText("Próxima vida en"));
    const before = hms(countdown.textContent ?? "");
    expect(["3:25:10", "3:25:11"]).toContain(/\d+:\d{2}:\d{2}/.exec(countdown.textContent ?? "")?.[0]);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    await waitFor(() => {
      const now = within(panel).getByText(containingText("Próxima vida en"));
      expect(hms(now.textContent ?? "")).toBe(before - 1);
    });
  });

  it("con las vidas desactivadas no muestra el contador «de 5»", async () => {
    serveStats(makeStats({ hearts: { enabled: false, current: 5, nextHeartAt: null } }));
    const panel = await renderPanel();
    expect(within(panel).queryByText(containingText("de 5"))).not.toBeInTheDocument();
    expect(panel.querySelector('img[data-icon="vida"]')).toBeNull();
    expect(within(panel).queryByText(containingText("Próxima vida en"))).not.toBeInTheDocument();
  });
});

describe("StatsPanel — protector de racha (R5.9)", () => {
  const BUY = "Comprar protector (50 de néctar)";

  it("muestra «Protectores: 1 de 2» y el botón de compra habilitado", async () => {
    serveStats(makeStats({ streak: { freezesAvailable: 1 } }));
    const panel = await renderPanel();
    expect(within(panel).getByText(containingText("Protectores: 1 de 2"))).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: BUY })).toBeEnabled();
  });

  it("con 2 protectores (el máximo) el botón está deshabilitado", async () => {
    serveStats(makeStats({ nectar: 300, streak: { freezesAvailable: 2 } }));
    const panel = await renderPanel();
    expect(within(panel).getByText(containingText("Protectores: 2 de 2"))).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: BUY })).toBeDisabled();
  });

  it("al comprar hace UN POST streak-freeze y actualiza protectores y néctar con la respuesta, sin esperar otro GET", async () => {
    const user = userEvent.setup();
    const before = makeStats({ nectar: 85, streak: { freezesAvailable: 0 } });
    const after = makeStats({ nectar: 35, streak: { freezesAvailable: 1 } });
    let bought = false;
    // Tras la compra, un GET de stats nunca responde: la interfaz debe usar la respuesta del POST.
    const never = deferred<Response>();
    const api = mockFetch((r) => {
      if (r.method === "GET" && r.path === STATS) return bought ? never.promise : jsonResponse(200, before);
      if (r.method === "POST" && r.path === FREEZE) {
        bought = true;
        return jsonResponse(200, after);
      }
      return jsonResponse(404, errorBody(404, "NOT_FOUND", "No encontrado."));
    });
    const panel = await renderPanel();
    expect(within(panel).getByText(containingText("Protectores: 0 de 2"))).toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: BUY }));

    await waitFor(() => expect(within(panel).getByText(containingText("Protectores: 1 de 2"))).toBeInTheDocument());
    expect(within(panel).getByText(containingText("35 de néctar"))).toBeInTheDocument();
    expect(within(panel).queryByText(containingText("85 de néctar"))).not.toBeInTheDocument();
    expect(api.to(FREEZE, "POST")).toHaveLength(1);
    expect(bearer(api.to(FREEZE, "POST")[0])).toBe("Bearer t");
    expect(within(panel).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("409 NOT_ENOUGH_NECTAR: alerta «No tienes suficiente néctar» y no cambia nada", async () => {
    const user = userEvent.setup();
    const stats = makeStats({ nectar: 20, streak: { freezesAvailable: 0 } });
    mockFetch((r) => {
      if (r.method === "GET" && r.path === STATS) return jsonResponse(200, stats);
      if (r.method === "POST" && r.path === FREEZE) {
        return jsonResponse(409, errorBody(409, "NOT_ENOUGH_NECTAR", "No tienes suficiente néctar"));
      }
      return jsonResponse(404, errorBody(404, "NOT_FOUND", "No encontrado."));
    });
    const panel = await renderPanel();

    await user.click(within(panel).getByRole("button", { name: BUY }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No tienes suficiente néctar");
    expect(within(panel).getByText(containingText("Protectores: 0 de 2"))).toBeInTheDocument();
    expect(within(panel).getByText(containingText("20 de néctar"))).toBeInTheDocument();
  });
});

describe("Barra superior de AppLayout (§9, mockup 3.1)", () => {
  function renderLayout() {
    render(
      withProviders(
        <AppLayout aside={<p>Panel</p>}>
          <p>Contenido</p>
        </AppLayout>,
      ),
    );
    return screen.getByRole("banner");
  }

  it("muestra racha, néctar y vidas de GET /api/gamification/stats", async () => {
    const api = serveStats(makeStats({ nectar: 85, streak: { current: 5 }, hearts: { enabled: true, current: 3 } }));
    const header = renderLayout();
    expect(await within(header).findByLabelText("Racha: 5 días")).toBeInTheDocument();
    expect(within(header).getByLabelText("Néctar: 85")).toBeInTheDocument();
    expect(within(header).getByLabelText("Vidas: 3")).toBeInTheDocument();
    expect(api.to(STATS, "GET").length).toBeGreaterThanOrEqual(1);
  });

  it("con las vidas desactivadas no muestra el contador de vidas", async () => {
    serveStats(makeStats({ nectar: 12, streak: { current: 2 }, hearts: { enabled: false } }));
    const header = renderLayout();
    expect(await within(header).findByLabelText("Racha: 2 días")).toBeInTheDocument();
    expect(within(header).getByLabelText("Néctar: 12")).toBeInTheDocument();
    expect(within(header).queryByLabelText(/^Vidas:/)).not.toBeInTheDocument();
  });
});
