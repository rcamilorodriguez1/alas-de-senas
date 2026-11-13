// Colector /admin/gestos (A.6; plan de mejora, paso B, D-045): todas las señas del modelo de movimiento y
// captura de 2 s o manual.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RecordedSample } from "../../camera/holistic/gesture-session";
import { useSessionStore } from "../../lib/session-store";
import { jsonResponse, makeUser, mockFetch } from "../../test/http";
import { GestureDatasetPage } from "./GestureDatasetPage";

const downloadJson = vi.fn();
vi.mock("../../camera/holistic/dataset-v2", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../camera/holistic/dataset-v2")>();
  return { ...actual, downloadJson: (...args: unknown[]) => downloadJson(...args) };
});

const recorded: RecordedSample = {
  frames: Array.from({ length: 30 }, () => new Float32Array(159)),
  quality: { faceRatio: 1, domHandRatio: 1, poseRatio: 1 },
  check: { ok: true },
  switchedHand: false,
};
vi.mock("./GestureCamera", () => ({
  GestureCamera: ({
    manual,
    recordText,
    onRecordStart,
    onSample,
  }: {
    manual?: boolean;
    recordText?: string;
    onRecordStart?: () => void;
    onSample: (sample: RecordedSample) => void;
  }) => (
    <div>
      <p>
        cámara: {recordText} · manual: {String(Boolean(manual))}
      </p>
      <button type="button" onClick={() => onRecordStart?.()}>
        empezar
      </button>
      <button type="button" onClick={() => onSample(recorded)}>
        entregar
      </button>
    </div>
  ),
}));

function renderCollector() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <GestureDatasetPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  useSessionStore.setState({ accessToken: "t", user: makeUser({ role: "ADMIN" }), status: "authenticated" });
  mockFetch((r) =>
    r.path.startsWith("/api/dictionary/signs")
      ? jsonResponse(200, { items: [{ slug: "hola", word: "Hola" }], total: 1, page: 1, pageSize: 24 })
      : jsonResponse(404, { statusCode: 404, code: "NOT_FOUND", message: "x" }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

describe("/admin/gestos", () => {
  it("ofrece todas las señas del modelo de movimiento (las de content/dataset-mapping.csv), sin repetir", async () => {
    renderCollector();
    const select = await screen.findByRole("combobox", { name: "Seña" });
    const values = within(select)
      .getAllByRole("option")
      .map((option) => option.getAttribute("value"));
    for (const slug of ["NINGUNA", "hola", "adios", "si", "no", "numero-6", "numero-10", "con-permiso"]) {
      expect(values, slug).toContain(slug);
    }
    expect(new Set(values).size).toBe(values.length);
    expect(values[0]).toBe("NINGUNA");
  });

  it("graba 2 s por defecto y permite marcar el inicio y el fin", async () => {
    renderCollector();
    expect(await screen.findByText("cámara: Grabar muestra (2 s) · manual: false")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: /Yo marco el inicio y el fin/ }));
    expect(screen.getByText("cámara: Grabar muestra · manual: true")).toBeInTheDocument();
  });

  it("la muestra queda con el alias que había al empezar a grabar, aunque se cambie durante la grabación", async () => {
    downloadJson.mockReset();
    renderCollector();
    await userEvent.type(await screen.findByLabelText("Alias de quien graba"), "equipo-01");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "empezar" }));
    await userEvent.type(screen.getByLabelText("Alias de quien graba"), "-otra");
    await userEvent.click(screen.getByRole("button", { name: "entregar" }));
    await userEvent.click(screen.getByRole("button", { name: "Exportar dataset.json" }));
    const [dataset] = downloadJson.mock.calls[0] as [{ samples: { collector: string }[] }];
    expect(dataset.samples.map((s) => s.collector)).toEqual(["equipo-01"]);
  }, 15_000);
});