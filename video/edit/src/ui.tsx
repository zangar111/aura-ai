import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  OffthreadVideo,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const FPS = 30;
export const s = (seconds: number) => Math.round(seconds * FPS);

export const C = {
  bg: "#07060f",
  violet: "#7b4dff",
  violetSoft: "#b694ff",
  lime: "#b6ff5c",
  cream: "#f4efe6",
  muted: "rgba(244,239,230,0.62)",
  red: "#ff5c7a",
};

export const FONT = '"Inter Display", "Inter", "Noto Color Emoji", sans-serif';

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const useSpring = (delay = 0, damping = 16, stiffness = 120) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping, stiffness, mass: 0.8 } });
};

// ---------- Фон: медленные световые пятна + зерно + виньетка ----------
export const Background: React.FC<{ accent?: string }> = ({ accent = C.violet }) => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const blob = (x: number, y: number, size: number, color: string, phase: number) => (
    <div
      style={{
        position: "absolute",
        left: x + Math.sin(t * 0.35 + phase) * 120,
        top: y + Math.cos(t * 0.28 + phase) * 90,
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        filter: "blur(140px)",
        opacity: 0.55,
      }}
    />
  );
  return (
    <AbsoluteFill style={{ background: C.bg, overflow: "hidden" }}>
      {blob(-200, -260, 900, accent, 0)}
      {blob(1150, 420, 800, "#2a1a7a", 2)}
      {blob(700, 700, 600, "rgba(182,255,92,0.35)", 4)}
      <AbsoluteFill
        style={{
          backgroundImage: "radial-gradient(rgba(255,255,255,0.07) 1px, transparent 1.4px)",
          backgroundSize: "34px 34px",
          transform: `translateY(${(t * 6) % 34}px)`,
        }}
      />
      <Grain />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,0.65) 100%)" }} />
    </AbsoluteFill>
  );
};

export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.09 }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ opacity, mixBlendMode: "overlay", pointerEvents: "none" }}>
      <svg width="1920" height="1080">
        <filter id={`grain${frame % 6}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={frame % 6} />
        </filter>
        <rect width="1920" height="1080" filter={`url(#grain${frame % 6})`} />
      </svg>
    </AbsoluteFill>
  );
};

