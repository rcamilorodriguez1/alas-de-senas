// MemoryMatchActivity, ConversationActivity y SpellingActivity dentro de LessonPage (R4.5, R4.14).
import { screen, waitFor, within } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSessionStore } from "../../../lib/session-store";
import { makeUser, mockFetch } from "../../../test/http";
import {
  activityCard,
  containingText,
  conversation,
  LESSON_INFO,
  LETTER_VIDEO,
  lessonFixture,
  lessonLoaded,
  lessonServer,
  memoryMatch,
  mockMedia,
  observe,
  renderLesson,
  SESSION_ID,
  SIGN_VIDEO,
  spelling,
  stubScrollIntoView,
  wordOfVideo,
  type Word,
} from "../../../test/lesson";

const ANSWERS = `/api/lesson-sessions/${SESSION_ID}/answers`;

beforeEach(() => {
  mockMedia();
  stubScrollIntoView();
  useSessionStore.setState({ accessToken: "t", user: makeUser(), status: "authenticated" });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

function videoInside(el: HTMLElement): HTMLVideoElement {
  const video = el instanceof HTMLVideoElement ? el : el.querySelector("video");
  if (video === null) throw new Error("La tarjeta debe contener un <video>");
  return video;
}

// ---------- MEMORY_MATCH ----------

describe("MemoryMatchActivity", () => {
  const WORDS: Word[] = ["hola", "gracias", "buenos días"];

  function memoryLesson() {
    const memory = memoryMatch("M1-N1-L3-E07", 7, WORDS);
    const fixture = lessonFixture({ ...LESSON_INFO.L2, id: "M1-N1-L3", order: 3, type: "PRACTICE", title: "Practica" }, [
      memory,
      observe("M1-N1-L3-E08", 8, null, "por favor"),
    ]);
    return { memory, fixture };
  }

  function videoCards(): HTMLElement[] {
    return WORDS.map((_, i) => screen.getByRole("button", { name: `Video ${i + 1}` }));
  }

  it("muestra una columna de videos («Video n», sin la palabra) y otra de palabras", async () => {
    const { memory, fixture } = memoryLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L3");
    await lessonLoaded();
    await screen.findByRole("button", { name: "Video 1" });

    const content = memory.exercise.content;
    if (content.type !== "MEMORY_MATCH") throw new Error("tipo");
    videoCards().forEach((card, i) => {
      expect(videoInside(card).getAttribute("src")).toBe(content.videoCards[i].video.src);
    });
    for (const w of WORDS) {
      expect(screen.getByRole("button", { name: w })).toBeInTheDocument();
    }
    const labels = Array.from(document.querySelectorAll("[aria-label]")).map((el) => el.getAttribute("aria-label") ?? "");
    for (const w of WORDS) {
      expect(labels.filter((l) => l.toLowerCase().includes(w))).toEqual([]);
    }
    expect(document.querySelector("[data-correct]")).toBeNull();
  });

  it("«Comprobar respuesta» se habilita al emparejar todas las tarjetas y envía los intentos en orden", async () => {
    const user = userEvent.setup();
    const { memory, fixture } = memoryLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L3");
    await lessonLoaded();
    await screen.findByRole("button", { name: "Video 1" });

    const check = screen.getByRole("button", { name: "Comprobar respuesta" });
    expect(check).toBeDisabled();

    // Empareja cada video con su palabra; el último par se arma empezando por la palabra.
    const expected: { videoToken: string; wordToken: string }[] = [];
    const cards = videoCards();
    for (let i = 0; i < cards.length; i += 1) {
      const word = wordOfVideo(videoInside(cards[i]).getAttribute("src"));
      const wordButton = screen.getByRole("button", { name: word });
      if (i === cards.length - 1) {
        await user.click(wordButton);
        await user.click(cards[i]);
      } else {
        await user.click(cards[i]);
        await user.click(wordButton);
      }
      expected.push({ videoToken: memory.videoTokenOf[word], wordToken: memory.wordTokenOf[word] });
      if (i < cards.length - 1) {
        expect(screen.getByRole("button", { name: "Comprobar respuesta" })).toBeDisabled();
      }
    }
    expect(api.to(ANSWERS, "POST")).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N1-L3-E07",
      answer: { attempts: expected },
    });
  });

  it("un intento equivocado también cuenta y se envía tal cual", async () => {
    const user = userEvent.setup();
    const { memory, fixture } = memoryLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L3");
    await lessonLoaded();
    await screen.findByRole("button", { name: "Video 1" });

    const cards = videoCards();
    const words = cards.map((c) => wordOfVideo(videoInside(c).getAttribute("src")));
    // Rotación: video 1 ↔ palabra del video 2, etc. (todas mal emparejadas).
    const expected = cards.map((_, i) => {
      const wrongWord = words[(i + 1) % words.length];
      return { videoToken: memory.videoTokenOf[words[i]], wordToken: memory.wordTokenOf[wrongWord] };
    });
    for (let i = 0; i < cards.length; i += 1) {
      await user.click(cards[i]);
      await user.click(screen.getByRole("button", { name: words[(i + 1) % words.length] }));
    }
    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N1-L3-E07",
      answer: { attempts: expected },
    });
  });
});

