// Utilidades SOLO para pruebas de la lección (Grupo 5): datos tipados con los esquemas generados,
// un servidor simulado que evalúa como el real (sin revelar la respuesta antes de tiempo, R4.4),
// espías de <video> (jsdom no reproduce medios) y el render de la ruta /leccion/:lessonId.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createElement, Fragment, StrictMode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi, type MockInstance } from "vitest";
import { appRoutes } from "../app/routes";
import type { components } from "../lib/api-types";
import { errorBody, jsonResponse, type FetchHandler, type RecordedRequest } from "./http";

type Schemas = components["schemas"];
export type LessonStartOut = Schemas["LessonStartOut"];
export type LessonInfoOut = Schemas["LessonInfoOut"];
export type PublicExerciseOut = Schemas["PublicExerciseOut"];
export type AnswerOut = Schemas["AnswerOut"];
export type LessonCompletionOut = Schemas["LessonCompletionOut"];
export type HeartsOut = Schemas["HeartsOut"];
export type VideoRef = Schemas["VideoRef"];
export type WordOption = Schemas["WordOption"];
export type VideoOption = Schemas["VideoOption"];
export type PublicObserve = Schemas["PublicObserve"];
export type PublicVideoToMeaning = Schemas["PublicVideoToMeaning"];
export type PublicMeaningToVideo = Schemas["PublicMeaningToVideo"];
export type PublicMemoryMatch = Schemas["PublicMemoryMatch"];
export type PublicProduce = Schemas["PublicProduce"];
export type PublicConversation = Schemas["PublicConversation"];
export type PublicSpelling = Schemas["PublicSpelling"];

export const SESSION_ID = "6f1d2c3b-4a5e-4f60-9b7a-8c9d0e1f2a3b";
export const NEW_SESSION_ID = "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d";

// ---------- Videos (rutas opacas, sin la palabra: R4.4) ----------

function media(hex: string): VideoRef {
  return { src: `/media/v/${hex}.mp4`, poster: `/media/p/${hex}.jpg` };
}

export const SIGN_VIDEO = {
  hola: media("3f9a1c0d5e7b2a46"),
  "buenos días": media("a17c4e9b0d3f5286"),
  gracias: media("c2d8e6f40a1b9375"),
  "hasta luego": media("5b0e7d2c9f4a6318"),
  "por favor": media("e4b19a7c03d5f862"),
  señor: media("7d3a0f9e2b6c1854"),
} as const satisfies Record<string, VideoRef>;

export type Word = keyof typeof SIGN_VIDEO;

export const LETTER_VIDEO: Record<string, VideoRef> = {
  A: media("0a1b2c3d4e5f6071"),
  L: media("1b2c3d4e5f607182"),
  M: media("2c3d4e5f60718293"),
  C: media("3d4e5f60718293a4"),
};

/** Palabra cuyo video tiene esa ruta (solo lo sabe la prueba, nunca la interfaz). */
export function wordOfVideo(src: string | null): Word {
  const found = (Object.keys(SIGN_VIDEO) as Word[]).find((w) => SIGN_VIDEO[w].src === src);
  if (found === undefined) throw new Error(`Video desconocido: ${String(src)}`);
  return found;
}

// ---------- Tokens opacos (orden público por token, D-008) ----------

let tokenSeed = 48_271;
function opaqueToken(): string {
  tokenSeed = (tokenSeed * 16_807) % 2_147_483_647;
  return `tk_${tokenSeed.toString(36).padStart(7, "0")}`;
}

function byToken<T extends { token: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => (a.token < b.token ? -1 : a.token > b.token ? 1 : 0));
}

// ---------- Ejercicios con su clave (la clave nunca llega al cliente) ----------

export interface ExerciseKey {
  correctToken: string | null;
  correctTokens: string[];
  correctWord: string | null;
  /** MEMORY_MATCH: token de video → token de palabra. */
  pairs: Record<string, string>;
}

export interface BuiltExercise {
  exercise: PublicExerciseOut;
  key: ExerciseKey;
}

const NO_KEY: ExerciseKey = { correctToken: null, correctTokens: [], correctWord: null, pairs: {} };

