import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
  Easing,
} from "remotion";
import { Background, C, Chip, CountUp, FONT, Grain, Kicker, Kinetic, Phone, SceneFrame, s, useSpring } from "./ui";

// Начала частей озвучки (video/voice/adi/full.mp3), секунды.
const SCENES = [0, 21, 51, 91, 121, 151, 171, 183];
export const TOTAL = s(183);

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Кадр внутри сцены по абсолютному времени ролика.
const at = (scene: number, seconds: number) => s(seconds - SCENES[scene]);

const Left: React.FC<{ children: React.ReactNode; top?: number }> = ({ children, top = 220 }) => (
  <div style={{ position: "absolute", left: 150, top, width: 900, display: "flex", flexDirection: "column", gap: 30 }}>
    {children}
  </div>
);

const PhoneSlot: React.FC<{ children: React.ReactNode; x?: number }> = ({ children, x = 1180 }) => (
  <div style={{ position: "absolute", left: x, top: 72 }}>{children}</div>
);

// Сменяющиеся заголовки: каждый живёт от from до to (кадры сцены).
const Swap: React.FC<{ from: number; to?: number; children: React.ReactNode }> = ({ from, to, children }) => (
  <Sequence from={from} durationInFrames={to === undefined ? undefined : to - from} layout="none">
    {children}
  </Sequence>
);

// ================= 1. Интро + проблема =================
const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const orb = useSpring(6, 10, 110);
  const word = useSpring(16, 14, 120);
  const ring = interpolate(frame, [6, 40], [0, 1], clamp);
  const out = interpolate(frame, [s(6), s(6.6)], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: 1 - out, transform: `scale(${1 + out * 0.3})`, filter: `blur(${out * 16}px)` }}>
      <div
        style={{
          position: "absolute",
          width: 700,
          height: 700,
          borderRadius: "50%",
          border: `3px solid ${C.violetSoft}`,
          transform: `scale(${0.3 + ring * 1.6})`,
          opacity: 1 - ring,
        }}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Img
          src={staticFile("logo_icon.png")}
          style={{ width: 330, transform: `scale(${orb}) rotate(${(1 - orb) * -90}deg)`, filter: `drop-shadow(0 0 60px ${C.violet})` }}
        />
        <div style={{ overflow: "hidden", width: 620 * word }}>
          <div style={{ fontFamily: FONT, fontWeight: 850, fontSize: 210, letterSpacing: -9, color: C.cream, whiteSpace: "nowrap" }}>
            Aur<span style={{ background: `linear-gradient(90deg, ${C.violetSoft}, ${C.lime})`, WebkitBackgroundClip: "text", color: "transparent" }}>a</span>
          </div>
        </div>
      </div>
      <div style={{ position: "absolute", top: 760 }}>
        <Kinetic text="ЕҰУ студентіне арналған ЖИ-көмекші" delay={s(1.6)} size={52} weight={600} color={C.muted} highlight={["ЖИ-көмекші"]} />
      </div>
    </AbsoluteFill>
  );
};

