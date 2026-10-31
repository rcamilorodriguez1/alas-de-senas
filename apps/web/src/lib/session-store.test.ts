import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { makeUser } from "../test/http";
import { useSessionStore } from "./session-store";

const TOKEN = "eyJhbGciOiJIUzI1NiJ9.token-de-acceso-secreto.firma";

function storageValues(storage: Storage): string[] {
  const values: string[] = [];
  for (let i = 0; i < storage.length; i += 1) {
    const key = storage.key(i);
    if (key !== null) {
      values.push(key, storage.getItem(key) ?? "");
    }
  }
  return values;
}

beforeEach(() => {
  useSessionStore.setState(useSessionStore.getInitialState(), true);
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

describe("useSessionStore", () => {
  it("arranca cargando, sin token ni usuario (aún no se resolvió el refresh)", () => {
    const state = useSessionStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
    expect(state.status).toBe("loading");
  });

  it("setSession guarda token y usuario y marca la sesión como autenticada", () => {
    const user = makeUser();
    useSessionStore.getState().setSession(TOKEN, user);
    const state = useSessionStore.getState();
    expect(state.accessToken).toBe(TOKEN);
    expect(state.user).toEqual(user);
    expect(state.status).toBe("authenticated");
  });

  it("clearSession borra token y usuario y marca la sesión como anónima", () => {
    useSessionStore.getState().setSession(TOKEN, makeUser());
    useSessionStore.getState().clearSession();
    const state = useSessionStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
    expect(state.status).toBe("anonymous");
  });

  it("clearSession desde 'loading' también deja la sesión anónima", () => {
    useSessionStore.getState().clearSession();
    expect(useSessionStore.getState().status).toBe("anonymous");
  });

  it("B23: el token de acceso vive solo en memoria (ni localStorage ni sessionStorage ni cookies)", () => {
    useSessionStore.getState().setSession(TOKEN, makeUser());
    for (const value of storageValues(localStorage)) {
      expect(value).not.toContain(TOKEN);
    }
    for (const value of storageValues(sessionStorage)) {
      expect(value).not.toContain(TOKEN);
    }
    expect(document.cookie).not.toContain(TOKEN);
  });
});
