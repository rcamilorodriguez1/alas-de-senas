import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { apiRequest, type UserOut } from "../../lib/api";
import { useSessionStore } from "../../lib/session-store";

const SIZE = 256;
export const avatarKey = ["me", "avatar"] as const;

/** Recorta al centro y reduce a 256×256 en el navegador (la foto original nunca sale entera). */
export async function resizeToSquare(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const side = Math.min(bitmap.width, bitmap.height);
  const canvas = document.createElement("canvas");
  canvas.width = SIZE;
  canvas.height = SIZE;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Sin canvas");
  context.drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, SIZE, SIZE);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/webp", 0.85));
  if (!blob) throw new Error("No se pudo convertir la imagen");
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

/** Sube la foto (D-023) y actualiza la sesión con `avatarUpdatedAt`. */
export async function uploadAvatar(
  file: File,
  resize: (file: File) => Promise<string> = resizeToSquare,
): Promise<UserOut> {
  const image = await resize(file);
  const user = await apiRequest<UserOut>("PUT", "/me/avatar", { body: { image } });
  const { accessToken, setSession } = useSessionStore.getState();
  if (accessToken) setSession(accessToken, user);
  return user;
}

export async function removeAvatar(): Promise<UserOut> {
  const user = await apiRequest<UserOut>("DELETE", "/me/avatar");
  const { accessToken, setSession } = useSessionStore.getState();
  if (accessToken) setSession(accessToken, user);
  return user;
}

/** URL local (blob:) de la foto; se pide con el token porque es un dato personal. */
export function useAvatarUrl(): string | null {
  const updatedAt = useSessionStore((state) => state.user?.avatarUpdatedAt ?? null);
  const { data } = useQuery({
    queryKey: [...avatarKey, updatedAt],
    enabled: updatedAt !== null,
    queryFn: () => apiRequest<Blob>("GET", "/me/avatar", { responseType: "blob" }),
    staleTime: Infinity,
  });
  const url = useMemo(() => (data && updatedAt !== null ? URL.createObjectURL(data) : null), [data, updatedAt]);
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url);
  }, [url]);
  return url;
}

export function useInvalidateAvatar() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: avatarKey });
}
