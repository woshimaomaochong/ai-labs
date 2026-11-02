# Lightpanda 对比 Chrome（2026-10-18）

视频：号称比Chrome快9倍的AI浏览器，实测：省内存是真的，快9倍打折
被测项目：https://github.com/lightpanda-io/browser（官方测试站点和方法：https://github.com/lightpanda-io/demo）

## 实验（都在服务器的隔离容器里跑）
- `scripts/bench.mjs`：照官方方法，从 Amiibo 演示站首页起爬完全部子页面（940 页），记录耗时和内存峰值。并发 1 个和 25 个，每组 3 次。结果在 `data/bench_results.jsonl`。
- `scripts/compat.mjs`：14 个常用网站，两个浏览器各打开一次，记下耗时、标题、正文字数、链接数、能否截图。结果在 `data/compat_*.json`。
- `scripts/probe.mjs`：拆开看每页时间花在打开页面还是等链接上。
- `scripts/conns.sh`：数一次爬虫一共开了几个网络连接。

## 运行
```
npm i puppeteer-core
node scripts/bench.mjs lp 1        # 或 chrome；第二个参数是并发数
node scripts/compat.mjs lp
```
Lightpanda 和 Chrome 需要先装好，并以 CDP 方式启动（见脚本开头）。

## 边界
直连海外站点时 Lightpanda 反而比 Chrome 慢（50 页 60 秒对 38 秒），原因我们没查明。
