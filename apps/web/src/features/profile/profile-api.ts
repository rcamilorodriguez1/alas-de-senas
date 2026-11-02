import { apiRequest, type UserOut } from "../../lib/api";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";

type Schemas = components["schemas"];
export type MeUpdate = Schemas["MeUpdateIn"];
export type AccountExport = Schemas["AccountExportOut"];

/** Guarda nombre, meta diaria o mano dominante y actualiza la sesión con el usuario nuevo. */
export async function updateMe(body: MeUpdate): Promise<UserOut> {
  const user = await apiRequest<UserOut>("PATCH", "/me", { body });
  const { accessToken, setSession } = useSessionStore.getState();
  if (accessToken) setSession(accessToken, user);
  return user;
}

/** Descarga todos los datos de la cuenta en JSON (Ley 1581: derecho de acceso, D-022). */
export async function downloadMyData(): Promise<void> {
  const data = await apiRequest<AccountExport>("GET", "/me/export");
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `mis-datos-alas-de-senas-${data.exportedAt.slice(0, 10)}.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Elimina la cuenta con todos sus datos (Ley 1581: supresión) y cierra la sesión local. */
export async function deleteAccount(password: string): Promise<void> {
  await apiRequest<undefined>("DELETE", "/me", { body: { password } });
  useSessionStore.getState().clearSession();
}