export function observe(
  id: string,
  order: number,
  group: number | null,
  word: Word,
  text: { howTo?: string | null; usageExample?: string } = {},
): BuiltExercise {
  const content: PublicObserve = {
    type: "OBSERVE",
    video: SIGN_VIDEO[word],
    word,
    howTo: text.howTo === undefined ? `Para «${word}», mueve la mano abierta desde la frente.` : text.howTo,
    usageExample: text.usageExample ?? `Úsala al saludar: «${word}, ¿cómo estás?».`,
  };
  return {
    exercise: { id, order, activity: "OBSERVE", type: "OBSERVE", scored: false, group, content },
    key: NO_KEY,
  };
}

export interface ChoiceExercise extends BuiltExercise {
  /** Token de cada palabra entre las opciones. */
  tokenOf: Record<string, string>;
}

export function videoToMeaning(
  id: string,
  order: number,
  group: number | null,
  word: Word,
  distractors: Word[],
): ChoiceExercise {
  const options = byToken([word, ...distractors].map((w) => ({ token: opaqueToken(), word: w })));
  const tokenOf = Object.fromEntries(options.map((o) => [o.word, o.token]));
  const content: PublicVideoToMeaning = { type: "VIDEO_TO_MEANING", video: SIGN_VIDEO[word], options };
  return {
    exercise: { id, order, activity: "SELECT", type: "VIDEO_TO_MEANING", scored: true, group, content },
    key: { ...NO_KEY, correctToken: tokenOf[word], correctWord: word },
    tokenOf,
  };
}

export function meaningToVideo(
  id: string,
  order: number,
  group: number | null,
  word: Word,
  distractors: Word[],
): ChoiceExercise {
  const tagged = [word, ...distractors].map((w) => ({ token: opaqueToken(), word: w }));
  const tokenOf = Object.fromEntries(tagged.map((o) => [o.word, o.token]));
  const options: VideoOption[] = byToken(tagged).map((o) => ({ token: o.token, video: SIGN_VIDEO[o.word] }));
  const content: PublicMeaningToVideo = { type: "MEANING_TO_VIDEO", word, options };
  return {
    exercise: { id, order, activity: "SELECT", type: "MEANING_TO_VIDEO", scored: true, group, content },
    key: { ...NO_KEY, correctToken: tokenOf[word], correctWord: word },
    tokenOf,
  };
}

export function produce(id: string, order: number, group: number | null, word: Word): BuiltExercise {
  const content: PublicProduce = { type: "PRODUCE", video: SIGN_VIDEO[word], word, cameraLabel: null };
  return {
    exercise: { id, order, activity: "PRODUCE", type: "PRODUCE", scored: false, group, content },
    key: NO_KEY,
  };
}

export interface MemoryExercise extends BuiltExercise {
  videoTokenOf: Record<string, string>;
  wordTokenOf: Record<string, string>;
}

export function memoryMatch(id: string, order: number, words: Word[]): MemoryExercise {
  const videos = words.map((w) => ({ token: opaqueToken(), word: w }));
  const wordsTagged = words.map((w) => ({ token: opaqueToken(), word: w }));
  const videoTokenOf = Object.fromEntries(videos.map((v) => [v.word, v.token]));
  const wordTokenOf = Object.fromEntries(wordsTagged.map((v) => [v.word, v.token]));
  const content: PublicMemoryMatch = {
    type: "MEMORY_MATCH",
    videoCards: byToken(videos).map((v) => ({ token: v.token, video: SIGN_VIDEO[v.word] })),
    wordCards: byToken(wordsTagged),
  };
  const pairs = Object.fromEntries(words.map((w) => [videoTokenOf[w], wordTokenOf[w]]));
  return {
    exercise: { id, order, activity: "SELECT", type: "MEMORY_MATCH", scored: true, group: null, content },
    key: { ...NO_KEY, pairs },
    videoTokenOf,
    wordTokenOf,
  };
}

export interface ConversationTurnSpec {
  prompt: Word;
  answer: Word;
  distractors: Word[];
}

export interface ConversationExercise extends BuiltExercise {
  /** Por turno: token de cada palabra de respuesta. */
  turnTokens: Record<string, string>[];
}

export function conversation(id: string, order: number, turns: ConversationTurnSpec[]): ConversationExercise {
  const turnTokens: Record<string, string>[] = [];
  const publicTurns = turns.map((t) => {
    const tagged = [t.answer, ...t.distractors].map((w) => ({ token: opaqueToken(), word: w }));
    turnTokens.push(Object.fromEntries(tagged.map((o) => [o.word, o.token])));
    return {
      prompt: SIGN_VIDEO[t.prompt],
      options: byToken(tagged).map((o) => ({ token: o.token, video: SIGN_VIDEO[o.word] })),
    };
  });
  const content: PublicConversation = { type: "CONVERSATION", turns: publicTurns };
  return {
    exercise: { id, order, activity: "USE", type: "CONVERSATION", scored: true, group: null, content },
    key: { ...NO_KEY, correctTokens: turns.map((t, i) => turnTokens[i][t.answer]) },
    turnTokens,
  };
}

