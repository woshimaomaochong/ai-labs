// 录一张图的操作过程（在服务器容器里跑）：只录页面里最大的那张图（svg/canvas 外框，统一规则，三组一样），
// 先静置 3 秒，再按顺序点几个按钮，最后鼠标从左到右扫过图。
// 用法：node rec.mjs <figure.html> <out.mp4> [秒数=14]
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

const [file, out, secsArg] = process.argv.slice(2);
const SECS = +(secsArg || 14);
const tmp = out + "_frames";
fs.rmSync(tmp, { recursive: true, force: true });
fs.mkdirSync(tmp, { recursive: true });
const browser = await puppeteer.launch({
  executablePath: "/usr/bin/chromium",
  args: ["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--disable-dev-shm-usage"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 860, deviceScaleFactor: 2 });
await page.goto("file://" + path.resolve(file), { waitUntil: "load", timeout: 30000 });
await new Promise(r => setTimeout(r, 1500));
// 找最大的图（svg 或 canvas），外扩 30px，按 860:520 的比例补齐
const box = await page.evaluate(() => {
  let best = null, area = 0;
  for (const el of document.querySelectorAll("svg, canvas")) {
    const r = el.getBoundingClientRect();
    if (r.width * r.height > area && r.width > 200) { area = r.width * r.height; best = r; }
  }
  if (!best) return { x: 0, y: 0, width: 1280, height: 774 };
  let x = best.x - 30, y = best.y - 45, w = best.width + 60, h = best.height + 90;
  const R = 860 / 520;
  if (w / h < R) { const nw = h * R; x -= (nw - w) / 2; w = nw; } else { const nh = w / R; y -= (nh - h) / 2; h = nh; }
  x = Math.max(0, x); y = Math.max(0, y + window.scrollY);
  return { x, y, width: Math.min(w, 1280 - x), height: h };
});
if (box.y + box.height > 860) { await page.setViewport({ width: 1280, height: Math.ceil(box.y + box.height + 10), deviceScaleFactor: 2 }); await new Promise(r => setTimeout(r, 800)); }

const KEY = /突发|自动|演示|运行|开始|播放|单步|生成|加入|放入|插入|访问|发送|发 ?1|查询|一键|合适|震荡/;
const ctrls = [];
for (const h of await page.$$("button, [role=button]")) {
  const t = (await h.evaluate(e => e.innerText || "")).trim();
  const vis = await h.evaluate(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  if (vis && !/重置|清空|复位|reset/i.test(t)) ctrls.push({ h, t, key: KEY.test(t) });
}
ctrls.sort((a, b) => b.key - a.key);
const plan = ctrls.slice(0, 3);
const clickFig = plan.length === 0;  // 没有按钮的图（技能做的常见）：直接点图本身，它提示「点击突发」
const log = [];
let n = 0;
const DSF = 2;
const cdp = await page.createCDPSession();
const frames = [];
cdp.on("Page.screencastFrame", async f => {
  const name = `${tmp}/${String(frames.length).padStart(5, "0")}.jpg`;
  frames.push({ name, ts: f.metadata.timestamp });
  fs.writeFileSync(name, Buffer.from(f.data, "base64"));
  cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
});
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, everyNthFrame: 1, maxWidth: 2560, maxHeight: 4000 });
const t0 = Date.now();
const el = () => (Date.now() - t0) / 1000;
let acted = 0, swept = false;
while (el() < SECS) {
  const t = el();
  if (acted < plan.length && t > 3 + acted * 2.6) {
    try { await plan[acted].h.click({ delay: 20 }); log.push([+t.toFixed(2), "点「" + plan[acted].t.slice(0, 12) + "」"]); } catch {}
    acted++;
  }
  if (clickFig && acted < 2 && t > 3 + acted * 2.6) {
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2).catch(() => {});
    log.push([+t.toFixed(2), "点一下画面"]); acted++;
  }
  if (!swept && t > SECS - 3.5) {
    swept = true; log.push([+t.toFixed(2), "鼠标扫过画面"]);
    const y = box.y + box.height * 0.5;
    page.mouse.move(box.x + box.width * 0.15, y).then(() => page.mouse.move(box.x + box.width * 0.85, y, { steps: 25 })).catch(() => {});
  }
  await new Promise(r => setTimeout(r, 100));
}
await cdp.send("Page.stopScreencast");
await browser.close();
n = frames.length;
const fps = n / SECS;
// 按真实时间戳写 concat 清单（每帧停到下一帧出现），首帧从 0 秒算
const lines = [];
for (let i = 0; i < n; i++) {
  const d = i + 1 < n ? frames[i + 1].ts - frames[i].ts : 0.1;
  lines.push(`file '${path.resolve(frames[i].name)}'`, `duration ${Math.max(0.001, d).toFixed(4)}`);
}
if (n) lines.push(`file '${path.resolve(frames[n - 1].name)}'`);
fs.writeFileSync(`${tmp}/list.txt`, lines.join("\n"));
// 截屏流的帧大小不一定等于设备像素，按帧宽 / 1280 换算
const f = v => `iw*${(v / 1280).toFixed(5)}`;
execFileSync("ffmpeg", ["-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", `${tmp}/list.txt`,
  "-vf", `crop=${f(box.width)}:${f(box.height)}:${f(box.x)}:${f(box.y)},scale=1720:-2,fps=15`, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out]);
fs.rmSync(tmp, { recursive: true, force: true });
fs.writeFileSync(out.replace(/\.mp4$/, ".json"), JSON.stringify({ file, box, fps: +fps.toFixed(2), frames: n, steps: log }, null, 1));
console.log(JSON.stringify({ out, fps: +fps.toFixed(2), frames: n, steps: log }));
