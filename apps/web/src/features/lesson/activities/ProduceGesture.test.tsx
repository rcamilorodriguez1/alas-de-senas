// «Produce la seña» en modo gestos (10B.9, anexo A.10): solo si el modelo de gestos conoce la seña.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetGestureLabelsCache } from "../../../camera/holistic/sequence-classifier";
import { resetModelLabelsCache } from "../../../camera/labels";
import type { LessonExercise } from "../lesson-api";
import { ProduceActivity } from "./ProduceActivity";

const exercise: LessonExercise = {
  id: "M1-N1-L1-E07",
  order: 7,
  activity: "PRODUCE",
  type: "PRODUCE",
  scored: false,
  group: 0,
  content: {
    type: "PRODUCE",
    video: { src: "/media/v/hola.mp4", poster: "/media/p/hola.webp", placeholder: false, source: "video" },
    word: "Hola",
    cameraLabel: null,
    gestureLabel: "hola",
  },
};

const meta = (labels: string[]) => ({
  featureVersion: "holistic-v2",
  featureSize: 159,
  frames: 30,
  durationSec: 2,
  threshold: 0.7,
  mean: Array.from({ length: 159 }, () => 0),
  std: Array.from({ length: 159 }, () => 1),
  labels,
});

function stubGestureModel(labels: string[] | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/lsc-gestos/meta.json")) {
        return labels ? new Response(JSON.stringify(meta(labels))) : new Response("", { status: 404 });
      }
      if (url.endsWith("/labels.json")) return new Response(JSON.stringify(["NINGUNA", "letra-a"]));
      return new Response("{}");
    }),
  );
}

beforeEach(() => {
  resetModelLabelsCache();
  resetGestureLabelsCache();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ProduceActivity con gestos", () => {
  it("si el modelo de gestos conoce la seña, ofrece la cámara con aviso de privacidad", async () => {
    stubGestureModel(["NINGUNA", "hola", "adios"]);
    render(<ProduceActivity exercise={exercise} onSubmit={vi.fn()} onContinue={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Usar la cámara" }));
    expect(await screen.findByRole("button", { name: "Activar cámara" }, { timeout: 10000 })).toBeInTheDocument();
    expect(screen.getByText(/tu expresión facial/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sí, me salió" })).toBeInTheDocument();
  });

  it("sin modelo de gestos (o sin la seña) solo hay autoevaluación", async () => {
    stubGestureModel(["NINGUNA", "adios"]);
    render(<ProduceActivity exercise={exercise} onSubmit={vi.fn()} onContinue={vi.fn()} />);
    await screen.findByRole("button", { name: "Sí, me salió" });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("button", { name: "Usar la cámara" })).not.toBeInTheDocument();
  });
});