// ---------- CONVERSATION ----------

describe("ConversationActivity", () => {
  function conversationLesson() {
    const talk = conversation("M1-N1-L2-E07", 7, [
      { prompt: "hola", answer: "buenos días", distractors: ["gracias", "hasta luego", "por favor"] },
      { prompt: "gracias", answer: "por favor", distractors: ["hola", "buenos días", "hasta luego"] },
    ]);
    const fixture = lessonFixture(LESSON_INFO.L2, [talk, observe("M1-N1-L2-E08", 8, null, "señor")]);
    return { talk, fixture };
  }

  async function chooseTurn(user: UserEvent, index: number) {
    const radios = within(screen.getByRole("radiogroup")).getAllByRole("radio");
    await user.click(radios[index]);
  }

  async function submitIfNeeded(user: UserEvent) {
    const check = screen.queryByRole("button", { name: "Comprobar respuesta" });
    if (check !== null) {
      await waitFor(() => expect(check).toBeEnabled());
      await user.click(check);
    }
  }

  it("muestra «Turno 1 de 2» con el video de la Persona A y 4 opciones de video", async () => {
    const { talk, fixture } = conversationLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    expect(await screen.findByText(containingText("Turno 1 de 2"))).toBeInTheDocument();
    expect(screen.getByText(containingText("Persona A"))).toBeInTheDocument();
    const content = talk.exercise.content;
    if (content.type !== "CONVERSATION") throw new Error("tipo");
    const srcs = Array.from(document.querySelectorAll("video")).map((v) => v.getAttribute("src"));
    expect(srcs).toContain(content.turns[0].prompt.src);
    const radios = within(screen.getByRole("radiogroup")).getAllByRole("radio");
    expect(radios).toHaveLength(4);
    content.turns[0].options.forEach((option, i) => {
      expect(videoInside(screen.getByLabelText(`Opción ${i + 1}`)).getAttribute("src")).toBe(option.video.src);
    });
    expect(document.querySelector("[data-correct]")).toBeNull();
  });

  it("avanza turno a turno y al elegir en todos envía {choices: [token por turno]}", async () => {
    const user = userEvent.setup();
    const { talk, fixture } = conversationLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    await screen.findByText(containingText("Turno 1 de 2"));

    const content = talk.exercise.content;
    if (content.type !== "CONVERSATION") throw new Error("tipo");
    await chooseTurn(user, 2);
    expect(api.to(ANSWERS, "POST")).toHaveLength(0);

    expect(await screen.findByText(containingText("Turno 2 de 2"))).toBeInTheDocument();
    const srcs = Array.from(document.querySelectorAll("video")).map((v) => v.getAttribute("src"));
    expect(srcs).toContain(content.turns[1].prompt.src);
    await chooseTurn(user, 0);
    await submitIfNeeded(user);

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N1-L2-E07",
      answer: { choices: [content.turns[0].options[2].token, content.turns[1].options[0].token] },
    });
  });

  it("aparece bajo «Actividad 4. Usa lo aprendido»", async () => {
    const { fixture } = conversationLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    await screen.findByText(containingText("Turno 1 de 2"));
    const active = activityCard(4);
    expect(active).not.toHaveTextContent("Pendiente");
    expect(active).not.toHaveTextContent("🔒");
    expect(within(active).getByText(containingText("Turno 1 de 2"))).toBeInTheDocument();
  });
});

