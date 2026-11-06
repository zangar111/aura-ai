// Съёмка Mini App (демо-сервер serve_miniapp.py должен быть запущен).
//
//   node video/raw/miniapp.js dark  video/raw/out/05_miniapp.mp4
//   node video/raw/miniapp.js light video/raw/out/05b_miniapp_light.mp4
//
// Кадры снимаются по виртуальному времени: прокрутка и «нажатия»
// выполняются скриптом, поэтому движение ровное.

const { chromium } = require("playwright");
const { spawn } = require("child_process");

const FPS = 30;
const [scheme = "dark", out = "out/05_miniapp.mp4"] = process.argv.slice(2);
const TOP = 74; // высота «шапки Telegram» над приложением

const CHROME_CSS = `
  #tg-chrome { position: fixed; left: 0; right: 0; top: 0; height: ${TOP}px; z-index: 50;
    background: var(--tg-theme-secondary-bg-color, #151e27); color: var(--tg-theme-text-color, #fff);
    font: 600 13px Inter, sans-serif; }
  #tg-chrome .sb { height: 26px; display: flex; justify-content: space-between; align-items: center; padding: 0 18px; }
  #tg-chrome .bar { height: 48px; display: flex; align-items: center; justify-content: space-between; padding: 0 14px; font-size: 16px; }
  #tg-chrome .bar .close { color: var(--tg-theme-link-color, #5eabe1); font-weight: 500; }
  #tg-chrome .bar .title { display: flex; flex-direction: column; align-items: center; line-height: 1.15; }
  #tg-chrome .bar .title small { font-size: 12px; font-weight: 500; opacity: 0.55; }
  body { padding-top: ${TOP}px !important; }
  #tap { position: fixed; width: 56px; height: 56px; margin: -28px 0 0 -28px; border-radius: 50%;
    background: rgba(255,255,255,0.4); z-index: 60; pointer-events: none; display: none; }
  html { scroll-behavior: auto !important; }
  ::-webkit-scrollbar { display: none; }
`;

const CHROME_HTML = `
  <div class="sb"><span>10:40</span><span>●●●● ▮</span></div>
  <div class="bar"><span class="close">Жабу</span>
  <span class="title">Aura<small>мини-қосымша</small></span><span>⋯</span></div>`;

const ease = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);

// Сценарий: [начало мс, длительность мс, действие]
function timeline() {
  return [
    [0, 1800, { hold: true }],
    [1800, 4200, { scrollTo: "bottom" }],
    [6400, 1800, { scrollTo: 0 }],
    [8600, 0, { tap: ".card.subject:nth-of-type(2)", click: true }],
    [10200, 0, { hover: "chart", week: 9 }],
    [12600, 0, { hover: "chart", week: 4 }],
    [14200, 0, { hover: "off" }],
    [14400, 2400, { scrollTo: "bottom" }],
    [17600, 1400, { scrollTo: 0 }],
    [19400, 0, { tap: "#tabs button:nth-child(2)", click: true }],
    [21600, 0, { tap: ".day-chip:nth-child(5)", click: true }],
    [24000, 0, { tap: ".day-chip:nth-child(4)", click: true }],
    [26200, 0, { tap: "#tabs button:nth-child(3)", click: true }],
    [29500, 0, { tap: "#tabs button:nth-child(1)", click: true }],
    [31500, 0, { end: true }],
  ];
}

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 432, height: 768 }, deviceScaleFactor: 2.5 });
  await page.goto(`http://127.0.0.1:8090/preview${scheme === "dark" ? "?scheme=dark" : ""}`);
  await page.waitForSelector(".card.subject", { timeout: 20000 });
  await page.addStyleTag({ content: CHROME_CSS });
  await page.evaluate((html) => {
    const chrome = document.createElement("div");
    chrome.id = "tg-chrome";
    chrome.innerHTML = html;
    document.body.appendChild(chrome);
    const tap = document.createElement("div");
    tap.id = "tap";
    document.body.appendChild(tap);
  }, CHROME_HTML);
  await page.evaluate(() => document.fonts.ready);

  const events = timeline();
  const duration = events[events.length - 1][0];
  const frames = Math.ceil((duration / 1000) * FPS);
  const ffmpeg = spawn("ffmpeg", [
    "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out,
  ], { stdio: ["pipe", "inherit", "inherit"] });

  let scrollFrom = 0, scrollTarget = 0, tapAt = null, tapPos = null;
  const done = new Set();

  for (let f = 0; f < frames; f++) {
    const t = (f * 1000) / FPS;

    for (const [index, [start, length, action]] of events.entries()) {
      if (t < start) continue;

      if (action.scrollTo !== undefined && t <= start + length + 1000 / FPS) {
        if (!done.has(index)) {
          done.add(index);
          scrollFrom = await page.evaluate(() => window.scrollY);
          scrollTarget = action.scrollTo === "bottom"
            ? await page.evaluate(() => document.documentElement.scrollHeight - innerHeight)
            : action.scrollTo;
        }
        const y = scrollFrom + (scrollTarget - scrollFrom) * ease(Math.min(1, (t - start) / length));
        await page.evaluate((y) => window.scrollTo(0, y), y);
      }

      if (done.has(index)) continue;

      if (action.tap) {
        done.add(index);
        tapPos = await page.evaluate((sel) => {
          const r = document.querySelector(sel).getBoundingClientRect();
          return { x: r.left + r.width / 2, y: r.top + Math.min(r.height / 2, 40) };
        }, action.tap);
        tapAt = t;
      }

      if (action.hover) {
        done.add(index);
        if (action.hover === "off") {
          await page.mouse.move(5, 760);
          await page.evaluate(() => { const tip = document.getElementById("tooltip"); if (tip) tip.hidden = true; });
        } else {
          const pos = await page.evaluate((week) => {
            const svg = [...document.querySelectorAll(".card svg")].sort(
              (a, b) => b.getBoundingClientRect().width - a.getBoundingClientRect().width)[0];
            const r = svg.getBoundingClientRect();
            const last = 15;
            return { x: r.left + 34 + ((r.width - 44) * (week - 1)) / (last - 1), y: r.top + r.height / 2 };
          }, action.week);
          await page.mouse.move(pos.x, pos.y);
          tapPos = pos; tapAt = t;
        }
      }
    }

    // Нажатие: кружок появляется, затем срабатывает клик.
    if (tapAt !== null) {
      const k = t - tapAt;
      const style = k > 600 ? { display: "none" } : {
        display: "block", left: tapPos.x + "px", top: tapPos.y + "px",
        opacity: String((1 - k / 600) * 0.9), transform: `scale(${0.6 + (k / 600) * 1.3})`,
      };
      await page.evaluate((s) => Object.assign(document.getElementById("tap").style, s), style);
      const pending = events.find(([start, , a]) => a.click && start === tapAt && !a.clicked);
      if (pending && k >= 200) {
        pending[2].clicked = true;
        await page.evaluate((sel) => document.querySelector(sel).click(), pending[2].tap);
      }
    }

    const buffer = await page.screenshot({ type: "png" });
    if (!ffmpeg.stdin.write(buffer)) await new Promise((r) => ffmpeg.stdin.once("drain", r));
    if (f % 150 === 0) process.stdout.write(`miniapp ${scheme}: ${f}/${frames}\n`);
  }

  ffmpeg.stdin.end();
  await new Promise((r) => ffmpeg.on("close", r));
  await browser.close();
  console.log("OK", out);
}

main().catch((e) => { console.error(e); process.exit(1); });
