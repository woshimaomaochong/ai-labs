"""frontend-design 技能实测：同一模型（claude -p 干净会话、不开工具、不读项目设置），A 组无技能 / B 组系统提示附技能原文。
每份结果：pages/<arm>_<bid>_<rep>.html + raw.jsonl 一行（用量、费用、耗时）。
用法：python run.py <空目录> [--reps 3] [--only b01,b02] [--workers 4]"""
import argparse
import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WD = Path(__file__).resolve().parent
BRIEFS = json.loads((WD / "briefs.json").read_text(encoding="utf-8"))
BASE = ("你是一名前端工程师。根据用户的需求做一个网页：只输出一个完整、可以直接用浏览器打开的 HTML 文件"
        "（CSS 和 JS 都写在这个文件里，可以引用公开 CDN 上的字体或库），用 ```html 代码块包起来。"
        "不要向用户提问，信息不足时自己做合理假设。")
ARMS = {"A": BASE, "B": BASE + "\n\n" + (WD / "frontend-design_SKILL.md").read_text(encoding="utf-8")}
MODEL = "claude-sonnet-5-5"
CLAUDE_EXE = "C:/nvm4w/nodejs/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
OUT, PAGES = WD / "raw.jsonl", WD / "pages"
lock = threading.Lock()


def extract(text):
    m = re.findall(r"```html\s*\n(.*?)```", text, re.S)
    if m:
        return max(m, key=len)
    i = text.find("<!DOCTYPE")
    return text[i:] if i >= 0 else None


def job(key, clean):
    arm, bid, rep = key
    b = next(x for x in BRIEFS if x["id"] == bid)
    for _ in range(3):
        p = subprocess.run([CLAUDE_EXE, "-p", b["brief"], "--model", MODEL, "--system-prompt", ARMS[arm], "--tools", "",
                            "--setting-sources", "", "--output-format", "json"],
                           cwd=clean, capture_output=True, text=True, encoding="utf-8", timeout=1200)
        try:
            d = json.loads(p.stdout)
            if d.get("is_error"):
                raise ValueError(d.get("result"))
            html = extract(d["result"])
            if not html:
                raise ValueError("no html")
            break
        except Exception as e:  # noqa: BLE001
            print("retry", key, e, p.stderr[:300], file=sys.stderr, flush=True)
    else:
        return
    name = f"{arm}_{bid}_{rep}.html"
    (PAGES / name).write_text(html, encoding="utf-8")
    u = d["usage"]
    rec = {"model": MODEL, "arm": arm, "bid": bid, "rep": rep, "file": name, "sec": round(d["duration_ms"] / 1000, 1),
           "prompt_tokens": u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"],
           "completion_tokens": u["output_tokens"], "cost_usd": d["total_cost_usd"], "html_bytes": len(html.encode()),
           "plan": d["result"].split("```html")[0].strip()[:4000]}
    with lock, OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("ok", name, rec["sec"], "s", round(rec["cost_usd"], 3), "$", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("clean")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    PAGES.mkdir(exist_ok=True)
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["arm"], r["bid"], r["rep"]))
    only = set(a.only.split(",")) if a.only else None
    todo = [(arm, b["id"], k) for k in range(a.reps) for b in BRIEFS for arm in ARMS
            if (not only or b["id"] in only) and (arm, b["id"], k) not in done]
    print("todo", len(todo), flush=True)
    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(lambda k: job(k, a.clean), todo))
    print("done")
