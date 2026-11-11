// Iconos de la racha (llama), el néctar (flor) y las vidas (corazón): reemplazan a los emojis
// 🔥, 🌸 y ❤️, que cambiaban de aspecto según el sistema operativo. Son decorativos: el texto de al lado ya dice qué son.
import nectarUrl from "../../assets/icons/nectar.png";
import streakUrl from "../../assets/icons/racha.png";
import heartUrl from "../../assets/icons/vida.png";

interface IconProps {
  /** Tamaño en píxeles (ancho = alto). */
  size?: number;
  className?: string;
}

function GameIcon({ src, name, size = 20, className = "" }: IconProps & { src: string; name: string }) {
  return (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      data-icon={name}
      width={size}
      height={size}
      draggable={false}
      className={`inline-block shrink-0 select-none align-[-0.2em] ${className}`}
    />
  );
}

export function StreakIcon(props: IconProps) {
  return <GameIcon src={streakUrl} name="racha" {...props} />;
}

export function NectarIcon(props: IconProps) {
  return <GameIcon src={nectarUrl} name="nectar" {...props} />;
}

export function HeartIcon(props: IconProps) {
  return <GameIcon src={heartUrl} name="vida" {...props} />;
}
