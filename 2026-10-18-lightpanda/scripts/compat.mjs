// 真实网站兼容性：每个网站两个浏览器各打开一次，记下耗时、标题、正文字数、链接数、能否截图
// node compat.mjs <lp|chrome>
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import fs from "node:fs";

const engine = process.argv[2];
const SITES = [
  ["百度", "https://www.baidu.com"], ["B站", "https://www.bilibili.com"], ["京东", "https://www.jd.com"],
  ["淘宝", "https://www.taobao.com"], ["豆瓣", "https://www.douban.com"], ["IT之家", "https://www.ithome.com"],
  ["少数派", "https://sspai.com"], ["36氪", "https://www.36kr.com"], ["掘金", "https://juejin.cn"],
  ["GitHub 仓库页", "https://github.com/lightpanda-io/browser"], ["React 官网", "https://react.dev"],
  ["亚马逊", "https://www.amazon.com"], ["苹果中国", "https://www.apple.com.cn"], ["小米", "https://www.mi.com"],
];
const sleep = ms => new Promise(r => setTimeout(r, ms));
let browser, kid;
if (engine === "lp") {
  kid = spawn("/work/lightpanda", ["serve", "--host", "127.0.0.1", "--port", "9500", "--log_level", "error"], { stdio: "ignore" });
  await sleep(1200);
  browser = await puppeteer.connect({ browserWSEndpoint: "ws://127.0.0.1:9500" });
} else {
  browser = await puppeteer.launch({ executablePath: "/usr/bin/chromium", headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--lang=zh-CN"] });
}
fs.mkdirSync("/work/compat", { recursive: true });
const rows = [];
for (const [name, url] of SITES) {
  const ctx = engine === "lp" ? await browser.createBrowserContext() : browser.defaultBrowserContext();
  const row = { engine, name, url };
  let page;
  try {
    page = await ctx.newPage();
    await page.setViewport?.({ width: 1280, height: 860 }).catch(() => {});
    const t0 = Date.now();
    await page.goto(url, { waitUntil: "load", timeout: 25000 });
    row.loadMs = Date.now() - t0;
    await sleep(2500);  // 给页面脚本时间把内容渲染出来
    Object.assign(row, await page.evaluate(() => ({
      title: document.title.slice(0, 40),
      textLen: (document.body?.innerText || "").replace(/\s+/g, "").length,
      links: document.querySelectorAll("a[href]").length,
      nodes: document.getElementsByTagName("*").length,
    })));
  } catch (e) {
    row.error = String(e.message).split("\n")[0].slice(0, 100);
  }
  try {
    if (page && !row.error) {
      await page.screenshot({ path: `/work/compat/${engine}_${rows.length}.png` });
      row.shot = "ok";
    }
  } catch (e) {
    row.shot = "失败: " + String(e.message).split("\n")[0].slice(0, 60);
  }
  await page?.close().catch(() => {});
  if (engine === "lp") await ctx.close().catch(() => {});
  rows.push(row);
  console.log(JSON.stringify(row));
}
fs.writeFileSync(`/work/compat_${engine}.json`, JSON.stringify(rows, null, 1));
kid?.kill("SIGKILL");
if (engine === "chrome") await browser.close();
process.exit(0);
