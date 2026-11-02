#!/bin/sh
# 在 fe-lab 容器里运行：对 pages/ 下每个网页跑 Lighthouse（桌面预设），结果只留四项分数和没通过的检查项
cd /work
for f in pages/*.html; do
  n=$(basename "$f" .html)
  [ -f "out/$n/lh.json" ] && continue
  mkdir -p "out/$n"
  npx --no-install lighthouse "http://127.0.0.1:8000/$n.html" --chrome-path=/usr/bin/chromium \
    --chrome-flags="--headless=new --no-sandbox" --preset=desktop --output=json --output-path="out/$n/lh_full.json" \
    --only-categories=performance,accessibility,best-practices,seo --quiet >/dev/null 2>&1
  node -e '
    const r = JSON.parse(require("fs").readFileSync(process.argv[1]));
    const cats = Object.fromEntries(Object.entries(r.categories).map(([k, v]) => [k, v.score]));
    const failed = Object.values(r.audits).filter(a => a.score !== null && a.score < 0.9 && a.scoreDisplayMode === "binary").map(a => a.id);
    require("fs").writeFileSync(process.argv[2], JSON.stringify({ cats, failed }, null, 1));
  ' "out/$n/lh_full.json" "out/$n/lh.json" && rm -f "out/$n/lh_full.json" && echo "lh $n"
done
