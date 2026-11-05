// 在服务器容器里打开每个 figure.html：截图（桌面/手机）、检查报错、量交互和动画、数图元。
// 用法：node shoot.mjs <figure.html> <输出目录>
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import path from "node:path";
import { PNG } from "pngjs";

const [file, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const browser = await puppeteer.launch({
  executablePath: "/usr/bin/chromium",
  args: ["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--disable-dev-shm-usage"],
});
const res = { file, errors: [] };
const diff = (a, b) => { // 两张截图里变了的像素占比
  const A = PNG.sync.read(Buffer.from(a)), B = PNG.sync.read(Buffer.from(b));
  if (A.width !== B.width || A.height !== B.height) return 1;
  let d = 0;
  for (let i = 0; i < A.data.length; i += 4)
    if (Math.abs(A.data[i] - B.data[i]) + Math.abs(A.data[i + 1] - B.data[i + 1]) + Math.abs(A.data[i + 2] - B.data[i + 2]) > 24) d++;
  return +(d / (A.width * A.height)).toFixed(4);
};
try {
  const page = await browser.newPage();
  page.on("pageerror", e => res.errors.push("pageerror: " + String(e.message).slice(0, 200)));
  page.on("console", m => { if (m.type() === "error") res.errors.push("console: " + m.text().slice(0, 200)); });
  page.on("requestfailed", r => { if (!r.url().startsWith("data:")) res.errors.push("netfail: " + r.url().slice(0, 120)); });
  await page.setViewport({ width: 1280, height: 860, deviceScaleFactor: 1 });
  await page.goto("file://" + path.resolve(file), { waitUntil: "load", timeout: 30000 });
  await new Promise(r => setTimeout(r, 2500));
  const s1 = await page.screenshot({ path: `${outDir}/desktop.png` });
  await new Promise(r => setTimeout(r, 1500));
  const s2 = await page.screenshot({ path: `${outDir}/desktop_t2.png` });
  res.idle_change = diff(s1, s2); // 不操作时画面是否在动
  res.full_height = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.screenshot({ path: `${outDir}/full.png`, fullPage: true });
  Object.assign(res, await page.evaluate(() => {
    const q = s => document.querySelectorAll(s).length;
    return {
      svg_shapes: q("svg path, svg polygon, svg rect, svg circle, svg ellipse, svg line, svg polyline"),
      canvas: q("canvas"), buttons: q("button, input, select, [role=button]"),
      text_len: document.body.innerText.length,
      hscroll: document.documentElement.scrollWidth > window.innerWidth + 2,
    };
  }));
  // 交互：依次点所有按钮/拨动滑块，看画面变不变
  const before = await page.screenshot();
  const ctrls = await page.$$("button, input[type=range], [role=button]");
  let acted = 0;
  for (const c of ctrls.slice(0, 8)) {
    try {
      const tag = await c.evaluate(e => e.tagName + ":" + (e.type || ""));
      if (tag === "INPUT:range") await c.evaluate(e => { e.value = e.max || 100; e.dispatchEvent(new Event("input", { bubbles: true })); e.dispatchEvent(new Event("change", { bubbles: true })); });
      else await c.click({ delay: 30 });
      acted++; await new Promise(r => setTimeout(r, 400));
    } catch {}
  }
  // 鼠标在画面中部移动、按住拖动
  await page.mouse.move(400, 400); await page.mouse.down(); await page.mouse.move(800, 450, { steps: 12 }); await page.mouse.up();
  await new Promise(r => setTimeout(r, 1500));
  const after = await page.screenshot({ path: `${outDir}/after.png` });
  res.controls = ctrls.length; res.acted = acted; res.interact_change = diff(before, after);
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 });
  await page.goto("file://" + path.resolve(file), { waitUntil: "load", timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: `${outDir}/phone.png` });
  res.phone_hscroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  res.visible_text = (await page.evaluate(() => document.body.innerText)).slice(0, 4000);
} catch (e) { res.errors.push("fatal: " + e.message); }
await browser.close();
fs.writeFileSync(`${outDir}/shoot.json`, JSON.stringify(res, null, 1));
console.log(JSON.stringify({ file, errors: res.errors.length, shapes: res.svg_shapes, idle: res.idle_change, inter: res.interact_change }));
