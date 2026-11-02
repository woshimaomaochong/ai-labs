// 拆开看每页时间：goto 和等链接各花多少
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
const engine = process.argv[2], base = process.argv[3] || "https://demo-browser.lightpanda.io/amiibo/";
const sleep = ms => new Promise(r => setTimeout(r, ms));
let browser, kid;
if (engine === "lp") {
  kid = spawn("/work/lightpanda", ["serve", "--host", "127.0.0.1", "--port", "9400", "--log_level", "error"], { stdio: "ignore" });
  await sleep(1000); browser = await puppeteer.connect({ browserWSEndpoint: "ws://127.0.0.1:9400" });
} else browser = await puppeteer.launch({ executablePath: "/usr/bin/chromium", headless: "new", args: ["--no-sandbox", "--disable-dev-shm-usage"] });
const ctx = engine === "lp" ? await browser.createBrowserContext() : browser.defaultBrowserContext();
let url = base;
for (let i = 0; i < 5; i++) {
  const page = await ctx.newPage();
  const t0 = Date.now(); await page.goto(url, { waitUntil: "load", timeout: 30000 });
  const t1 = Date.now(); await page.waitForSelector("a[href]", { timeout: 15000 });
  const t2 = Date.now();
  const links = await page.evaluate(() => [...document.querySelectorAll("a[href]")].map(a => a.href));
  console.log(engine, i, "goto", t1 - t0, "wait", t2 - t1, "links", links.length);
  url = links.find(l => l.startsWith(base) && l !== url) || url;
  await page.close();
}
kid?.kill("SIGKILL"); await browser.close?.().catch(()=>{}); process.exit(0);
