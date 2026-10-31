import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { REDUCED_MOTION_QUERY, stubMatchMedia } from "../../test/media";
import { Mascot } from "./Mascot";
import { TomiSvg } from "./Tomi";

const MOODS = ["happy", "cheer", "sad", "thinking", "sleeping"] as const;
const EYE_FILL = "#0E2A2F";

function tomi(): HTMLElement {
  return screen.getByRole("img", { name: "Tomi, el colibrí" });
}

function eyeCircles(svg: Element): Element[] {
  return Array.from(svg.querySelectorAll("circle")).filter(
    (c) => c.getAttribute("fill")?.toUpperCase() === EYE_FILL,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TomiSvg (§9.6)", () => {
  it("es una imagen accesible llamada «Tomi, el colibrí»", () => {
    render(<TomiSvg />);
    const svg = tomi();
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg).toHaveAttribute("role", "img");
  });

  it("mide 120 px por defecto y respeta `size`", () => {
    const { unmount } = render(<TomiSvg />);
    expect(tomi()).toHaveAttribute("width", "120");
    expect(tomi()).toHaveAttribute("height", "120");
    unmount();
    render(<TomiSvg size={64} />);
    expect(tomi()).toHaveAttribute("width", "64");
    expect(tomi()).toHaveAttribute("height", "64");
  });

  it("no usa archivos externos (sin <image> ni href)", () => {
    render(<TomiSvg />);
    const svg = tomi();
    expect(svg.querySelector("image")).toBeNull();
    expect(svg.querySelector("[href]")).toBeNull();
  });

  it("despierto tiene el ojo como círculo", () => {
    render(<TomiSvg mood="happy" />);
    expect(eyeCircles(tomi()).length).toBeGreaterThan(0);
  });

  it("dormido cierra los ojos: sin círculo de ojo y data-mood=sleeping", () => {
    const { unmount } = render(<TomiSvg mood="happy" />);
    const awakeCircles = tomi().querySelectorAll("circle").length;
    unmount();

    render(<TomiSvg mood="sleeping" />);
    const svg = tomi();
    expect(svg).toHaveAttribute("data-mood", "sleeping");
    expect(eyeCircles(svg)).toHaveLength(0);
    expect(svg.querySelectorAll("circle").length).toBeLessThan(awakeCircles);
  });
});

describe("Mascot (R5.12)", () => {
  it.each(MOODS)("con mood=%s muestra a Tomi con ese estado de ánimo", (mood) => {
    render(<Mascot mood={mood} />);
    expect(tomi()).toHaveAttribute("data-mood", mood);
  });

  it("muestra el mensaje en una burbuja con role=status", () => {
    render(<Mascot mood="cheer" message="¡Muy bien, Camilo!" />);
    expect(screen.getByRole("status")).toHaveTextContent("¡Muy bien, Camilo!");
    expect(tomi()).toBeInTheDocument();
  });

  it("sin mensaje no muestra burbuja", () => {
    render(<Mascot mood="happy" />);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("con triste nunca regaña: el texto que se le pasa es el único que muestra", () => {
    render(<Mascot mood="sad" message="Casi, inténtalo otra vez." />);
    expect(screen.getByRole("status").textContent?.trim()).toBe("Casi, inténtalo otra vez.");
  });

  it("anima cuando el usuario no pide movimiento reducido", () => {
    stubMatchMedia(false);
    render(<Mascot mood="happy" message="Hola" />);
    const container = tomi().closest("[data-animated]");
    expect(container).not.toBeNull();
    expect(container).toHaveAttribute("data-animated", "true");
  });

  it("con prefers-reduced-motion no anima (data-animated=false)", () => {
    const matchMedia = stubMatchMedia(true);
    render(<Mascot mood="cheer" message="¡Lo lograste!" />);
    const container = tomi().closest("[data-animated]");
    expect(container).not.toBeNull();
    expect(container).toHaveAttribute("data-animated", "false");
    expect(matchMedia).toHaveBeenCalledWith(REDUCED_MOTION_QUERY);
  });

  it.each(MOODS)("con movimiento reducido y mood=%s tampoco anima", (mood) => {
    stubMatchMedia(true);
    render(<Mascot mood={mood} />);
    expect(tomi().closest("[data-animated]")).toHaveAttribute("data-animated", "false");
  });
});