export function spelling(
  id: string,
  order: number,
  letters: string[],
  word: string,
  distractors: string[],
): ChoiceExercise {
  const options = byToken([word, ...distractors].map((w) => ({ token: opaqueToken(), word: w })));
  const tokenOf = Object.fromEntries(options.map((o) => [o.word, o.token]));
  const content: PublicSpelling = {
    type: "SPELLING",
    letters: letters.map((l) => LETTER_VIDEO[l]),
    options,
  };
  return {
    exercise: { id, order, activity: "USE", type: "SPELLING", scored: true, group: null, content },
    key: { ...NO_KEY, correctToken: tokenOf[word], correctWord: word },
    tokenOf,
  };
}

// ---------- Lecciones ----------

export interface LessonFixture {
  start: LessonStartOut;
  keys: Record<string, ExerciseKey>;
}

export const HEARTS_OFF: HeartsOut = { enabled: false, current: 5, max: 5, nextHeartAt: null };
export const HEARTS_FULL: HeartsOut = { enabled: true, current: 5, max: 5, nextHeartAt: null };

export const LESSON_INFO: Record<"L1" | "L2" | "L4", LessonInfoOut> = {
  L1: {
    id: "M1-N1-L1",
    order: 1,
    type: "LEARN",
    title: "Aprende",
    nodeId: "M1-N1",
    nodeTitle: "Saludos y cortesía",
    nodeOrder: 1,
    moduleOrder: 1,
    estimatedXp: 20,
  },
  L2: {
    id: "M1-N1-L2",
    order: 2,
    type: "RECOGNIZE",
    title: "Reconoce",
    nodeId: "M1-N1",
    nodeTitle: "Saludos y cortesía",
    nodeOrder: 1,
    moduleOrder: 1,
    estimatedXp: 20,
  },
  L4: {
    id: "M1-N1-L4",
    order: 4,
    type: "CHALLENGE",
    title: "Reto final",
    nodeId: "M1-N1",
    nodeTitle: "Saludos y cortesía",
    nodeOrder: 1,
    moduleOrder: 1,
    estimatedXp: 30,
  },
};

export function lessonFixture(
  lesson: LessonInfoOut,
  built: BuiltExercise[],
  hearts: HeartsOut = lesson.type === "LEARN" ? HEARTS_OFF : HEARTS_FULL,
  sessionId: string = SESSION_ID,
): LessonFixture {
  return {
    start: { sessionId, lesson, exercises: built.map((b) => b.exercise), hearts },
    keys: Object.fromEntries(built.map((b) => [b.exercise.id, b.key])),
  };
}

/** M1-N1-L1 (Aprende) realista: por seña OBSERVE, VIDEO_TO_MEANING y PRODUCE; al final MEANING_TO_VIDEO. */
export function m1n1l1(sessionId: string = SESSION_ID) {
  const id = (n: number) => `M1-N1-L1-E${String(n).padStart(2, "0")}`;
  const words: Word[] = ["hola", "buenos días", "gracias"];
  const perSign = words.flatMap((w, g) => {
    const others = words.filter((x) => x !== w);
    return [
      observe(id(3 * g + 1), 3 * g + 1, g, w),
      videoToMeaning(id(3 * g + 2), 3 * g + 2, g, w, [...others, "hasta luego"]),
      produce(id(3 * g + 3), 3 * g + 3, g, w),
    ];
  });
  const finals = words.map((w, g) =>
    meaningToVideo(id(10 + g), 10 + g, g, w, [...words.filter((x) => x !== w), "por favor"]),
  );
  const built = [...perSign, ...finals];
  return { ...lessonFixture(LESSON_INFO.L1, built, HEARTS_OFF, sessionId), built };
}

export const COMPLETION_PASSED: LessonCompletionOut = {
  score: 83,
  correct: 5,
  total: 6,
  passed: true,
  xpEarned: 16,
  nectarEarned: 4,
  streak: { current: 3, extended: true },
  newAchievements: [{ id: "primer-vuelo", title: "Primer vuelo", nectar: 10 }],
  unlocked: [{ type: "LESSON", id: "M1-N1-L2" }],
  mascotMood: "cheer",
  mascotMessage: "¡Volaste alto! Ya sabes saludar en LSC.",
};