// ---------- SPELLING ----------

describe("SpellingActivity", () => {
  function spellingLesson() {
    const spell = spelling("M1-N3-L4-E05", 5, ["A", "L", "A"], "ALA", ["CAMA", "LAMA", "MALA"]);
    const info = { ...LESSON_INFO.L4, id: "M1-N3-L4", nodeId: "M1-N3", nodeTitle: "Alfabeto A–M", nodeOrder: 3 };
    const fixture = lessonFixture(info, [spell, observe("M1-N3-L4-E06", 6, null, "gracias")]);
    return { spell, fixture };
  }

  it("muestra los videos de las letras en orden y las palabras como radios", async () => {
    const { spell, fixture } = spellingLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N3-L4");
    await lessonLoaded();

    const radios = await screen.findAllByRole("radio");
    expect(radios).toHaveLength(4);
    const content = spell.exercise.content;
    if (content.type !== "SPELLING") throw new Error("tipo");
    content.options.forEach((o, i) => expect(radios[i]).toHaveTextContent(o.word));

    const letterSrcs = new Set(Object.values(LETTER_VIDEO).map((v) => v.src));
    const shown = Array.from(document.querySelectorAll("video"))
      .filter((v) => v.getAttribute("preload") !== "auto")
      .map((v) => v.getAttribute("src"))
      .filter((src): src is string => src !== null && letterSrcs.has(src));
    expect(shown).toEqual([LETTER_VIDEO.A.src, LETTER_VIDEO.L.src, LETTER_VIDEO.A.src]);
    expect(document.querySelector("[data-correct]")).toBeNull();
    expect(screen.queryByText(/Correcta/)).not.toBeInTheDocument();
  });

  it("«Comprobar respuesta» envía {optionToken} y marca la correcta", async () => {
    const user = userEvent.setup();
    const { spell, fixture } = spellingLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N3-L4");
    await lessonLoaded();

    const content = spell.exercise.content;
    if (content.type !== "SPELLING") throw new Error("tipo");
    const correct = content.options.findIndex((o) => o.token === spell.tokenOf.ALA);
    const check = screen.getByRole("button", { name: "Comprobar respuesta" });
    expect(check).toBeDisabled();

    await user.click((await screen.findAllByRole("radio"))[correct]);
    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N3-L4-E05",
      answer: { optionToken: spell.tokenOf.ALA },
    });
    await waitFor(() => expect(screen.getAllByRole("radio")[correct]).toHaveTextContent("Correcta"));
    expect(screen.getAllByRole("status").some((s) => (s.textContent ?? "").includes("¡Exacto!"))).toBe(true);
  });

  it("atajos: «3» elige la opción 3, Enter comprueba y otro Enter continúa", async () => {
    const user = userEvent.setup();
    const { spell, fixture } = spellingLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N3-L4");
    await lessonLoaded();
    await screen.findAllByRole("radio");

    const content = spell.exercise.content;
    if (content.type !== "SPELLING") throw new Error("tipo");

    await user.keyboard("3");
    expect(screen.getAllByRole("radio")[2]).toBeChecked();
    await user.keyboard("{Enter}");

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N3-L4-E05",
      answer: { optionToken: content.options[2].token },
    });
    await screen.findByRole("button", { name: "Continuar" });

    await user.keyboard("{Enter}");
    expect(await screen.findByLabelText("Video de la seña gracias")).toBeInTheDocument();
    expect(SIGN_VIDEO.gracias.src).toMatch(/^\/media\/v\/[0-9a-f]{16}\.mp4$/);
  });
});