const Problem: React.FC = () => {
  const frame = useCurrentFrame();
  const enter = useSpring(0, 18, 80);
  const dim = interpolate(frame, [s(6), s(10)], [0, 1], clamp);
  const t = frame / 30;
  const tags = ["ТК", "РК1", "Р1", "ТК ОБЩ.", "Рейтинг допуска", "РК2", "Итоговый контроль", "Р2"];
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: 210,
          top: 90,
          width: 1500,
          height: 900,
          borderRadius: 24,
          overflow: "hidden",
          boxShadow: "0 60px 140px rgba(0,0,0,0.8)",
          transform: `perspective(2400px) rotateX(${12 - enter * 6}deg) rotateY(${-10 + t * 0.6}deg) translateY(${(1 - enter) * 300}px) scale(${0.9 + t * 0.006})`,
          opacity: enter,
          filter: `blur(${dim * 5}px) saturate(${1 - dim * 0.6}) brightness(${1 - dim * 0.45})`,
        }}
      >
        <div style={{ height: 56, background: "#dfe3ea", display: "flex", alignItems: "center", gap: 10, padding: "0 22px" }}>
          {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
            <span key={c} style={{ width: 16, height: 16, borderRadius: 8, background: c }} />
          ))}
          <span style={{ marginLeft: 26, flex: 1, height: 32, borderRadius: 16, background: "#fff", fontFamily: FONT, fontSize: 18, color: "#667", display: "flex", alignItems: "center", paddingLeft: 18 }}>
            🔒 Журнал успеваемости
          </span>
        </div>
        <OffthreadVideo src={staticFile("01_journal.mp4")} muted style={{ width: 1500, height: 844, objectFit: "cover" }} />
      </div>
      {/* Летающие названия столбцов */}
      {tags.map((tag, i) => {
        const appear = s(6.6 + i * 0.35);
        const p = interpolate(frame, [appear, appear + 14], [0, 1], clamp);
        const x = 180 + ((i * 397) % 1500);
        const y = 140 + ((i * 263) % 760);
        return (
          <div
            key={tag}
            style={{
              position: "absolute",
              left: x + Math.sin(t * 0.8 + i) * 40,
              top: y + Math.cos(t * 0.7 + i * 2) * 30,
              fontFamily: FONT,
              fontWeight: 800,
              fontSize: 40 + (i % 3) * 18,
              color: i % 2 ? C.red : C.cream,
              opacity: p * 0.9,
              transform: `scale(${p}) rotate(${Math.sin(i) * 12}deg)`,
              textShadow: "0 10px 30px rgba(0,0,0,0.8)",
            }}
          >
            {tag}
          </div>
        );
      })}
      <AbsoluteFill style={{ background: "linear-gradient(0deg, rgba(7,6,15,0.95) 0%, rgba(7,6,15,0.2) 45%, transparent 70%)" }} />
      <div style={{ position: "absolute", left: 150, bottom: 120, display: "flex", flexDirection: "column", gap: 26 }}>
        <Kinetic text="Жаңа баға қойылды ма?" delay={s(0.6)} size={104} highlight={["баға"]} />
        <div style={{ display: "flex", gap: 20 }}>
          <Chip text="🔕 Хабарлама келмейді" delay={s(4.4)} />
          <Chip text="📊 Ондаған баған" delay={s(7)} />
          <Chip text="⚠️ Қауіп қай жерде?" delay={s(10.6)} accent={C.red} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Scene1: React.FC = () => (
  <SceneFrame duration={s(21)}>
    <Sequence durationInFrames={s(7)}>
      <Intro />
    </Sequence>
    <Sequence from={s(6.4)}>
      <Problem />
    </Sequence>
  </SceneFrame>
);

// ================= 2. Уведомление + ИИ-сводка =================
const Scene2: React.FC = () => {
  const rate = 26 / 30;
  const clip = (t: number) => s(21 + t / rate) - s(21); // момент клипа → кадр сцены
  return (
    <SceneFrame duration={s(30)}>
      <PhoneSlot>
        <Phone src="02_notify.mp4" rate={rate} />
      </PhoneSlot>
      <Left>
        <Kicker text="01 · Хабарлама" delay={6} />
        <Swap from={0} to={clip(8.6)}>
          <Kinetic text="Жаңа баға — бірден хабар" delay={10} highlight={["бірден"]} out={clip(8.6) - 10} />
          <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 30 }}>
            <Chip text="🔔 Апталық бағалар мен рубежкалар" delay={clip(1.7)} out={clip(8.6) - 10} />
            <Chip text="🎯 Тек маңызды бағалар — артық шусыз" delay={clip(4.5)} out={clip(8.6) - 10} />
          </div>
        </Swap>
        <Swap from={clip(8.6)}>
          <Kinetic text="ЖИ-шолу әр жаңа бағадан кейін" delay={4} highlight={["ЖИ-шолу"]} />
          <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 30 }}>
            <Chip text="🆕 Не өзгерді" delay={s(2.2)} />
            <Chip text="✅ Жалпы жағдай" delay={s(3.4)} />
            <Chip text="⚠️ Қай пәннен қауіп бар" delay={s(4.6)} accent={C.red} />
            <Chip text="💡 Бір нақты кеңес" delay={s(6.6)} accent={C.lime} />
          </div>
        </Swap>
      </Left>
    </SceneFrame>
  );
};