export const COMPLETION_FAILED: LessonCompletionOut = {
  score: 50,
  correct: 3,
  total: 6,
  passed: false,
  xpEarned: 5,
  nectarEarned: 1,
  streak: { current: 1, extended: true },
  newAchievements: [],
  unlocked: [],
  mascotMood: "thinking",
  mascotMessage: "Vas bien. Repasa las señas y vuelve a intentarlo.",
};

// ---------- Servidor simulado ----------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function sameStrings(a: unknown, b: string[]): boolean {
  return Array.isArray(a) && a.length === b.length && a.every((x, i) => x === b[i]);
}

function evaluate(exercise: PublicExerciseOut, key: ExerciseKey, answer: Record<string, unknown>): boolean {
  switch (exercise.type) {
    case "OBSERVE":
      return answer.watched === true;
    case "PRODUCE":
      return answer.ok === true;
    case "VIDEO_TO_MEANING":
    case "MEANING_TO_VIDEO":
    case "SPELLING":
      return answer.optionToken === key.correctToken;
    case "CONVERSATION":
      return sameStrings(answer.choices, key.correctTokens);
    case "MEMORY_MATCH": {
      const attempts = answer.attempts;
      if (!Array.isArray(attempts)) return false;
      const expected = Object.keys(key.pairs).length;
      return (
        attempts.length === expected &&
        attempts.every((a) => isRecord(a) && typeof a.videoToken === "string" && key.pairs[a.videoToken] === a.wordToken)
      );
    }
  }
}

export interface LessonServerOptions {
  /** Respuestas sucesivas a POST …/sessions (la última se repite). */
  starts?: (LessonFixture | Response)[];
  /** Permite sustituir la respuesta de una petición de respuesta (p. ej. 410). */
  onAnswer?: (request: RecordedRequest, evaluated: AnswerOut) => Response | AnswerOut | undefined;
  completion?: LessonCompletionOut | Response;
}

export interface LessonServer {
  handler: FetchHandler;
  /** Sesión actual (cambia con «Empezar de nuevo»). */
  current(): LessonFixture | null;
}

export function lessonServer(fixture: LessonFixture, options: LessonServerOptions = {}): LessonServer {
  const starts = options.starts ?? [fixture];
  let startCalls = 0;
  let current: LessonFixture | null = null;
  let hearts: HeartsOut = fixture.start.hearts;
  let answered = new Map<string, AnswerOut>();

  const handler: FetchHandler = (request) => {
    const { path, method } = request;
    if (method === "GET" && path === "/api/learning-path") {
      return jsonResponse(200, { modules: [] });
    }
    const startMatch = /^\/api\/lessons\/([^/]+)\/sessions$/.exec(path);
    if (method === "POST" && startMatch) {
      const next = starts[Math.min(startCalls, starts.length - 1)];
      startCalls += 1;
      if (next instanceof Response) return next.clone();
      current = next;
      hearts = next.start.hearts;
      answered = new Map();
      return jsonResponse(201, next.start);
    }
    const answerMatch = /^\/api\/lesson-sessions\/([^/]+)\/answers$/.exec(path);
    if (method === "POST" && answerMatch) {
      if (current === null || answerMatch[1] !== current.start.sessionId) {
        return jsonResponse(404, errorBody(404, "SESSION_NOT_FOUND", "No encontramos esta sesión."));
      }
      const body = request.body;
      const exerciseId = isRecord(body) && typeof body.exerciseId === "string" ? body.exerciseId : "";
      const answer = isRecord(body) && isRecord(body.answer) ? body.answer : {};
      const exercise = current.start.exercises.find((e) => e.id === exerciseId);
      if (exercise === undefined) {
        return jsonResponse(422, errorBody(422, "VALIDATION_ERROR", "Ejercicio inválido."));
      }
      const first = answered.get(exerciseId);
      let evaluated: AnswerOut;
      if (first !== undefined) {
        evaluated = { ...first, alreadyAnswered: true };
      } else {
        const key = current.keys[exerciseId];
        const correct = evaluate(exercise, key, answer);
        if (!correct && exercise.scored && hearts.enabled) {
          hearts = { ...hearts, current: Math.max(0, hearts.current - 1) };
        }
        evaluated = {
          correct,
          correctToken: key.correctToken,
          correctTokens: key.correctTokens,
          correctWord: key.correctWord,
          alreadyAnswered: false,
          hearts,
        };
        answered.set(exerciseId, evaluated);
      }
      const custom = options.onAnswer?.(request, evaluated);
      if (custom instanceof Response) return custom;
      return jsonResponse(200, custom ?? evaluated);
    }
    const completeMatch = /^\/api\/lesson-sessions\/([^/]+)\/complete$/.exec(path);
    if (method === "POST" && completeMatch) {
      const completion = options.completion ?? COMPLETION_PASSED;
      return completion instanceof Response ? completion.clone() : jsonResponse(200, completion);
    }
    return jsonResponse(404, errorBody(404, "NOT_FOUND", "No encontrado."));
  };

  return { handler, current: () => current };
}