// ---------- Кинетический заголовок: слова «вылетают» по очереди ----------
export const Kinetic: React.FC<{
  text: string;
  delay?: number;
  size?: number;
  weight?: number;
  color?: string;
  highlight?: string[];
  stagger?: number;
  style?: React.CSSProperties;
  out?: number; // кадр, с которого текст уходит
}> = ({ text, delay = 0, size = 84, weight = 800, color = C.cream, highlight = [], stagger = 3, style, out }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(" ");
  const exit = out === undefined ? 0 : interpolate(frame, [out, out + 10], [0, 1], clamp);
  return (
    <div
      style={{
        fontFamily: FONT,
        fontSize: size,
        fontWeight: weight,
        lineHeight: 1.04,
        letterSpacing: -size * 0.03,
        color,
        display: "flex",
        flexWrap: "wrap",
        columnGap: size * 0.26,
        opacity: 1 - exit,
        transform: `translateY(${-exit * 30}px)`,
        filter: `blur(${exit * 8}px)`,
        ...style,
      }}
    >
      {words.map((word, i) => {
        const p = spring({ frame: frame - delay - i * stagger, fps, config: { damping: 14, stiffness: 140, mass: 0.7 } });
        const lit = highlight.some((h) => word.includes(h));
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              transform: `translateY(${(1 - p) * size * 0.7}px) rotate(${(1 - p) * 6}deg)`,
              opacity: interpolate(p, [0, 0.4], [0, 1], clamp),
              filter: `blur(${(1 - Math.min(p, 1)) * 10}px)`,
              ...(lit
                ? { background: `linear-gradient(90deg, ${C.violetSoft}, ${C.lime})`, WebkitBackgroundClip: "text", color: "transparent" }
                : {}),
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};

// ---------- Маленькая надпись над заголовком ----------
export const Kicker: React.FC<{ text: string; delay?: number }> = ({ text, delay = 0 }) => {
  const p = useSpring(delay);
  return (
    <div
      style={{
        fontFamily: FONT,
        fontSize: 24,
        fontWeight: 700,
        letterSpacing: 6,
        color: C.lime,
        textTransform: "uppercase",
        display: "flex",
        alignItems: "center",
        gap: 16,
        opacity: p,
        transform: `translateX(${(1 - p) * -40}px)`,
      }}
    >
      <span style={{ width: 54 * p, height: 3, background: C.lime, borderRadius: 3 }} />
      {text}
    </div>
  );
};

// ---------- «Пилюля»-выноска ----------
export const Chip: React.FC<{
  text: string;
  delay?: number;
  size?: number;
  accent?: string;
  out?: number;
  style?: React.CSSProperties;
}> = ({ text, delay = 0, size = 32, accent, out, style }) => {
  const frame = useCurrentFrame();
  const p = useSpring(delay, 13, 150);
  const exit = out === undefined ? 0 : interpolate(frame, [out, out + 8], [0, 1], clamp);
  if (frame < delay) return null;
  return (
    <div
      style={{
        fontFamily: FONT,
        fontSize: size,
        fontWeight: 650,
        color: C.cream,
        padding: `${size * 0.42}px ${size * 0.8}px`,
        borderRadius: 999,
        background: "rgba(255,255,255,0.07)",
        border: `1.5px solid ${accent ?? "rgba(255,255,255,0.16)"}`,
        boxShadow: accent ? `0 0 40px ${accent}55` : "0 10px 30px rgba(0,0,0,0.35)",
        backdropFilter: "blur(18px)",
        display: "inline-flex",
        alignItems: "center",
        gap: 14,
        whiteSpace: "nowrap",
        opacity: Math.min(1, p * 1.5) * (1 - exit),
        transform: `scale(${0.6 + 0.4 * p}) translateY(${(1 - p) * 30 - exit * 20}px)`,
        transformOrigin: "left center",
        ...style,
      }}
    >
      {text}
    </div>
  );
};

// ---------- Телефон с видео внутри ----------
export const PHONE_H = 900;
export const PHONE_W = Math.round((PHONE_H * 1080) / 1920);

export const Phone: React.FC<{
  src: string;
  rate?: number;
  startFrom?: number;
  delay?: number;
  tilt?: number;
  zoom?: number;
  zoomOriginY?: number;
  glow?: string;
  muted?: boolean;
}> = ({ src, rate = 1, startFrom = 0, delay = 0, tilt = -14, zoom = 1, zoomOriginY = 70, glow = C.violet }) => {
  const frame = useCurrentFrame();
  const enter = useSpring(delay, 18, 90);
  const t = frame / FPS;
  const rotY = tilt * (1 - enter) * 2.2 + tilt * 0.45 + Math.sin(t * 0.6) * 3;
  const rotX = 4 + Math.cos(t * 0.5) * 2;
  const floatY = Math.sin(t * 0.9) * 10;
  const bezel = 16;
  return (
    <div style={{ perspective: 2200, width: PHONE_W + bezel * 2, height: PHONE_H + bezel * 2 }}>
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          transform: `translateY(${(1 - enter) * 500 + floatY}px) rotateY(${rotY}deg) rotateX(${rotX}deg) scale(${0.85 + 0.15 * enter})`,
          opacity: enter,
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: -60,
            borderRadius: 120,
            background: glow,
            filter: "blur(90px)",
            opacity: 0.45,
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: 70,
            background: "linear-gradient(145deg, #3a3a46, #0c0c12 40%, #22222c)",
            padding: bezel,
            boxShadow: "0 50px 120px rgba(0,0,0,0.7), inset 0 0 0 2px rgba(255,255,255,0.12)",
          }}
        >
          <div style={{ width: PHONE_W, height: PHONE_H, borderRadius: 56, overflow: "hidden", position: "relative", background: "#000" }}>
            <div
              style={{
                width: "100%",
                height: "100%",
                transform: `scale(${zoom})`,
                transformOrigin: `50% ${zoomOriginY}%`,
              }}
            >
              <OffthreadVideo
                src={staticFile(src)}
                playbackRate={rate}
                startFrom={startFrom}
                muted
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </div>
            {/* блик на стекле */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "linear-gradient(115deg, rgba(255,255,255,0.10) 0%, transparent 28%, transparent 70%, rgba(255,255,255,0.04) 100%)",
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

// ---------- Вход/выход сцены ----------
export const SceneFrame: React.FC<{ duration: number; children: React.ReactNode }> = ({ duration, children }) => {
  const frame = useCurrentFrame();
  const inP = interpolate(frame, [0, 14], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const outP = interpolate(frame, [duration - 12, duration], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
  return (
    <AbsoluteFill
      style={{
        opacity: inP * (1 - outP),
        transform: `scale(${1.06 - 0.06 * inP + 0.08 * outP})`,
        filter: `blur(${(1 - inP) * 14 + outP * 18}px)`,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

// Число, которое «набегает»
export const CountUp: React.FC<{ to: number; delay?: number; duration?: number; style?: React.CSSProperties; suffix?: string }> = ({
  to,
  delay = 0,
  duration = 40,
  style,
  suffix = "",
}) => {
  const frame = useCurrentFrame();
  const v = interpolate(frame, [delay, delay + duration], [0, to], { ...clamp, easing: Easing.out(Easing.cubic) });
  return <span style={style}>{Math.round(v) + suffix}</span>;
};