// ================= 3. Чат с ИИ — главный «вау» =================
const Scene3: React.FC = () => {
  const frame = useCurrentFrame();
  const rate = 30.73 / 40;
  const clip = (t: number) => Math.round((t / rate) * 30);
  // Приближение к печатающемуся ответу.
  const zoom = interpolate(frame, [clip(7.4), clip(8.6), clip(18.6), clip(19.8)], [1, 1.32, 1.32, 1], {
    ...clamp,
    easing: Easing.inOut(Easing.cubic),
  });
  return (
    <SceneFrame duration={s(40)}>
      <PhoneSlot>
        <Phone src="03_ai_chat.mp4" rate={rate} zoom={zoom} zoomOriginY={88} glow={C.lime} />
      </PhoneSlot>
      <Left top={200}>
        <Kicker text="02 · ЖИ-мен сөйлесу" delay={6} />
        <Swap from={0} to={clip(5)}>
          <Kinetic text="Кәдімгі тілмен жаз" delay={10} highlight={["тілмен"]} out={clip(5) - 10} />
          <div style={{ marginTop: 40 }}>
            <Chip text="💬 «Ең нашар сабағым қайсы?»" delay={s(2)} size={40} out={clip(5) - 10} />
          </div>
        </Swap>
        <Swap from={clip(5)} to={clip(7.6)}>
          <Kinetic text="ЖИ өзі шешеді" delay={2} highlight={["өзі"]} out={clip(7.6) - clip(5) - 10} />
          <div style={{ marginTop: 40 }}>
            <Chip text="📊 Бағаларды қарап жатырмын…" delay={8} size={38} accent={C.violetSoft} />
          </div>
        </Swap>
        <Swap from={clip(7.6)} to={clip(20.6)}>
          <Kinetic text="Жауап нақты уақытта жазылады" delay={2} highlight={["нақты", "уақытта"]} out={clip(20.6) - clip(7.6) - 10} />
          <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 40 }}>
            <Chip text="⚡ Стриминг — көз алдыңда" delay={s(2)} accent={C.lime} />
            <Chip text="🧠 9 құрал: бағалар, кесте, жазбалар" delay={s(5)} />
            <Chip text="🎯 Нақты кеңес, жалпы сөз емес" delay={s(8.5)} />
          </div>
        </Swap>
        <Swap from={clip(20.6)}>
          <Kinetic text="Бір батырма — прогресс графигі" delay={2} highlight={["графигі"]} />
          <div style={{ marginTop: 40 }}>
            <Chip text="📈 Апталар бойынша баллдар" delay={clip(24.9) - clip(20.6)} accent={C.lime} size={38} />
          </div>
        </Swap>
      </Left>
    </SceneFrame>
  );
};

