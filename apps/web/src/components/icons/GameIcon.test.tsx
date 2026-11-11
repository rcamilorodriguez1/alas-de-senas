// Iconos de la racha y el néctar (reemplazan a los emojis 🔥 y 🌸).
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NectarIcon, StreakIcon } from "./GameIcon";

describe("iconos del juego", () => {
  it("la racha es una imagen decorativa: el texto de al lado ya dice «racha»", () => {
    const { container } = render(<StreakIcon />);
    const image = container.querySelector("img");
    expect(image).not.toBeNull();
    expect(image?.getAttribute("alt")).toBe("");
    expect(image?.getAttribute("aria-hidden")).toBe("true");
    expect(image?.dataset.icon).toBe("racha");
  });

  it("el néctar es una imagen decorativa", () => {
    const { container } = render(<NectarIcon />);
    const image = container.querySelector("img");
    expect(image?.getAttribute("alt")).toBe("");
    expect(image?.dataset.icon).toBe("nectar");
  });

  it("tiene ancho y alto fijos para que el texto no salte al cargar", () => {
    const { container } = render(<StreakIcon size={28} />);
    const image = container.querySelector("img");
    expect(image?.getAttribute("width")).toBe("28");
    expect(image?.getAttribute("height")).toBe("28");
  });
});
