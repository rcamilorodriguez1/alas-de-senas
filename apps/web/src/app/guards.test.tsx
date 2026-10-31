import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";
import { useSessionStore } from "../lib/session-store";
import { makeUser } from "../test/http";
import { GuestOnly, RequireAuth } from "./guards";

function WhereAmI({ label }: { label: string }) {
  const location = useLocation();
  return (
    <p>
      {label}: {location.pathname}
      {location.search}
    </p>
  );
}

function renderAt(entry: string) {
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route
          path="/aprender"
          element={
            <RequireAuth>
              <p>Contenido privado</p>
            </RequireAuth>
          }
        />
        <Route
          path="/leccion/:lessonId"
          element={
            <RequireAuth>
              <p>Lección privada</p>
            </RequireAuth>
          }
        />
        <Route
          path="/ingresar"
          element={
            <GuestOnly>
              <WhereAmI label="Formulario de ingreso" />
            </GuestOnly>
          }
        />
        <Route
          path="/registro"
          element={
            <GuestOnly>
              <p>Formulario de registro</p>
            </GuestOnly>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

function signIn() {
  useSessionStore.getState().setSession("token", makeUser());
}

function signOut() {
  useSessionStore.getState().clearSession();
}

beforeEach(() => {
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

describe("RequireAuth", () => {
  it("con sesión muestra los hijos", () => {
    signIn();
    renderAt("/aprender");
    expect(screen.getByText("Contenido privado")).toBeInTheDocument();
  });

  it("sin sesión redirige a /ingresar?volver=<ruta actual codificada>", () => {
    signOut();
    renderAt("/leccion/M1-N1-L2");
    expect(screen.queryByText("Lección privada")).not.toBeInTheDocument();
    expect(
      screen.getByText("Formulario de ingreso: /ingresar?volver=%2Fleccion%2FM1-N1-L2"),
    ).toBeInTheDocument();
  });

  it("conserva la query string de la ruta actual en volver", () => {
    signOut();
    renderAt("/aprender?modulo=2");
    expect(
      screen.getByText("Formulario de ingreso: /ingresar?volver=%2Faprender%3Fmodulo%3D2"),
    ).toBeInTheDocument();
  });
});

describe("GuestOnly", () => {
  it("sin sesión muestra los hijos (/ingresar)", () => {
    signOut();
    renderAt("/ingresar");
    expect(screen.getByText("Formulario de ingreso: /ingresar")).toBeInTheDocument();
  });

  it("sin sesión muestra los hijos (/registro)", () => {
    signOut();
    renderAt("/registro");
    expect(screen.getByText("Formulario de registro")).toBeInTheDocument();
  });

  it("con sesión redirige a /aprender desde /ingresar", () => {
    signIn();
    renderAt("/ingresar");
    expect(screen.getByText("Contenido privado")).toBeInTheDocument();
    expect(screen.queryByText(/Formulario de ingreso/)).not.toBeInTheDocument();
  });

  it("con sesión redirige a /aprender desde /registro", () => {
    signIn();
    renderAt("/registro");
    expect(screen.getByText("Contenido privado")).toBeInTheDocument();
    expect(screen.queryByText("Formulario de registro")).not.toBeInTheDocument();
  });
});
