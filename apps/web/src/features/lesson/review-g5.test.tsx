import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SignVideoPlayer } from "../../components/video/SignVideoPlayer";
import { useSessionStore } from "../../lib/session-store";
import { makeUser, mockFetch, type FetchHandler } from "../../test/http";
import {
  LESSON_INFO,
  lessonFixture,
  lessonLoaded,
  lessonServer,
  mockMedia,
  renderLesson,
  SESSION_ID,
  SIGN_VIDEO,
  stubScrollIntoView,
  videoToMeaning,
  type MediaSpies,
} from "../../test/lesson";

const ANSWERS = `/api/lesson-sessions/${SESSION_ID}/answers`;
let media: MediaSpies;

beforeEach(() => {
  media = mockMedia();
  stubScrollIntoView();
  useSessionStore.setState({ accessToken: "t", user: makeUser(), status: "authenticated" });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function v2m() {
  return lessonFixture(LESSON_INFO.L2, [
    videoToMeaning("M1-N1-L2-E01", 1, 0, "hola", ["gracias", "buenos días", "hasta luego"]),
    videoToMeaning("M1-N1-L2-E02", 2, 0, "gracias", ["hola", "buenos días", "hasta luego"]),
  ]);
}

describe("Revisión del Grupo 5", () => {
  it("un reproductor compacto (opciones, memoria, conversación) se reproduce solo y en bucle", async () => {
    render(
      <SignVideoPlayer src={SIGN_VIDEO.hola.src} poster={SIGN_VIDEO.hola.poster} word="hola" compact />,
    );
    await waitFor(() => expect(media.play).toHaveBeenCalled());
    const video = screen.getByLabelText("Video de la seña hola");
    expect(video).toHaveProperty("loop", true);
  });

  it("Enter después de elegir con el mouse comprueba la respuesta", async () => {
    const user = userEvent.setup();
    const api = mockFetch(lessonServer(v2m()).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    await user.click((await screen.findAllByRole("radio"))[1]);
    await user.keyboard("{Enter}");
    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(await screen.findByRole("button", { name: "Continuar" })).toHaveFocus();
  });

  it("un corte de red al responder avisa y deja seguir la lección (no la tumba)", async () => {
    const user = userEvent.setup();
    const server = lessonServer(v2m());
    let failOnce = true;
    const handler: FetchHandler = (request) => {
      if (request.path === ANSWERS && failOnce) {
        failOnce = false;
        return Promise.reject(new TypeError("Failed to fetch"));
      }
      return server.handler(request);
    };
    mockFetch(handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    await user.click((await screen.findAllByRole("radio"))[0]);
    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));
    expect(await screen.findByText(/No pudimos enviar tu respuesta/)).toBeInTheDocument();
    expect(screen.queryByText("No pudimos abrir la lección.")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));
    expect(await screen.findByRole("button", { name: "Continuar" })).toBeInTheDocument();
  });
});
