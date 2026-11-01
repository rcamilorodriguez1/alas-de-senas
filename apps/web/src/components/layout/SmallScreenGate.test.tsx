import { act, render, screen } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, it } from "vitest";
import { setViewportWidth } from "../../test/media";
import { SmallScreenGate } from "./SmallScreenGate";

const NOTICE = /Alas de Señas está pensada por ahora para portátil o computador/;
const SOON = /¡Pronto llegará la versión para celular!/;

function renderGate() {
  render(
    <SmallScreenGate>
      <p>Contenido de la app</p>
    </SmallScreenGate>,
  );
}

function resizeTo(width: number) {
  act(() => {
    setViewportWidth(width, true);
  });
}

describe("SmallScreenGate (R10.1, §9.7)", () => {
  it("en 1366 px muestra la app y no el aviso", () => {
    setViewportWidth(1366);
    renderGate();
    expect(screen.getByText("Contenido de la app")).toBeInTheDocument();
    expect(screen.queryByText(NOTICE)).toBeNull();
  });

  it("en exactamente 1024 px (mínimo soportado) muestra la app", () => {
    setViewportWidth(1024);
    renderGate();
    expect(screen.getByText("Contenido de la app")).toBeInTheDocument();
    expect(screen.queryByText(NOTICE)).toBeNull();
  });

  it("en 1023 px muestra el aviso amable con Tomi y oculta la app", () => {
    setViewportWidth(1023);
    renderGate();
    expect(screen.getByText(NOTICE)).toBeInTheDocument();
    expect(screen.getByText(SOON)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Tomi, el colibrí" })).toBeInTheDocument();
    expect(screen.getByText("Contenido de la app")).not.toBeVisible();
  });

  it("en 390 px (celular) muestra el aviso", () => {
    setViewportWidth(390);
    renderGate();
    expect(screen.getByText(NOTICE)).toBeInTheDocument();
    expect(screen.getByText("Contenido de la app")).not.toBeVisible();
  });

  it("al achicar la ventana por debajo de 1024 px aparece el aviso", () => {
    setViewportWidth(1366);
    renderGate();
    expect(screen.getByText("Contenido de la app")).toBeInTheDocument();

    resizeTo(800);

    expect(screen.getByText(NOTICE)).toBeInTheDocument();
    expect(screen.getByText("Contenido de la app")).not.toBeVisible();
  });

  it("al agrandar la ventana a 1024 px o más vuelve la app", () => {
    setViewportWidth(800);
    renderGate();
    expect(screen.getByText(NOTICE)).toBeInTheDocument();

    resizeTo(1280);

    expect(screen.getByText("Contenido de la app")).toBeInTheDocument();
    expect(screen.queryByText(NOTICE)).toBeNull();
  });

  it("deja de escuchar resize al desmontarse", () => {
    setViewportWidth(1366);
    const { unmount } = render(
      <SmallScreenGate>
        <p>Contenido de la app</p>
      </SmallScreenGate>,
    );
    unmount();
    // No debe lanzar ni actualizar un componente desmontado.
    expect(() => resizeTo(600)).not.toThrow();
  });
});

describe("SmallScreenGate: revisión del Grupo 4", () => {
  it("no desmonta la app al achicar y volver a ensanchar (no repite el arranque de sesión)", () => {
    let mounts = 0;
    function Counter() {
      useEffect(() => {
        mounts += 1;
      }, []);
      return <p>Contenido de la app</p>;
    }
    setViewportWidth(1366);
    render(
      <SmallScreenGate>
        <Counter />
      </SmallScreenGate>,
    );
    resizeTo(900);
    resizeTo(1366);
    expect(mounts).toBe(1);
    expect(screen.getByText("Contenido de la app")).toBeVisible();
  });

  it("no bloquea el diccionario aunque la pantalla sea pequeña (§9.7)", () => {
    window.history.pushState({}, "", "/diccionario/gracias");
    setViewportWidth(900);
    renderGate();
    expect(screen.getByText("Contenido de la app")).toBeVisible();
    expect(screen.queryByText(NOTICE)).toBeNull();
    window.history.pushState({}, "", "/");
  });
});
