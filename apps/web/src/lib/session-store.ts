import { create } from "zustand";
import type { components } from "./api-types";

export type SessionUser = components["schemas"]["UserOut"];
export type SessionStatus = "loading" | "authenticated" | "anonymous";

interface SessionState {
  /** Solo en memoria: nunca en localStorage ni sessionStorage (§9.2, B23). */
  accessToken: string | null;
  user: SessionUser | null;
  status: SessionStatus;
  setSession: (accessToken: string, user: SessionUser) => void;
  clearSession: () => void;
}

export const useSessionStore = create<SessionState>()((set) => ({
  accessToken: null,
  user: null,
  status: "loading",
  setSession: (accessToken, user) => set({ accessToken, user, status: "authenticated" }),
  clearSession: () => set({ accessToken: null, user: null, status: "anonymous" }),
}));
