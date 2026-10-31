import { render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSessionStore } from "../lib/session-store";
import { deferred, errorBody, jsonResponse, makeAuth, makeUser, mockFetch } from "../test/http";
import { AuthBootstrap } from "./AuthBootstrap";

function App() {
  return (
    <AuthBootstrap>
      <p>Contenido de la app</p>
    </AuthBootstrap>
  );
}

beforeEach(() => {
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AuthBootstrap", () => {
  it("B24: mientras se resuelve el refresh muestra «Cargando…» y NO los hijos (sin parpadeo del login)", async () => {
    const gate = deferred<Response>();
    mockFetch(() => gate.promise);
    render(<App />);

    expect(screen.getByRole("status")).toHaveTextContent("Cargando…");
    expect(screen.queryByText("Contenido de la app")).not.toBeInTheDocument();

    gate.resolve(jsonResponse(200, makeAuth("nuevo")));
    expect(await screen.findByText("Contenido de la app")).toBeInTheDocument();
    expect(screen.queryByText("Cargando…")).not.toBeInTheDocument();
  });

  it("R2.6: con una cookie válida restaura la sesión al recargar", async () => {
    const user = makeUser({ name: "Lucía" });
    const http = mockFetch(() => jsonResponse(200, makeAuth("nuevo", user)));
    render(<App />);

    expect(await screen.findByText("Contenido de la app")).toBeInTheDocument();
    expect(http.to("/api/auth/refresh", "POST")).toHaveLength(1);
    const state = useSessionStore.getState();
    expect(state.status).toBe("authenticated");
    expect(state.accessToken).toBe("nuevo");
    expect(state.user).toEqual(user);
  });

  it("sin sesión (refresh 401) muestra los hijos como anónimo", async () => {
    mockFetch(() => jsonResponse(401, errorBody(401, "UNAUTHORIZED", "Inicia sesión.")));
    render(<App />);

    expect(await screen.findByText("Contenido de la app")).toBeInTheDocument();
    expect(useSessionStore.getState().status).toBe("anonymous");
  });

  it("si la red falla al arrancar, no se queda cargando para siempre", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );
    render(<App />);

    expect(await screen.findByText("Contenido de la app")).toBeInTheDocument();
    expect(useSessionStore.getState().status).toBe("anonymous");
  });

  it("en StrictMode (doble montaje) hace UNA sola petición de refresh", async () => {
    const http = mockFetch(() => jsonResponse(200, makeAuth("nuevo")));
    render(
      <StrictMode>
        <App />
      </StrictMode>,
    );

    expect(await screen.findByText("Contenido de la app")).toBeInTheDocument();
    expect(http.to("/api/auth/refresh")).toHaveLength(1);
  });
});
