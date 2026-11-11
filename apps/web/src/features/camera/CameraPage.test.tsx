// Cámara beta (tareas 10.3–10.4; R8.1–R8.6).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import { cameraErrorKind, displayLabel, type FrameResult } from "../../camera/session";
import { useSessionStore } from "../../lib/session-store";
import { jsonResponse, makeUser, mockFetch } from "../../test/http";

const stop = vi.fn();
const startCameraSession = vi.fn();

vi.mock("../../camera/session", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../camera/session")>();
  return { ...actual, startCameraSession: (...args: unknown[]) => startCameraSession(...args) };
});

function renderCamera() {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/camara"] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, view };
}

beforeEach(() => {
  stop.mockReset();
  startCameraSession.mockReset();
  useSessionStore.setState({ accessToken: "t", user: makeUser({ role: "ADMIN" }), status: "authenticated" });
  mockFetch(() => jsonResponse(404, { statusCode: 404, code: "NOT_FOUND", message: "x" }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("/camara", () => {
  it("avisa que el video no sale del dispositivo (R8.3)", async () => {
    renderCamera();
    expect(await screen.findByText("Tu video no sale de tu dispositivo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Activar cámara" })).toBeInTheDocument();
  });

  it("permiso denegado: mensaje específico y autoevaluación (R8.4)", async () => {
    const user = userEvent.setup();
    startCameraSession.mockRejectedValue(new DOMException("denied", "NotAllowedError"));
    renderCamera();
    await user.click(await screen.findByRole("button", { name: "Activar cámara" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Necesitamos permiso para usar la cámara");
    await user.click(screen.getByRole("button", { name: "Sí, me salió" }));
    expect(screen.getByText("¡Muy bien! Sigue así.")).toBeInTheDocument();
  });

  it("modo simulado sin errores y aviso «Modelo en entrenamiento» para ADMIN (R8.6)", async () => {
    const user = userEvent.setup();
    startCameraSession.mockResolvedValue({ classifier: { simulated: true }, stop });
    renderCamera();
    await user.click(await screen.findByRole("button", { name: "Activar cámara" }));
    expect(await screen.findByText(/Modelo en entrenamiento/)).toBeInTheDocument();
    expect(screen.getByText("Seña detectada")).toBeInTheDocument();
  });

  it("al salir de la pantalla apaga la cámara (R8.5)", async () => {
    const user = userEvent.setup();
    startCameraSession.mockResolvedValue({ classifier: { simulated: true }, stop });
    const { router } = renderCamera();
    await user.click(await screen.findByRole("button", { name: "Activar cámara" }));
    await screen.findByRole("button", { name: "Apagar cámara" });
    await router.navigate("/diccionario");
    await waitFor(() => expect(stop).toHaveBeenCalled());
  });
});

describe("/camara: pestañas (D-031)", () => {
  it("empieza en «Alfabeto y números»; la otra pestaña es «Señas con movimiento»", async () => {
    renderCamera();
    const alphabet = await screen.findByRole("tab", { name: "Alfabeto y números" });
    expect(alphabet).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Señas con movimiento" })).toHaveAttribute("aria-selected", "false");
  });

  it("cambiar a «Señas con movimiento» apaga la cámara del alfabeto (R8.5)", async () => {
    const user = userEvent.setup();
    startCameraSession.mockResolvedValue({ classifier: { simulated: true }, stop });
    renderCamera();
    await user.click(await screen.findByRole("button", { name: "Activar cámara" }));
    await screen.findByRole("button", { name: "Apagar cámara" });
    await user.click(screen.getByRole("tab", { name: "Señas con movimiento" }));
    await waitFor(() => expect(stop).toHaveBeenCalled());
    // Sin modelo de gestos publicado en la prueba: lo dice en vez de fallar.
    expect(await screen.findByText(/aún no está disponible/)).toBeInTheDocument();
  });
});

describe("/camara: medición de rendimiento (D-038)", () => {
  function sessionWithStats() {
    startCameraSession.mockImplementation(async (_video: HTMLVideoElement, onFrame: (result: FrameResult) => void) => {
      setTimeout(() => onFrame({ points: null, features: null, detected: null, stats: { fps: 29.6, workMs: 12.4 } }));
      return { classifier: { simulated: true }, stop };
    });
  }

  it("a quien administra le muestra los FPS y los milisegundos por cuadro", async () => {
    const user = userEvent.setup();
    sessionWithStats();
    renderCamera();
    await user.click(await screen.findByRole("button", { name: "Activar cámara" }));
    expect(await screen.findByText("29 FPS · 12 ms por cuadro")).toBeInTheDocument();
  });

  it("a un estudiante no le muestra la medición", async () => {
    const user = userEvent.setup();
    useSessionStore.setState({ accessToken: "t", user: makeUser({ role: "LEARNER" }), status: "authenticated" });
    sessionWithStats();
    renderCamera();
    await user.click(await screen.findByRole("button", { name: "Activar cámara" }));
    await screen.findByRole("button", { name: "Apagar cámara" });
    await new Promise((done) => setTimeout(done, 20));
    expect(screen.queryByText(/FPS/)).not.toBeInTheDocument();
  });
});

describe("/camara: salir mientras se enciende (B40, R8.5)", () => {
  it("si sale antes de que termine de encender, la cámara se apaga al terminar", async () => {
    const user = userEvent.setup();
    let resolve: (session: { classifier: { simulated: boolean }; stop: () => void }) => void = () => undefined;
    startCameraSession.mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const { router } = renderCamera();
    await user.click(await screen.findByRole("button", { name: "Activar cámara" }));
    await router.navigate("/diccionario");
    resolve({ classifier: { simulated: true }, stop });
    await waitFor(() => expect(stop).toHaveBeenCalled());
  });
});

describe("apoyo de la cámara", () => {
  it("cada error de la cámara tiene su tipo (§10.4)", () => {
    expect(cameraErrorKind(new DOMException("x", "NotAllowedError"))).toBe("denied");
    expect(cameraErrorKind(new DOMException("x", "NotFoundError"))).toBe("not-found");
    expect(cameraErrorKind(new DOMException("x", "NotReadableError"))).toBe("busy");
    expect(cameraErrorKind(new DOMException("x", "InsecureContextError"))).toBe("insecure");
    expect(cameraErrorKind(new Error("raro"))).toBe("unknown");
  });

  it("muestra las letras como letras", () => {
    expect(displayLabel("letra-a")).toBe("A");
    expect(displayLabel("letra-n-tilde")).toBe("Ñ");
    expect(displayLabel("numero-3")).toBe("3");
    expect(displayLabel("hola")).toBe("hola");
  });
});
