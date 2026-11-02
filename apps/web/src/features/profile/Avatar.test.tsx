// Foto de perfil (D-023): subir, rechazar archivos que no son imagen, mostrar y quitar.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import { useSessionStore } from "../../lib/session-store";
import { errorBody, jsonResponse, makeUser, mockFetch, type FetchHandler } from "../../test/http";

const UPDATED = "2026-11-02T15:00:00Z";

// jsdom no tiene canvas: la reducción a 256×256 se sustituye por un resultado conocido.
vi.mock("./avatar-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./avatar-api")>();
  return {
    ...actual,
    uploadAvatar: (file: File) => actual.uploadAvatar(file, async () => btoa("foto-reducida")),
  };
});

function server(overrides: Partial<Record<string, FetchHandler>> = {}): FetchHandler {
  return (r) => {
    const custom = overrides[`${r.method} ${r.path}`];
    if (custom) return custom(r);
    if (r.path === "/api/me/avatar" && r.method === "GET") {
      // Cuerpo de texto: el Blob de jsdom no es compatible con el Response de Node.
      return new Response("webp", { status: 200, headers: { "Content-Type": "image/webp" } });
    }
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
}

beforeEach(() => {
  useSessionStore.setState({ accessToken: "t", user: makeUser({ avatarUpdatedAt: null }), status: "authenticated" });
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:foto");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Foto de perfil", () => {
  it("subir una foto la envía reducida (base64) y la muestra", async () => {
    const user = userEvent.setup();
    const api = mockFetch(
      server({
        "PUT /api/me/avatar": () => jsonResponse(200, makeUser({ avatarUpdatedAt: UPDATED })),
      }),
    );
    renderAt("/perfil");
    const file = new File(["contenido"], "yo.jpg", { type: "image/jpeg" });
    await user.upload(await screen.findByLabelText("Subir foto"), file);

    expect(await screen.findByText("Foto actualizada.")).toBeInTheDocument();
    const body = api.to("/api/me/avatar", "PUT")[0].body as { image: string };
    expect(atob(body.image)).toBe("foto-reducida");
    expect(useSessionStore.getState().user?.avatarUpdatedAt).toBe(UPDATED);
    await waitFor(() =>
      expect(screen.getByRole("img", { name: "Tu foto de perfil" })).toHaveAttribute("src", "blob:foto"),
    );
  });

  it("un archivo que no es imagen se rechaza sin enviar nada", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const api = mockFetch(server());
    renderAt("/perfil");
    await user.upload(
      await screen.findByLabelText("Subir foto"),
      new File(["%PDF"], "doc.pdf", { type: "application/pdf" }),
    );
    expect(await screen.findByText("Usa una imagen JPG, PNG o WebP.")).toBeInTheDocument();
    expect(api.to("/api/me/avatar", "PUT")).toHaveLength(0);
  });

  it("con foto, la barra superior la muestra y se puede quitar desde el perfil", async () => {
    useSessionStore.setState({ user: makeUser({ avatarUpdatedAt: UPDATED }) });
    const user = userEvent.setup();
    const api = mockFetch(
      server({ "DELETE /api/me/avatar": () => jsonResponse(200, makeUser({ avatarUpdatedAt: null })) }),
    );
    renderAt("/perfil");
    await waitFor(() =>
      expect(screen.getByRole("img", { name: /Foto de perfil de/ })).toHaveAttribute("src", "blob:foto"),
    );
    await user.click(await screen.findByRole("button", { name: "Quitar foto" }));
    await waitFor(() => expect(api.to("/api/me/avatar", "DELETE")).toHaveLength(1));
    expect(await screen.findByText("Quitamos tu foto.")).toBeInTheDocument();
    expect(useSessionStore.getState().user?.avatarUpdatedAt).toBeNull();
  });
});
