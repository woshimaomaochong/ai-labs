// 在服务器 fe-lab 容器里运行：node shoot.mjs [文件名...]（默认 pages/ 下全部）
// 每个网页：桌面 1440x900 + 手机 390x844 截图（首屏 + 整页）、axe 无障碍检查、技能承诺的几项检查。
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";

const BASE = "http://127.0.0.1:8000/";
const files = process.argv.slice(2).length ? process.argv.slice(2) : fs.readdirSync("pages").filter(f => f.endsWith(".html")).sort();
const AXE = fs.readFileSync("node_modules/axe-core/axe.min.js", "utf8");
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox"] });

async function settle(page) {
  try { await page.waitForLoadState("networkidle", { timeout: 15000 }); } catch {}
  await page.waitForTimeout(1500);
}

// 像真人一样慢慢滚到底再回顶部，触发“滚到才出现”的动画，否则整页截图下面全是空白（对用了这类动画的页面不公平）
async function warm(page) {
  for (let i = 0; i < 80; i++) {
    const end = await page.evaluate(() => { window.scrollBy(0, Math.round(innerHeight * 0.5)); return innerHeight + scrollY >= document.documentElement.scrollHeight - 2; });
    await page.waitForTimeout(150);
    if (end) break;
  }
  await page.waitForTimeout(1200);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(600);
}

async function scrollVideo(dir, name, vw, vh, mobile) {
  const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, isMobile: mobile, hasTouch: mobile,
    recordVideo: { dir, size: { width: vw, height: vh } } });
  const page = await ctx.newPage();
  await page.goto(BASE + name, { timeout: 30000 }).catch(() => {});
  await settle(page);
  await page.waitForTimeout(1200);
  const h = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
  const steps = 90;
  for (let i = 1; i <= steps; i++) {
    await page.evaluate(y => window.scrollTo(0, y), Math.round(h * i / steps));
    await page.waitForTimeout(80);
  }
  await page.waitForTimeout(800);
  const v = page.video();
  await ctx.close();
  fs.renameSync(await v.path(), path.join(dir, mobile ? "mobile.webm" : "desktop.webm"));
}

for (const name of files) {
  const dir = path.join("out", name.replace(".html", ""));
  if (fs.existsSync(path.join(dir, "metrics.json"))) continue;
  fs.mkdirSync(dir, { recursive: true });
  const m = { file: name };
  try {
    // ---- 桌面 ----
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on("console", msg => { if (msg.type() === "error") errors.push(msg.text().slice(0, 200)); });
    page.on("pageerror", e => errors.push("pageerror: " + String(e).slice(0, 200)));
    await page.goto(BASE + name, { timeout: 30000 });
    await settle(page);
    await page.screenshot({ path: path.join(dir, "desktop_hero.png") });
    await warm(page);
    const fullH = await page.evaluate(() => document.documentElement.scrollHeight);
    await page.screenshot({ path: path.join(dir, "desktop_full.png"), fullPage: fullH <= 9000,
      clip: fullH > 9000 ? { x: 0, y: 0, width: 1440, height: 9000 } : undefined });
    m.desktop_height = fullH;
    m.console_errors = errors;
    Object.assign(m, await page.evaluate(() => {
      const cs = el => el ? getComputedStyle(el) : null;
      const pick = sel => { const e = document.querySelector(sel); const c = cs(e); return c ? { font: c.fontFamily, size: c.fontSize, weight: c.fontWeight, color: c.color, transform: c.textTransform } : null; };
      const loaded = [...document.fonts].filter(f => f.status === "loaded").map(f => f.family.replace(/"/g, ""));
      // 段落每行大约多少个字（中文按 1em 一个字，英文按 0.5em 一个字估算）
      const per = [];
      for (const el of document.querySelectorAll("p, li, dd, blockquote")) {
        const t = el.innerText.trim(); if (t.length < 40) continue;
        const r = el.getBoundingClientRect(); if (r.width < 50) continue;
        const fs_ = parseFloat(cs(el).fontSize); const cjk = /[一-鿿]/.test(t);
        per.push(Math.round(r.width / (fs_ * (cjk ? 1 : 0.5))));
      }
      per.sort((a, b) => a - b);
      const upperLabels = [...document.querySelectorAll("body *")].filter(e => e.children.length === 0 && e.innerText && e.innerText.trim().length > 1 && cs(e).textTransform === "uppercase").length;
      const html = document.documentElement.outerHTML;
      return {
        title: document.title,
        body: pick("body"), h1: pick("h1"), button: pick("button, .btn, a.button"),
        fonts_loaded: [...new Set(loaded)],
        body_bg: cs(document.body).backgroundColor,
        chars_per_line_median: per.length ? per[Math.floor(per.length / 2)] : null,
        chars_per_line_max: per.length ? per[per.length - 1] : null,
        reduced_motion_css: /prefers-reduced-motion/.test(html),
        uppercase_labels: upperLabels,
        arrow_in_buttons: [...document.querySelectorAll("a, button")].filter(e => /→/.test(e.innerText)).length,
        numbered_markers: (document.body.innerText.match(/(^|\s)0[1-9](\s|\/|$)/g) || []).length,
        middle_dot_meta: (document.body.innerText.match(/ · /g) || []).length,
      };
    }));
    // 键盘焦点：按 Tab 直到焦点落在可见元素，看有没有可见的焦点样式
    m.focus = null;
    for (let i = 0; i < 4 && !m.focus; i++) {
      await page.keyboard.press("Tab");
      m.focus = await page.evaluate(() => {
        const e = document.activeElement; if (!e || e === document.body) return null;
        const c = getComputedStyle(e);
        const visible = (c.outlineStyle !== "none" && parseFloat(c.outlineWidth) > 0) || (c.boxShadow && c.boxShadow !== "none");
        return { tag: e.tagName, outline: c.outlineStyle + " " + c.outlineWidth, shadow: c.boxShadow, visible };
      });
    }
    // axe 无障碍（WCAG 2 A/AA）
    await page.addScriptTag({ content: AXE });
    const axe = await page.evaluate(async () => {
      const r = await axe.run(document, { runOnly: ["wcag2a", "wcag2aa"] });
      return r.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }));
    });
    m.axe = axe;
    await ctx.close();
    // ---- 手机 ----
    const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const mp = await mctx.newPage();
    await mp.goto(BASE + name, { timeout: 30000 });
    await settle(mp);
    m.mobile_overflow_px = await mp.evaluate(() => Math.max(0, document.documentElement.scrollWidth - innerWidth));
    await mp.screenshot({ path: path.join(dir, "mobile_hero.png") });
    await warm(mp);
    const mh = await mp.evaluate(() => document.documentElement.scrollHeight);
    await mp.screenshot({ path: path.join(dir, "mobile_full.png"), fullPage: mh <= 9000,
      clip: mh > 9000 ? { x: 0, y: 0, width: 390, height: 9000 } : undefined });
    await mctx.close();
    // 滚动录屏改在本机用整页截图平移合成（容器里没有 Playwright 自带的 ffmpeg）
  } catch (e) {
    m.error = String(e).slice(0, 300);
  }
  fs.writeFileSync(path.join(dir, "metrics.json"), JSON.stringify(m, null, 1));
  console.log("ok", name, m.error || "");
}
await browser.close();
