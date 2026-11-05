// «Señas con movimiento» en Cámara beta (D-031): práctica libre con el modelo de gestos.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RecordedSample } from "../../camera/holistic/gesture-session";
import { useSessionStore } from "../../lib/session-store";
import { jsonResponse, makeUser, mockFetch } from "../../test/http";
import { GesturePractice } from "./GesturePractice";

const classify = vi.fn();
const dispose = vi.fn();
const loadSequenceClassifier = vi.fn();
vi.mock("../../camera/holistic/sequence-classifier", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../camera/holistic/sequence-classifier")>();
  return { ...actual, loadSequenceClassifier: () => loadSequenceClassifier() };
});

// La cámara real necesita MediaPipe: aquí un botón entrega una grabación ya hecha.
const sample = (ok: boolean): RecordedSample => ({
  frames: [],
  quality: { faceRatio: 1, domHandRatio: 1, poseRatio: 1 },
  check: ok ? { ok: true } : { ok: false, reason: "Tu mano salió del cuadro." },
  switchedHand: false,
});
vi.mock("./GestureCamera", () => ({
  GestureCamera: ({ onSample, requireFace }: { onSample: (s: RecordedSample) => void; requireFace: boolean }) => (
    <div>
      <p>cara exigida: {String(requireFace)}</p>
      <button type="button" onClick={() => onSample(sample(true))}>
        simular seña
      </button>
      <button type="button" onClick={() => onSample(sample(false))}>
        simular seña mala
      </button>
    </div>
  ),
}));

const model = {
  labels: ["NINGUNA", "adios", "hola"],
  meta: { faceFeatures: false, labels: ["NINGUNA", "adios", "hola"], prototypes: {} },
  classify,
  dispose,
};

let posted: unknown[] = [];

function renderPractice() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <GesturePractice />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  classify.mockReset();
  dispose.mockReset();
  loadSequenceClassifier.mockReset();
  posted = [];
  useSessionStore.setState({ accessToken: "t", user: makeUser(), status: "authenticated" });
  mockFetch((r) => {
    if (r.path === "/api/recognition/results") {
      posted.push(r.body);
      return jsonResponse(200, {});
    }
    if (r.path.startsWith("/api/dictionary/signs")) {
      return jsonResponse(200, {
        items: [
          { slug: "hola", word: "Hola" },
          { slug: "adios", word: "Adiós" },
        ],
        total: 2,
        page: 1,
        pageSize: 24,
      });
    }
    return jsonResponse(404, { statusCode: 404, code: "NOT_FOUND", message: "x" });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

describe("GesturePractice", () => {
  it("lista las señas que conoce el modelo y no exige la cara si el modelo no la usa", async () => {
    loadSequenceClassifier.mockResolvedValue(model);
    renderPractice();
    expect(await screen.findByText(/conoce 2 señas/)).toBeInTheDocument();
    expect(await screen.findByText("Hola")).toBeInTheDocument();
    expect(screen.getByText("Adiós")).toBeInTheDocument();
    expect(screen.getByText("cara exigida: false")).toBeInTheDocument();
  });

  it("muestra la seña reconocida con su confianza y la reporta al servidor", async () => {
    loadSequenceClassifier.mockResolvedValue(model);
    classify.mockReturnValue({ label: "hola", confidence: 0.91 });
    renderPractice();
    await userEvent.click(await screen.findByRole("button", { name: "simular seña" }));
    expect(await screen.findByText(/¡Eso es «Hola»!/)).toBeInTheDocument();
    expect(screen.getByText("Confianza: 91 %")).toBeInTheDocument();
    expect(posted).toEqual([{ signId: "hola", correct: true, confidence: 0.91 }]);
  });

  it("si no es ninguna de las señas conocidas, lo dice y no reporta nada", async () => {
    loadSequenceClassifier.mockResolvedValue(model);
    classify.mockReturnValue({ label: "NINGUNA", confidence: 0.4 });
    renderPractice();
    await userEvent.click(await screen.findByRole("button", { name: "simular seña" }));
    expect(await screen.findByText(/No reconocí ninguna de las señas/)).toBeInTheDocument();
    expect(posted).toEqual([]);
  });

  it("una grabación que no pasa el control de calidad explica el motivo", async () => {
    loadSequenceClassifier.mockResolvedValue(model);
    renderPractice();
    await userEvent.click(await screen.findByRole("button", { name: "simular seña mala" }));
    expect(await screen.findByText(/Tu mano salió del cuadro/)).toBeInTheDocument();
    expect(classify).not.toHaveBeenCalled();
  });

  it("sin modelo de gestos publicado, avisa y no ofrece la cámara", async () => {
    loadSequenceClassifier.mockResolvedValue(null);
    renderPractice();
    expect(await screen.findByText(/aún no está disponible/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "simular seña" })).not.toBeInTheDocument();
  });

  it("al salir libera la memoria del modelo", async () => {
    loadSequenceClassifier.mockResolvedValue(model);
    const view = renderPractice();
    await screen.findByText(/conoce 2 señas/);
    view.unmount();
    await vi.waitFor(() => expect(dispose).toHaveBeenCalled());
  });
});