export function sessionExpired(): Response {
  return jsonResponse(
    410,
    errorBody(410, "SESSION_EXPIRED", "Esta lección se actualizó o pasó mucho tiempo. Empecemos de nuevo"),
  );
}

// ---------- <video> en jsdom ----------

export interface MediaSpies {
  play: MockInstance<HTMLMediaElement["play"]>;
  pause: MockInstance<HTMLMediaElement["pause"]>;
  load: MockInstance<HTMLMediaElement["load"]>;
  /** Simula que el navegador bloquea la reproducción automática (B30). */
  blockPlayback(blocked: boolean): void;
}

export function mockMedia(): MediaSpies {
  const paused = new WeakMap<HTMLMediaElement, boolean>();
  let blocked = false;
  const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
    if (blocked) {
      return Promise.reject(new DOMException("La reproducción automática está bloqueada.", "NotAllowedError"));
    }
    paused.set(this, false);
    this.dispatchEvent(new Event("play"));
    this.dispatchEvent(new Event("playing"));
    return Promise.resolve();
  });
  const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(function (this: HTMLMediaElement) {
    paused.set(this, true);
    this.dispatchEvent(new Event("pause"));
  });
  const load = vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
  vi.spyOn(HTMLMediaElement.prototype, "paused", "get").mockImplementation(function (this: HTMLMediaElement) {
    return paused.get(this) ?? true;
  });
  return {
    play,
    pause,
    load,
    blockPlayback(value: boolean) {
      blocked = value;
    },
  };
}

/** jsdom no implementa `scrollIntoView` (la lección hace scroll suave a la actividad activa). */
export function stubScrollIntoView(): void {
  if (typeof Element.prototype.scrollIntoView !== "function") {
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      writable: true,
      value: () => undefined,
    });
  }
}

// ---------- Render ----------

export function renderLesson(lessonId = "M1-N1-L1", options: { strict?: boolean } = {}) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [`/leccion/${lessonId}`] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const tree = createElement(
    QueryClientProvider,
    { client },
    createElement(RouterProvider, { router }),
  );
  render(createElement(options.strict ? StrictMode : Fragment, null, tree));
  return router;
}

// ---------- Consultas ----------

function normalize(text: string | null): string {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

/** Coincide con el elemento más interno cuyo texto (aunque esté repartido en varios nodos) incluye `text`. */
export function containingText(text: string) {
  return (_content: string, element: Element | null): boolean => {
    if (element === null || !normalize(element.textContent).includes(text)) return false;
    return Array.from(element.children).every((child) => !normalize(child.textContent).includes(text));
  };
}

export const ACTIVITY_TITLES = [
  "Actividad 1. Observa la seña",
  "Actividad 2. Selecciona el significado",
  "Actividad 3. Produce la seña",
  "Actividad 4. Usa lo aprendido",
] as const;

function activityHeadings(root: Element): Element[] {
  return Array.from(root.querySelectorAll("h1, h2, h3, h4, h5, h6, [role='heading']")).filter((h) =>
    normalize(h.textContent).includes("Actividad "),
  );
}

/** Tarjeta de la actividad n (1–4): el mayor contenedor que solo incluye su título. */
export function activityCard(n: 1 | 2 | 3 | 4): HTMLElement {
  const heading = screen.getByRole("heading", { name: (name) => name.includes(ACTIVITY_TITLES[n - 1]) });
  let card: HTMLElement = heading;
  while (card.parentElement !== null && activityHeadings(card.parentElement).length === 1) {
    card = card.parentElement;
  }
  return card;
}

/** Espera a que la lección cargue (aparece la barra de progreso del encabezado). */
export async function lessonLoaded(): Promise<void> {
  await screen.findByRole("progressbar");
}
