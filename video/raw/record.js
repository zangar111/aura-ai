// Кадр за кадром снимает сцену и собирает MP4 через ffmpeg.
//
//   node video/raw/record.js telegram notify  out/02_notify.mp4
//   node video/raw/record.js still    notify  out/still.png 9000
//
// Страница должна выставить window.renderAt(ms) и window.SCENE_DURATION.
// Время виртуальное, поэтому каждый кадр чёткий и ровно 1/30 секунды.

const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const HERE = __dirname;
const FPS = 30;

async function open(page, kind, scene) {
  const messages = fs.readFileSync(path.join(HERE, "build", "messages.json"), "utf8");
  const grades = fs.readFileSync(path.join(HERE, "build", "grades.json"), "utf8");
  await page.addInitScript(`window.MESSAGES = ${messages}; window.GRADES = ${grades};`);
  if (kind === "telegram" || kind === "still") {
    await page.goto(`file://${path.join(HERE, "telegram.html")}?scene=${scene}`);
  } else {
    await page.goto(`file://${path.join(HERE, kind + ".html")}?scene=${scene}`);
  }
  await page.evaluate(() => window.ready);
}

async function main() {
  const [kind, scene, out, at] = process.argv.slice(2);
  const desktop = kind === "journal" || kind === "terminal";
  const browser = await chromium.launch();
  if (kind === "logo") {
    const icon = scene === "icon";
    const page = await browser.newPage({ viewport: { width: icon ? 600 : 1200, height: 600 }, deviceScaleFactor: 2 });
    await open(page, kind, scene);
    await page.screenshot({ path: out, omitBackground: true });
    await browser.close();
    return;
  }
  const page = await browser.newPage(
    desktop
      ? { viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1.5 }
      : { viewport: { width: 432, height: 768 }, deviceScaleFactor: 2.5 }
  );
  await open(page, kind, scene);
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });

  if (at !== undefined) {
    // Один кадр: прогоняем время до нужного момента, чтобы прокрутка улеглась.
    for (let t = 0; t <= Number(at); t += 1000 / FPS) await page.evaluate((x) => window.renderAt(x), t);
    await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => {}))));
    await page.screenshot({ path: out });
    await browser.close();
    return;
  }

  const duration = await page.evaluate(() => window.SCENE_DURATION);
  const frames = Math.ceil((duration / 1000) * FPS);
  const ffmpeg = spawn("ffmpeg", [
    "-y", "-loglevel", "error",
    "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", "15",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart", out,
  ], { stdio: ["pipe", "inherit", "inherit"] });

  for (let f = 0; f < frames; f++) {
    await page.evaluate((x) => window.renderAt(x), (f * 1000) / FPS);
    await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => {}))));
    const buffer = await page.screenshot({ type: "png" });
    if (!ffmpeg.stdin.write(buffer)) await new Promise((r) => ffmpeg.stdin.once("drain", r));
    if (f % 150 === 0) process.stdout.write(`${scene}: ${f}/${frames}\n`);
  }

  ffmpeg.stdin.end();
  await new Promise((r) => ffmpeg.on("close", r));
  await browser.close();
  console.log("OK", out, `${(duration / 1000).toFixed(1)}s`);
}

main().catch((e) => { console.error(e); process.exit(1); });
