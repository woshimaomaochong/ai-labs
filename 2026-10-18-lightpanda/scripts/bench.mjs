// 复现 Lightpanda 官方爬虫测试：Amiibo 演示站从首页起爬完全部子页面，对比耗时和内存峰值。
// node bench.mjs <lp|chrome> <并发数> [最多页数]
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import fs from "node:fs";

const [engine, poolArg, limitArg, baseArg] = process.argv.slice(2);
const POOL = +poolArg || 1, LIMIT = +limitArg || 100000;
const START = baseArg || "https://demo-browser.lightpanda.io/amiibo/";  // 第 4 个参数：换成本地镜像
const sleep = ms => new Promise(r => setTimeout(r, ms));

// 内存：每 100ms 把引擎所有进程的 PSS 加起来（共享页按比例算，和官方用的 smem 同口径），取峰值
const procName = engine === "lp" ? "/work/lightpanda" : "chromium";
function pssMB() {
  let kb = 0;
  for (const pid of fs.readdirSync("/proc").filter(d => /^\d+$/.test(d))) {
    try {
      const cmd = fs.readFileSync(`/proc/${pid}/cmdline`, "utf8");
      if (!cmd.startsWith(procName) && !cmd.includes("/usr/lib/chromium/chromium")) continue;
      if (engine === "lp" && !cmd.startsWith("/work/lightpanda")) continue;
      const m = fs.readFileSync(`/proc/${pid}/smaps_rollup`, "utf8").match(/^Pss:\s+(\d+)/m);
      if (m) kb += +m[1];
    } catch {}
  }
  return kb / 1024;
}

const kids = [];
async function launch() {
  if (engine === "lp") {  // 官方做法：Lightpanda 开 N 个进程，每个进程一个连接
    const eps = [];
    for (let i = 0; i < POOL; i++) {
      const port = 9300 + i;
      kids.push(spawn("/work/lightpanda", ["serve", "--host", "127.0.0.1", "--port", String(port), "--log_level", "error"], { stdio: "ignore" }));
      eps.push(`ws://127.0.0.1:${port}`);
    }
    await sleep(1500);
    return Promise.all(eps.map(async ep => ({ browser: await puppeteer.connect({ browserWSEndpoint: ep }) })));
  }
  // Chrome：一个浏览器开 N 个标签页（官方做法）
  const b = await puppeteer.launch({ executablePath: "/usr/bin/chromium", headless: "new",
    args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--user-data-dir=/tmp/bench_chrome_" + Date.now()] });
  return Array.from({ length: POOL }, () => ({ browser: b, shared: true }));
}

const t0 = Date.now();
let peak = 0;
const timer = setInterval(() => { peak = Math.max(peak, pssMB()); }, 100);
const workers = await launch();
const seen = new Set([START]), queue = [START];
let done = 0, failed = 0, active = 0;
const errors = {};

async function work(w) {
  const ctx = w.shared ? null : await w.browser.createBrowserContext();
  let page = w.shared ? await w.browser.newPage() : null;
  if (page && process.env.NOCACHE) await page.setCacheEnabled(false);  // 验证：关掉 Chrome 缓存，看是不是缓存让它在慢网络下领先
  while (true) {
    const url = queue.shift();
    if (!url) { if (active === 0) break; await sleep(20); continue; }
    active++;
    try {
      if (!w.shared) page = await ctx.newPage();
      await page.goto(url, { waitUntil: "load", timeout: 30000 });
      await page.waitForSelector("a[href]", { timeout: 15000 });  // 官方爬虫同样等链接出现（链接由页面 JS 填进来）
      const links = await page.evaluate(() => [...document.querySelectorAll("a[href]")].map(a => a.href));
      for (const l of links) {
        const u = l.split("#")[0];
        if (u.startsWith(START) && !seen.has(u) && seen.size < LIMIT) { seen.add(u); queue.push(u); }
      }
      done++;
    } catch (e) {
      failed++; const k = String(e.message).slice(0, 80); errors[k] = (errors[k] || 0) + 1;
    } finally {
      if (!w.shared && page) await page.close().catch(() => {});
      active--;
    }
  }
}
await Promise.all(workers.map(work));
const secs = (Date.now() - t0) / 1000;
clearInterval(timer);
const out = { engine, pool: POOL, pages: done, failed, seconds: +secs.toFixed(2), peakMB: +peak.toFixed(1), errors };
console.log(JSON.stringify(out));
fs.appendFileSync("/work/bench_results.jsonl", JSON.stringify({ ...out, at: new Date().toISOString() }) + "\n");
for (const w of workers) { try { w.shared ? null : await w.browser.disconnect(); } catch {} }
if (engine === "chrome") await workers[0].browser.close().catch(() => {});
kids.forEach(k => k.kill("SIGKILL"));
process.exit(0);
