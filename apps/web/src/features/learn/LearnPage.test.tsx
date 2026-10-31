import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { isValidElement, type ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import {
  bearer,
  deferred,
  emptyResponse,
  errorBody,
  jsonResponse,
  makeUser,
  mockFetch,
  type FetchHandler,
} from "../../test/http";
import { LearnPage } from "./LearnPage";

type LearningPathOut = components["schemas"]["LearningPathOut"];
type ModuleOut = components["schemas"]["ModuleOut"];
type NodeSummaryOut = components["schemas"]["NodeSummaryOut"];
type LessonSummaryOut = components["schemas"]["LessonSummaryOut"];
type ProgressStatus = components["schemas"]["ProgressStatus"];

// ---------- Datos de prueba realistas (§6, §7.4) ----------

const LESSONS = [
  { order: 1, type: "LEARN", title: "Aprende", xp: 10 },
  { order: 2, type: "RECOGNIZE", title: "Reconoce", xp: 15 },
  { order: 3, type: "PRACTICE", title: "Practica", xp: 15 },
  { order: 4, type: "CHALLENGE", title: "Reto final", xp: 25 },
] as const;

const ALL_LOCKED: readonly ProgressStatus[] = ["LOCKED", "LOCKED", "LOCKED", "LOCKED"];

function lessons(nodeId: string, statuses: readonly ProgressStatus[]): LessonSummaryOut[] {
  return LESSONS.map((l, i) => {
    const status = statuses[i] ?? "LOCKED";
    const approved = status === "COMPLETED" || status === "GOLDEN";
    return {
      id: `${nodeId}-L${l.order}`,
      order: l.order,
      type: l.type,
      title: l.title,
      status,
      bestScore: status === "GOLDEN" ? 100 : approved ? 80 : null,
      estimatedXp: l.xp,
    };
  });
}

function node(
  id: string,
  order: number,
  title: string,
  status: ProgressStatus,
  lessonStatuses: readonly ProgressStatus[] | null = ALL_LOCKED,
  kind: NodeSummaryOut["kind"] = "STANDARD",
): NodeSummaryOut {
  return {
    id,
    order,
    title,
    kind,
    status,
    lessons: lessonStatuses === null ? [] : lessons(id, lessonStatuses),
  };
}

function lockedModule(order: number, title: string, description: string, titles: string[]): ModuleOut {
  const id = `M${order}`;
  return {
    id,
    order,
    title,
    description,
    published: true,
    status: "LOCKED",
    progress: 0,
    nodes: titles.map((t, i) => node(`${id}-N${i + 1}`, i + 1, t, "LOCKED")),
  };
}

const M2 = lockedModule(2, "Personas y vida cotidiana", "Familia, números y el día a día.", [
  "Familia",
  "Números",
  "La casa",
  "Rutinas",
]);

const M3 = lockedModule(3, "El mundo a mi alrededor", "Colores, comida y lugares.", [
  "Colores",
  "Comida",
  "Lugares",
  "El clima",
]);

/** Módulo no publicado: nodos sin lecciones (R3.6). */
const M4_COMING_SOON: ModuleOut = {
  id: "M4",
  order: 4,
  title: "Comunidad y conversación",
  description: "Conversaciones completas y cultura sorda.",
  published: false,
  status: "COMING_SOON",
  progress: 0,
  nodes: [
    node("M4-N1", 1, "Emociones", "COMING_SOON", null),
    node("M4-N2", 2, "En el médico", "COMING_SOON", null),
    node("M4-N3", 3, "Transporte", "COMING_SOON", null),
    node("M4-N4", 4, "Cultura sorda", "COMING_SOON", null),
  ],
};

const M1_LATER_NODES: NodeSummaryOut[] = [
  node("M1-N3", 3, "Alfabeto A–M", "LOCKED", ALL_LOCKED, "ALPHABET"),
  node("M1-N4", 4, "Alfabeto N–Z", "LOCKED", ALL_LOCKED, "ALPHABET"),
];

function m1(progress: number, n1: NodeSummaryOut, n2: NodeSummaryOut): ModuleOut {
  return {
    id: "M1",
    order: 1,
    title: "Fundamentos de la LSC",
    description: "Saludos, cortesía y alfabeto",
    published: true,
    status: "IN_PROGRESS",
    progress,
    nodes: [n1, n2, ...M1_LATER_NODES],
  };
}

/** M1-N1-L1 aprobada: L2 disponible, el resto bloqueado. */
const PATH_IN_PROGRESS: LearningPathOut = {
  modules: [
    m1(
      6,
      node("M1-N1", 1, "Saludos", "IN_PROGRESS", ["COMPLETED", "AVAILABLE", "LOCKED", "LOCKED"]),
      node("M1-N2", 2, "Presentaciones", "LOCKED"),
    ),
    M2,
    M3,
    M4_COMING_SOON,
  ],
};

/** M1-N1 dorado (reto al 100 %) y M1-N2-L1 disponible. */
const PATH_GOLDEN: LearningPathOut = {
  modules: [
    m1(
      25,
      node("M1-N1", 1, "Saludos", "GOLDEN", ["COMPLETED", "COMPLETED", "COMPLETED", "GOLDEN"]),
      node("M1-N2", 2, "Presentaciones", "IN_PROGRESS", ["AVAILABLE", "LOCKED", "LOCKED", "LOCKED"]),
    ),
    M2,
    M3,
    M4_COMING_SOON,
  ],
};

/** M1-N1 completado (reto aprobado sin 100 %). */
const PATH_COMPLETED_NODE: LearningPathOut = {
  modules: [
    m1(
      25,
      node("M1-N1", 1, "Saludos", "COMPLETED", ["COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED"]),
      node("M1-N2", 2, "Presentaciones", "IN_PROGRESS", ["AVAILABLE", "LOCKED", "LOCKED", "LOCKED"]),
    ),
    M2,
    M3,
    M4_COMING_SOON,
  ],
};

// ---------- Utilidades ----------

const notFound = () => jsonResponse(404, errorBody(404, "NOT_FOUND", "No existe."));

function serve(path: LearningPathOut): FetchHandler {
  return (r) => {
    if (r.path === "/api/learning-path" && r.method === "GET") return jsonResponse(200, path);
    if (r.path === "/api/auth/logout") return emptyResponse(204);
    return notFound();
  };
}

function renderLearn() {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/aprender"] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

async function loaded() {
  await screen.findByRole("heading", { name: "Módulo 1 · Fundamentos de la LSC" });
}

const LESSON_TITLES = LESSONS.map((l) => l.title);

/** Botón de nodo: su nombre incluye el título del nodo y ningún título de lección. */
function nodeButton(title: string): HTMLElement {
  return screen.getByRole("button", {
    name: (n) => n.includes(title) && !LESSON_TITLES.some((t) => n.includes(t)),
  });
}

/** Botones de lección por «{order} · {title}» y, opcionalmente, su estado en texto. */
function lessonButtons(label: string, state?: string): HTMLElement[] {
  return screen.queryAllByRole("button", {
    name: (n) => n.includes(label) && (state === undefined || n.includes(state)),
  });
}

function lessonButton(label: string, state?: string): HTMLElement {
  const found = lessonButtons(label, state);
  expect(found).toHaveLength(1);
  return found[0];
}

function following(a: Node, b: Node): boolean {
  return (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
}

beforeEach(() => {
  useSessionStore.setState({
    accessToken: "t",
    user: makeUser({ name: "Camilo" }),
    status: "authenticated",
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

// ---------- Pruebas ----------

describe("ruta /aprender", () => {
  it("usa LearnPage de features/learn dentro de RequireAuth", () => {
    const route = appRoutes.find((r) => r.path === "/aprender");
    const element: ReactNode = route?.element;
    expect(isValidElement<{ children?: ReactNode }>(element)).toBe(true);
    if (isValidElement<{ children?: ReactNode }>(element)) {
      const child = element.props.children;
      expect(isValidElement(child) && child.type === LearnPage).toBe(true);
    }
  });
});

describe("LearnPage: carga de la ruta", () => {
  it("pide GET /api/learning-path con el token Bearer de la sesión", async () => {
    const http = mockFetch(serve(PATH_IN_PROGRESS));
    renderLearn();
    await loaded();
    const calls = http.to("/api/learning-path", "GET");
    expect(calls.length).toBeGreaterThanOrEqual(1);
    expect(bearer(calls[0])).toBe("Bearer t");
  });

  it("muestra «Cargando tu ruta…» mientras espera", async () => {
    const pending = deferred<Response>();
    mockFetch((r) => (r.path === "/api/learning-path" ? pending.promise : notFound()));
    renderLearn();
    expect(await screen.findByText("Cargando tu ruta…")).toBeInTheDocument();
    pending.resolve(jsonResponse(200, PATH_IN_PROGRESS));
    await loaded();
    expect(screen.queryByText("Cargando tu ruta…")).toBeNull();
  });

  it("si falla muestra «No pudimos cargar tu ruta.» y «Reintentar» vuelve a pedirla", async () => {
    let calls = 0;
    const http = mockFetch((r) => {
      if (r.path !== "/api/learning-path") return notFound();
      calls += 1;
      return calls === 1
        ? jsonResponse(500, errorBody(500, "INTERNAL_ERROR", "Error interno."))
        : jsonResponse(200, PATH_IN_PROGRESS);
    });
    const user = userEvent.setup();
    renderLearn();

    expect(await screen.findByText("No pudimos cargar tu ruta.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /^Módulo 1/ })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    await loaded();
    expect(http.to("/api/learning-path", "GET")).toHaveLength(2);
    expect(screen.queryByText("No pudimos cargar tu ruta.")).toBeNull();
  });

  it("usa el layout de escritorio: «Aprender» activo y la ruta dentro de <main>", async () => {
    mockFetch(serve(PATH_IN_PROGRESS));
    renderLearn();
    await loaded();
    const nav = screen.getByRole("navigation", { name: "Principal" });
    expect(within(nav).getByRole("link", { name: /Aprender/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      within(screen.getByRole("main")).getByRole("heading", {
        name: "Módulo 1 · Fundamentos de la LSC",
      }),
    ).toBeInTheDocument();
  });

  it("el panel lateral muestra a Tomi alegre saludando por el nombre", async () => {
    mockFetch(serve(PATH_IN_PROGRESS));
    renderLearn();
    await loaded();
    const aside = screen.getByRole("complementary", { name: "Panel lateral" });
    expect(within(aside).getByRole("status")).toHaveTextContent("¡Hola, Camilo! Sigue tu ruta.");
    expect(within(aside).getByRole("img", { name: "Tomi, el colibrí" })).toHaveAttribute(
      "data-mood",
      "happy",
    );
  });
});

describe("LearnPage: módulos (R3.1, R3.6)", () => {
  beforeEach(() => {
    mockFetch(serve(PATH_IN_PROGRESS));
  });

  it("muestra los 4 módulos en orden con «Módulo {order} · {title}»", async () => {
    renderLearn();
    await loaded();
    const headings = screen
      .getAllByRole("heading", { name: /^Módulo \d · / })
      .map((h) => h.textContent?.trim());
    expect(headings).toEqual([
      "Módulo 1 · Fundamentos de la LSC",
      "Módulo 2 · Personas y vida cotidiana",
      "Módulo 3 · El mundo a mi alrededor",
      "Módulo 4 · Comunidad y conversación",
    ]);
  });

  it("muestra la descripción de cada módulo", async () => {
    renderLearn();
    await loaded();
    expect(screen.getByText("Saludos, cortesía y alfabeto")).toBeInTheDocument();
    expect(screen.getByText("Familia, números y el día a día.")).toBeInTheDocument();
    expect(screen.getByText("Colores, comida y lugares.")).toBeInTheDocument();
    expect(screen.getByText("Conversaciones completas y cultura sorda.")).toBeInTheDocument();
  });

  it("cada módulo publicado tiene una barra de progreso con su porcentaje", async () => {
    renderLearn();
    await loaded();
    const bars = screen.getAllByRole("progressbar");
    expect(bars.map((b) => b.getAttribute("aria-valuenow"))).toEqual(["6", "0", "0"]);
    expect(screen.getByText("6 %")).toBeInTheDocument();
    expect(screen.getAllByText("0 %")).toHaveLength(2);
  });

  it("el módulo no publicado lleva el sello «Próximamente» y no tiene barra (no cuenta)", async () => {
    renderLearn();
    await loaded();
    const m3 = screen.getByRole("heading", { name: "Módulo 3 · El mundo a mi alrededor" });
    const m4 = screen.getByRole("heading", { name: "Módulo 4 · Comunidad y conversación" });
    const seals = screen.getAllByText("Próximamente");
    // Un único sello, en M4: los módulos bloqueados publicados no lo llevan.
    expect(seals).toHaveLength(1);
    expect(following(m3, seals[0])).toBe(true);
    expect(following(m3, m4)).toBe(true);
    // Barras solo para M1, M2 y M3; ninguna después del encabezado de M4.
    const bars = screen.getAllByRole("progressbar");
    expect(bars).toHaveLength(3);
    expect(bars.some((b) => following(m4, b))).toBe(false);
  });

  it("el módulo «Próximamente» no ofrece botones de nodos ni de lecciones", async () => {
    renderLearn();
    await loaded();
    for (const title of ["Emociones", "En el médico", "Transporte", "Cultura sorda"]) {
      expect(screen.queryByRole("button", { name: new RegExp(title) })).toBeNull();
    }
  });

  it("los módulos bloqueados publicados muestran sus 4 nodos como botones «Bloqueado»", async () => {
    renderLearn();
    await loaded();
    for (const title of ["Familia", "Números", "La casa", "Rutinas", "Colores", "El clima"]) {
      expect(nodeButton(title)).toHaveAccessibleName(/Bloqueado/);
    }
  });
});

describe("LearnPage: nodos (R3.1, R3.5, §9.5)", () => {
  it("muestra los 4 nodos del módulo 1 en orden", async () => {
    mockFetch(serve(PATH_IN_PROGRESS));
    renderLearn();
    await loaded();
    const ordered = ["Saludos", "Presentaciones", "Alfabeto A–M", "Alfabeto N–Z"].map(nodeButton);
    for (let i = 1; i < ordered.length; i += 1) {
      expect(following(ordered[i - 1], ordered[i])).toBe(true);
    }
  });

  it("el nodo en curso dice «En progreso» en texto", async () => {
    mockFetch(serve(PATH_IN_PROGRESS));
    renderLearn();
    await loaded();
    expect(nodeButton("Saludos")).toHaveAccessibleName(/En progreso/);
  });

  it("un nodo bloqueado dice «Bloqueado» con candado, no solo color", async () => {
    mockFetch(serve(PATH_IN_PROGRESS));
    renderLearn();
    await loaded();
    const locked = nodeButton("Presentaciones");
    expect(locked).toHaveAccessibleName(/Bloqueado/);
    const hasLockIcon =
      (locked.textContent ?? "").includes("🔒") || locked.querySelector("svg") !== null;
    expect(hasLockIcon).toBe(true);
  });

  it("un nodo con el reto aprobado dice «Completado»", async () => {
    mockFetch(serve(PATH_COMPLETED_NODE));
    renderLearn();
    await loaded();
    expect(nodeButton("Saludos")).toHaveAccessibleName(/Completado/);
  });

  it("un nodo con el reto al 100 % dice «Dorado» (R3.5)", async () => {
    mockFetch(serve(PATH_GOLDEN));
    renderLearn();
    await loaded();
    expect(nodeButton("Saludos")).toHaveAccessibleName(/Dorado/);
    expect(nodeButton("Presentaciones")).toHaveAccessibleName(/En progreso/);
  });
});

describe("LearnPage: lecciones de un nodo", () => {
  it("al cargar, el nodo con la lección disponible actual aparece desplegado", async () => {
    mockFetch(serve(PATH_IN_PROGRESS));
    renderLearn();
    await loaded();
    expect(lessonButton("1 · Aprende")).toHaveAccessibleName(/Completada/);
    expect(lessonButton("2 · Reconoce")).toHaveAccessibleName(/Disponible/);
    expect(lessonButton("3 · Practica")).toHaveAccessibleName(/Bloqueada/);
    expect(lessonButton("4 · Reto final")).toHaveAccessibleName(/Bloqueada/);
  });

  it("los demás nodos empiezan plegados (solo se ven las 4 lecciones de M1-N1)", async () => {
    mockFetch(serve(PATH_IN_PROGRESS));
    renderLearn();
    await loaded();
    expect(lessonButtons("1 · Aprende")).toHaveLength(1);
    expect(lessonButtons("4 · Reto final")).toHaveLength(1);
  });

  it("al pulsar un nodo se despliegan sus 4 lecciones con su estado", async () => {
    mockFetch(serve(PATH_IN_PROGRESS));
    const user = userEvent.setup();
    renderLearn();
    await loaded();

    await user.click(nodeButton("Presentaciones"));

    expect(lessonButtons("1 · Aprende")).toHaveLength(2);
    expect(lessonButtons("1 · Aprende", "Bloqueada")).toHaveLength(1);
    expect(lessonButtons("2 · Reconoce", "Bloqueada")).toHaveLength(1);
    expect(lessonButtons("3 · Practica", "Bloqueada")).toHaveLength(2);
    expect(lessonButtons("4 · Reto final", "Bloqueada")).toHaveLength(2);
  });

  it("en un nodo dorado el reto dice «Dorada» y las demás «Completada»", async () => {
    mockFetch(serve(PATH_GOLDEN));
    const user = userEvent.setup();
    renderLearn();
    await loaded();
    // Desplegado al cargar: M1-N2, que contiene la lección disponible.
    expect(lessonButton("1 · Aprende", "Disponible")).toBeInTheDocument();
    expect(lessonButtons("4 · Reto final", "Dorada")).toHaveLength(0);

    await user.click(nodeButton("Saludos"));

    expect(lessonButton("4 · Reto final", "Dorada")).toBeInTheDocument();
    expect(lessonButton("1 · Aprende", "Completada")).toBeInTheDocument();
    expect(lessonButton("2 · Reconoce", "Completada")).toBeInTheDocument();
    expect(lessonButton("3 · Practica", "Completada")).toBeInTheDocument();
  });
});

describe("LearnPage: popover de lección (R3.8)", () => {
  beforeEach(() => {
    mockFetch(serve(PATH_IN_PROGRESS));
  });

  it("una lección disponible abre un diálogo con título, XP y «Empezar» a /leccion/{id}", async () => {
    const user = userEvent.setup();
    renderLearn();
    await loaded();
    expect(screen.queryByRole("dialog")).toBeNull();

    await user.click(lessonButton("2 · Reconoce"));

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getAllByText(/Reconoce/).length).toBeGreaterThan(0);
    expect(within(dialog).getByText(/\+15 XP/)).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: /Empezar/ })).toHaveAttribute(
      "href",
      "/leccion/M1-N1-L2",
    );
    expect(within(dialog).queryByText("Esta lección aún está bloqueada")).toBeNull();
  });

  it("una lección completada también ofrece «Empezar» (repetir)", async () => {
    const user = userEvent.setup();
    renderLearn();
    await loaded();
    await user.click(lessonButton("1 · Aprende"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/\+10 XP/)).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: /Empezar/ })).toHaveAttribute(
      "href",
      "/leccion/M1-N1-L1",
    );
  });

  it("una lección bloqueada dice «Esta lección aún está bloqueada» y no ofrece «Empezar»", async () => {
    const user = userEvent.setup();
    renderLearn();
    await loaded();

    await user.click(lessonButton("3 · Practica"));

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getAllByText(/Practica/).length).toBeGreaterThan(0);
    expect(within(dialog).getByText(/\+15 XP/)).toBeInTheDocument();
    expect(within(dialog).getByText("Esta lección aún está bloqueada")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Empezar/ })).toBeNull();
  });

  it("al pulsar «Empezar» navega a /leccion/{id}", async () => {
    const user = userEvent.setup();
    const router = renderLearn();
    await loaded();
    await user.click(lessonButton("2 · Reconoce"));
    await user.click(within(screen.getByRole("dialog")).getByRole("link", { name: /Empezar/ }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/leccion/M1-N1-L2"));
  });

  it("Escape cierra el popover", async () => {
    const user = userEvent.setup();
    renderLearn();
    await loaded();
    await user.click(lessonButton("2 · Reconoce"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("el botón «Cerrar» cierra el popover", async () => {
    const user = userEvent.setup();
    renderLearn();
    await loaded();
    await user.click(lessonButton("3 · Practica"));
    const dialog = screen.getByRole("dialog");

    await user.click(within(dialog).getByRole("button", { name: "Cerrar" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("abrir otra lección reemplaza el popover (solo hay uno abierto)", async () => {
    const user = userEvent.setup();
    renderLearn();
    await loaded();
    await user.click(lessonButton("2 · Reconoce"));
    await user.click(lessonButton("3 · Practica"));
    const dialogs = screen.getAllByRole("dialog");
    expect(dialogs).toHaveLength(1);
    expect(within(dialogs[0]).getByText("Esta lección aún está bloqueada")).toBeInTheDocument();
  });
});