// ================= 4. Расписание, дайджест, напоминание =================
const Scene4: React.FC = () => {
  const rate = 39.77 / 30;
  const clip = (t: number) => Math.round((t / rate) * 30);
  return (
    <SceneFrame duration={s(30)}>
      <PhoneSlot>
        <Phone src="04_schedule.mp4" rate={rate} tilt={-12} />
      </PhoneSlot>
      <Left>
        <Kicker text="03 · Кесте" delay={6} />
        <Swap from={0} to={clip(10.4)}>
          <Kinetic text="☀️ Әр таңертең — бір хабарлама" delay={8} highlight={["таңертең"]} out={clip(10.4) - 10} />
          <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 30 }}>
            <Chip text="📚 Бүгінгі сабақтар" delay={s(2.4)} out={clip(10.4) - 10} />
            <Chip text="⏰ Еске салулар" delay={s(3.4)} out={clip(10.4) - 10} />
            <Chip text="🆕 Жаңа бағалар" delay={s(4.4)} out={clip(10.4) - 10} />
          </div>
        </Swap>
        <Swap from={clip(10.4)} to={clip(22.4)}>
          <Kinetic text="Сабаққа 15 минут қалғанда" delay={2} highlight={["15"]} out={clip(22.4) - clip(10.4) - 10} />
          <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 30 }}>
            <Chip text="📍 Аудитория мен корпус" delay={s(1.5)} />
            <Chip text="💻 Онлайн болса — Teams сілтемесі" delay={s(3)} accent={C.violetSoft} />
          </div>
        </Swap>
        <Swap from={clip(22.4)}>
          <Kinetic text="Кестені жай сұра" delay={2} highlight={["сұра"]} />
          <div style={{ marginTop: 36 }}>
            <Chip text="💬 «Ертең қандай сабақ бар?»" delay={s(1)} size={40} accent={C.lime} />
          </div>
        </Swap>
      </Left>
    </SceneFrame>
  );
};

// ================= 5. Mini App =================
const Scene5: React.FC = () => {
  const frame = useCurrentFrame();
  const split = at(4, 131);
  const p = interpolate(frame, [split, split + 24], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const appRate = 31.5 / 27;
  const textOut = interpolate(frame, [split - 12, split], [1, 0], clamp);
  return (
    <SceneFrame duration={s(30)}>
      {/* Тёмный телефон: справа → левее центра */}
      <div style={{ position: "absolute", left: interpolate(p, [0, 1], [1180, 380]), top: interpolate(p, [0, 1], [72, 118]) }}>
        <Sequence durationInFrames={s(3)} layout="none">
          <Phone src="05a_open_miniapp.mp4" />
        </Sequence>
        <Sequence from={s(3)} layout="none">
          <Phone src="05_miniapp.mp4" rate={appRate} tilt={-10} />
        </Sequence>
      </div>
      {/* Светлый телефон въезжает справа */}
      <Sequence from={split} layout="none">
        <div style={{ position: "absolute", left: 1010, top: 118 }}>
          <Phone src="05b_miniapp_light.mp4" rate={appRate} startFrom={Math.round((split - s(3)) * appRate)} tilt={10} glow={C.lime} />
        </div>
      </Sequence>
      <div style={{ opacity: textOut }}>
        <Left>
          <Kicker text="04 · Mini App" delay={6} />
          <Kinetic text="Telegram ішіндегі толыққанды қосымша" delay={s(1.5)} highlight={["толыққанды"]} size={78} />
          <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 24 }}>
            <Chip text="📊 Барлық пәндер" delay={s(4)} />
            <Chip text="📈 Апталық графиктер" delay={s(5)} />
            <Chip text="📅 Апта бойынша кесте" delay={s(6)} />
            <Chip text="🔔 Өзгерістер таспасы" delay={s(7)} />
          </div>
        </Left>
      </div>
      <Sequence from={split + 10} layout="none">
        <div style={{ position: "absolute", left: 0, right: 0, top: 22, display: "flex", justifyContent: "center", gap: 24, zIndex: 5 }}>
          <Chip text="🌙 Қараңғы" delay={0} />
          <Chip text="☀️ Жарық" delay={6} accent={C.lime} />
          <Chip text="🇰🇿 Қазақша" delay={14} />
          <Chip text="🇷🇺 Орысша" delay={20} />
        </div>
      </Sequence>
    </SceneFrame>
  );
};

