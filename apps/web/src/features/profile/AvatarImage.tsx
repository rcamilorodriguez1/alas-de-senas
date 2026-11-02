import { TomiSvg } from "../../components/mascot/Tomi";
import { useAvatarUrl } from "./avatar-api";

/** Foto de perfil (D-023) o, si no hay, Tomi. */
export function AvatarImage({ size = 40, label }: { size?: number; label: string }) {
  const url = useAvatarUrl();
  if (!url) {
    return (
      <span
        role="img"
        aria-label={label}
        className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-emerald-50"
        style={{ width: size, height: size }}
      >
        <TomiSvg size={size * 0.8} />
      </span>
    );
  }
  return (
    <img
      src={url}
      alt={label}
      width={size}
      height={size}
      className="shrink-0 rounded-full object-cover"
      style={{ width: size, height: size }}
    />
  );
}
