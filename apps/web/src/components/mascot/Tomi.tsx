export type MascotMood = "happy" | "cheer" | "sad" | "thinking" | "sleeping";

/** Tomi, el colibrí (§9.6): SVG propio, sin archivos externos. */
export function TomiSvg({ size = 120, mood = "happy" }: { size?: number; mood?: MascotMood }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 400 400"
      role="img"
      aria-label="Tomi, el colibrí"
      data-mood={mood}
    >
      <path d="M165 245 L70 320 L118 298 L88 368 L178 270 Z" fill="#0E9F6E" />
      <path
        className="tomi-wing"
        d="M190 205 C 220 90, 310 40, 370 52 C 335 110, 275 170, 215 218 Z"
        fill="#06B6D4"
      />
      <path
        d="M200 210 C 235 130, 290 105, 335 108 C 300 150, 255 192, 212 222 Z"
        fill="#67E8F9"
        opacity="0.85"
      />
      <ellipse cx="205" cy="228" rx="82" ry="54" transform="rotate(-30 205 228)" fill="#10B981" />
      <ellipse cx="252" cy="200" rx="26" ry="18" fill="#EC4899" />
      <circle cx="278" cy="160" r="38" fill="#10B981" />
      <path d="M308 150 L396 126 L312 168 Z" fill="#E8F4EF" />
      {mood === "sleeping" ? (
        <path
          d="M280 153 Q 290 160 300 153"
          stroke="#0E2A2F"
          strokeWidth="4"
          fill="none"
          strokeLinecap="round"
        />
      ) : (
        <>
          <circle cx="290" cy="152" r="8" fill="#0E2A2F" />
          <circle cx="293" cy="149" r="3" fill="#F5FAF7" />
        </>
      )}
    </svg>
  );
}
