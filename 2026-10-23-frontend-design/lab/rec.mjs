// 在服务器 fe-lab 容器里运行：node rec.mjs [文件名...]（默认 pages/ 下全部）
// 实拍动态效果：用 CDP 屏幕录制抓帧（打开时的入场动画 → 停顿 → 鼠标悬停主按钮 → 固定 12 秒匀速滚到底 → 停顿），
// 再用 ffmpeg 按真实时间戳合成 30fps 的 mp4。两组同题用同样的时间线，方便左右并排对比。
import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const BASE = "http://127.0.0.1:8000/";
const files = process.argv.slice(2).length ? process.argv.slice(2) : fs.readdirSync("pages").filter(f => f.endsWith(".html")).sort();
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox"] });
const SCROLL_MS = 12000;

async function record(name, out, vw, vh, mobile) {
  const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  const frames = [];
  cdp.on("Page.screencastFrame", f => {
    frames.push({ t: f.metadata.timestamp, data: f.data });
    cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await page.goto("about:blank");
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 85, maxWidth: vw * (mobile ? 2 : 1), maxHeight: vh * (mobile ? 2 : 1), everyNthFrame: 1 });
  const t0 = Date.now() / 1000;
  await page.goto(BASE + name, { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(3000);
  if (!mobile) {  // 悬停主按钮，展示交互动效
    const btn = page.locator("button:visible, a.btn:visible, .btn:visible, a[class*=button]:visible, a[class*=cta]:visible").first();
    try { const b = await btn.boundingBox({ timeout: 1000 }); if (b && b.y < vh) { await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 15 }); await page.waitForTimeout(1200); await page.mouse.move(vw - 40, vh - 40, { steps: 10 }); } } catch {}
  }
  await page.evaluate(ms => new Promise(res => {
    document.documentElement.style.scrollBehavior = "auto"; document.body.style.scrollBehavior = "auto";
    const h = document.documentElement.scrollHeight - innerHeight, s = performance.now();
    const step = now => { const k = Math.min(1, (now - s) / ms); window.scrollTo({ top: h * k, behavior: "instant" }); k < 1 ? requestAnimationFrame(step) : res(); };
    requestAnimationFrame(step);
  }), SCROLL_MS);
  await page.waitForTimeout(1500);
  const tEnd = Date.now() / 1000;
  await cdp.send("Page.stopScreencast");
  await ctx.close();
  // 帧 → mp4（按时间戳给每帧时长；about:blank 阶段的帧从 goto 开始算）
  const tmp = fs.mkdtempSync("/tmp/rec-");
  const fr = frames.filter(f => f.t >= t0 - 0.2);
  let list = "";
  fr.forEach((f, i) => {
    const p = path.join(tmp, `${String(i).padStart(5, "0")}.jpg`);
    fs.writeFileSync(p, Buffer.from(f.data, "base64"));
    const d = i + 1 < fr.length ? Math.max(0.001, fr[i + 1].t - f.t) : Math.max(0.5, tEnd - f.t);  // 静止的单屏页面只出很少几帧，最后一帧要撑到录制结束
    list += `file '${p}'\nduration ${d.toFixed(4)}\n`;
  });
  if (fr.length) list += `file '${path.join(tmp, String(fr.length - 1).padStart(5, "0") + ".jpg")}'\n`;
  fs.writeFileSync(path.join(tmp, "list.txt"), list);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", path.join(tmp, "list.txt"),
    "-vf", "fps=30,scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out]);
  fs.rmSync(tmp, { recursive: true, force: true });
  return fr.length;
}

for (const name of files) {
  const dir = path.join("out", name.replace(".html", ""));
  fs.mkdirSync(dir, { recursive: true });
  for (const [vw, vh, mob, fn] of [[1440, 900, false, "desktop.mp4"], [390, 844, true, "mobile.mp4"]]) {
    const out = path.join(dir, fn);
    if (fs.existsSync(out)) continue;
    try { console.log("rec", name, fn, await record(name, out, vw, vh, mob), "frames"); }
    catch (e) { console.log("fail", name, fn, String(e).slice(0, 200)); }
  }
}
await browser.close();
