// Importador /admin/importar (anexo A.7.1, D-044): elegir archivos o carpeta, arrastrar, resumen y reanudar.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import { MemoryProgressStore } from "../../camera/holistic/import-progress";
import { useSessionStore } from "../../lib/session-store";
import { jsonResponse, makeUser, mockFetch } from "../../test/http";

const store = vi.hoisted(() => ({ current: null as MemoryProgressStore | null }));
vi.mock("../../camera/holistic/import-progress", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../camera/holistic/import-progress")>();
  store.current = new actual.MemoryProgressStore();
  return { ...actual, progressStore: store.current };
});

const video = (name: string) => new File(["x"], name, { type: "video/mp4" });
const FILES = [
  video("Hola__lsc54-s2-01__1.mp4"),
  video("Chao__lsc54-s2-01__1.mp4"),
  video("Hola__lsc54-s2-02__1.mp4"),
  video("Bano__lsc54-s2-01__1.mp4"), // «Baño» está en el currículo: fuera del mapeo de LSC-54
  video("nombre-sin-formato.mp4"),
];

function renderImport() {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/admin/importar"] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await store.current?.clear();
  useSessionStore.setState({ accessToken: "t", user: makeUser({ role: "ADMIN" }), status: "authenticated" });
  mockFetch(() => jsonResponse(404, { statusCode: 404, code: "NOT_FOUND", message: "x" }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("/admin/importar", () => {
  it("muestra los botones para elegir archivos o una carpeta y la licencia de la fuente", async () => {
    renderImport();
    expect(await screen.findByRole("button", { name: "Elegir archivos" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Elegir carpeta" })).toBeInTheDocument();
    expect(screen.getByText(/CC BY-NC 4\.0/)).toBeInTheDocument();
    expect(screen.getByTestId("elegir-carpeta").hasAttribute("webkitdirectory")).toBe(true);
  });

  it("al elegir archivos resume cuántos se importarán y cuántos quedan fuera del mapeo", async () => {
    renderImport();
    fireEvent.change(await screen.findByTestId("elegir-archivos"), { target: { files: FILES } });
    expect(
      await screen.findByText("5 archivos · 3 se importarán · 1 fuera del mapeo · 1 con nombre inválido"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Procesar" })).toBeEnabled();
  });

  it("también acepta archivos arrastrados a la zona", async () => {
    renderImport();
    const zone = await screen.findByTestId("zona-soltar");
    fireEvent.dragOver(zone, { dataTransfer: { files: FILES } });
    fireEvent.drop(zone, { dataTransfer: { files: FILES } });
    expect(await screen.findByText(/3 se importarán/)).toBeInTheDocument();
  });

  it("si hay una importación sin terminar, avisa y al volver a elegir los archivos continúa donde iba", async () => {
    await store.current?.start({ source: "LSC-54", license: "CC BY-NC 4.0", faceFeatures: false, total: 3 });
    await store.current?.add({ item: "Chao__lsc54-s2-01__1.mp4", sample: null, reason: "Tu mano salió del cuadro" });
    renderImport();
    expect(await screen.findByText(/Tienes una importación sin terminar: 1 de 3 procesados \(LSC-54\)/)).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("elegir-archivos"), { target: { files: FILES } });
    expect(await screen.findByText(/1 ya procesados/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continuar" })).toBeEnabled();
    expect(screen.getByText(/1 de 3 procesados/)).toBeInTheDocument();
  });

  it("«Descartar progreso» borra lo guardado", async () => {
    const user = userEvent.setup();
    await store.current?.start({ source: "LSC-54", license: "CC BY-NC 4.0", faceFeatures: false, total: 3 });
    await store.current?.add({ item: "Chao__lsc54-s2-01__1.mp4", sample: null, reason: "x" });
    renderImport();
    await user.click(await screen.findByRole("button", { name: "Descartar progreso" }));
    await waitFor(async () => expect(await store.current?.load()).toBeNull());
    expect(screen.queryByText(/importación sin terminar/)).not.toBeInTheDocument();
  });

  it("no es para estudiantes", async () => {
    useSessionStore.setState({ accessToken: "t", user: makeUser({ role: "LEARNER" }), status: "authenticated" });
    renderImport();
    expect(await screen.findByText("Esta página es solo para administradores.")).toBeInTheDocument();
  });
});