// ================= 6. Технология и безопасность =================
const Stat: React.FC<{ delay: number; big: React.ReactNode; label: string; accent?: string }> = ({ delay, big, label, accent = C.violetSoft }) => {
  const p = useSpring(delay, 14, 130);
  return (
    <div
      style={{
        width: 360,
        height: 300,
        borderRadius: 36,
        background: "rgba(255,255,255,0.06)",
        border: `1.5px solid ${accent}66`,
        boxShadow: `0 0 60px ${accent}22`,
        backdropFilter: "blur(20px)",
        padding: 36,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        opacity: p,
        transform: `translateY(${(1 - p) * 80}px) scale(${0.8 + 0.2 * p})`,
      }}
    >
      <div style={{ fontFamily: FONT, fontSize: 120, fontWeight: 850, color: accent, letterSpacing: -4, lineHeight: 1 }}>{big}</div>
      <div style={{ fontFamily: FONT, fontSize: 30, fontWeight: 600, color: C.cream, lineHeight: 1.2 }}>{label}</div>
    </div>
  );
};

const Scene6: React.FC = () => {
  const frame = useCurrentFrame();
  const term = at(5, 162.2);
  const shift = interpolate(frame, [term - 10, term + 14], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  return (
    <SceneFrame duration={s(20)}>
      <div style={{ position: "absolute", left: 150, top: 110 }}>
        <Kicker text="05 · Технология" delay={6} />
      </div>
      <div
        style={{
          position: "absolute",
          left: 150,
          top: 220,
          display: "flex",
          gap: 36,
          transform: `translateY(${shift * -60}px) scale(${1 - shift * 0.35})`,
          transformOrigin: "left top",
          opacity: 1 - shift * 0.15,
        }}
      >
        <Stat delay={s(0.5)} big={<CountUp to={9} delay={s(0.5)} duration={30} />} label="құралы бар ЖИ-агент" />
        <Stat delay={s(5)} big="🔒" label="Platonus құпиясөзі шифрланады (AES)" accent={C.lime} />
        <Stat delay={s(8)} big="✓" label="Mini App Telegram қолтаңбасын тексереді" />
        <Stat delay={s(12)} big={<CountUp to={86} delay={s(12)} duration={40} />} label="автотест · бәрі өтті" accent={C.lime} />
      </div>
      <Sequence from={term} layout="none">
        <div
          style={{
            position: "absolute",
            left: 560,
            top: 340,
            width: 1240,
            height: 698,
            borderRadius: 24,
            overflow: "hidden",
            boxShadow: "0 50px 120px rgba(0,0,0,0.75)",
            transform: `perspective(2000px) rotateY(-8deg) scale(${0.9 + 0.1 * shift})`,
            opacity: shift,
          }}
        >
          <OffthreadVideo src={staticFile("06_pytest.mp4")} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </div>
      </Sequence>
    </SceneFrame>
  );
};

// ================= 7. Финал =================
const Scene7: React.FC = () => {
  const frame = useCurrentFrame();
  const orb = useSpring(4, 11, 100);
  const ring = interpolate(frame, [4, 50], [0, 1], clamp);
  const fade = interpolate(frame, [s(11.2), s(12)], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      {[0, 10, 20].map((d) => {
        const r = interpolate(frame, [4 + d, 60 + d], [0, 1], clamp);
        return (
          <div
            key={d}
            style={{
              position: "absolute",
              top: 140,
              width: 400,
              height: 400,
              borderRadius: "50%",
              border: `2px solid ${d === 10 ? C.lime : C.violetSoft}`,
              transform: `scale(${0.5 + r * 2.4})`,
              opacity: (1 - r) * 0.8,
            }}
          />
        );
      })}
      <Img
        src={staticFile("logo.png")}
        style={{ position: "absolute", top: 90, width: 900, transform: `scale(${orb})`, opacity: Math.min(1, orb), filter: `drop-shadow(0 0 ${40 + ring * 30}px ${C.violet})` }}
      />
      <div style={{ position: "absolute", top: 560, display: "flex", flexDirection: "column", alignItems: "center", gap: 26 }}>
        <Kinetic text="SMART.ENU-мен интеграцияға дайын" delay={s(0.6)} size={66} highlight={["SMART.ENU-мен"]} />
        <div style={{ display: "flex", gap: 20 }}>
          <Chip text="🎓 Сессия модулі" delay={s(3.6)} />
          <Chip text="🔑 Бірыңғай ЕҰУ аккаунты" delay={s(4.4)} />
        </div>
        <div style={{ marginTop: 20 }}>
          <Chip text="✈️ t.me/plt_pars_bot" delay={s(6.2)} size={44} accent={C.lime} />
        </div>
      </div>
      <AbsoluteFill style={{ background: "#000", opacity: fade }} />
    </AbsoluteFill>
  );
};

// ================= Переходы: вспышка на стыках =================
const Flashes: React.FC = () => {
  const frame = useCurrentFrame();
  let flash = 0;
  for (const start of SCENES.slice(1, -1)) {
    const k = frame - s(start);
    flash = Math.max(flash, interpolate(k, [-6, 0, 10], [0, 0.35, 0], clamp));
  }
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at center, ${C.violetSoft}, transparent 70%)`, opacity: flash, mixBlendMode: "screen" }} />
  );
};

// ================= Звук =================
const Sounds: React.FC = () => {
  const sfx = (file: string, second: number, volume = 0.5) => (
    <Sequence key={`${file}${second}`} from={Math.max(0, s(second))} layout="none">
      <Audio src={staticFile(`sfx/${file}.mp3`)} volume={volume} />
    </Sequence>
  );
  const r2 = 26 / 30;
  const r3 = 30.73 / 40;
  const r4 = 39.77 / 30;
  return (
    <>
      <Audio src={staticFile("voice.mp3")} volume={1} />
      <Audio
        src={staticFile("music_long.mp3")}
        volume={(f) => {
          const t = f / 30;
          const base = interpolate(t, [0, 1.5, 5.5, 6.5], [0, 0.32, 0.32, 0.12], clamp);
          // Без голоса — музыка громче: печать ответа ИИ и финал.
          const lift = Math.max(
            interpolate(t, [62, 63.5, 74, 75.5], [0, 0.12, 0.12, 0], clamp),
            interpolate(t, [181, 182], [0, 0.1], clamp),
          );
          const end = interpolate(t, [181.5, 183], [1, 0], clamp);
          return (t < 6.5 ? base : 0.12 + lift) * end;
        }}
      />
      {sfx("impact", 0.15, 0.7)}
      {sfx("whoosh", 6.1, 0.45)}
      {SCENES.slice(1, 6).map((start) => sfx("whoosh", start - 0.35, 0.5))}
      {sfx("riser", 168, 0.35)}
      {sfx("impact", 171.1, 0.75)}
      {sfx("notify", 21 + 0.6 / r2, 0.5)}
      {sfx("pop", 21 + 9 / r2, 0.4)}
      {sfx("pop", 51 + 4.4 / r3, 0.35)}
      {sfx("notify", 51 + 24.9 / r3, 0.4)}
      {sfx("notify", 91 + 0.4 / r4, 0.4)}
      {sfx("notify", 91 + 17.7 / r4, 0.5)}
    </>
  );
};

export const Promo: React.FC = () => {
  const scenes = [Scene1, Scene2, Scene3, Scene4, Scene5, Scene6, Scene7];
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <Background />
      {scenes.map((Scene, i) => (
        <Sequence key={i} from={s(SCENES[i])} durationInFrames={s(SCENES[i + 1] - SCENES[i])}>
          <Scene />
        </Sequence>
      ))}
      <Flashes />
      <Grain opacity={0.06} />
      <Sounds />
    </AbsoluteFill>
  );
};
