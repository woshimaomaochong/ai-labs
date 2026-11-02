"""caveman 技能实测：3 组 × 12 题 × 2 模型 × 3 次，原始结果追加到 raw.jsonl（已有的不重跑）。
A 组：不加要求；B 组：系统提示「请简洁回答。」；C 组：系统提示为 caveman SKILL.md 全文（commit 2e08b91）。"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import yaml

WD = Path(__file__).resolve().parent
KEY = __import__("os").environ["DEEPSEEK_API_KEY"]  # DeepSeek 官方 API key
QS = json.loads((WD / "questions.json").read_text(encoding="utf-8"))
ARMS = {"A": None, "B": "请简洁回答。", "C": (WD / "caveman_SKILL.md").read_text(encoding="utf-8")}
MODELS = ["deepseek-flash", "deepseek-v4-pro"]
REPS = 3
OUT = WD / "raw.jsonl"
lock = threading.Lock()


def call(model, system, user):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    for i in range(4):
        try:
            t = time.time()
            r = requests.post("https://api.deepseek.com/chat/completions", headers={"Authorization": "Bearer " + KEY},
                              json={"model": model, "messages": msgs}, timeout=300, proxies={"http": None, "https": None})
            r.raise_for_status()
            d = r.json()
            return d, time.time() - t
        except Exception as e:  # noqa: BLE001
            print("retry", model, e, file=sys.stderr)
            time.sleep(5 * (i + 1))
    raise RuntimeError("failed")


def job(key):
    model, arm, qid, rep = key
    q = next(x for x in QS if x["id"] == qid)
    d, sec = call(model, ARMS[arm], q["q"])
    u = d["usage"]
    rec = {"model": model, "arm": arm, "qid": qid, "rep": rep, "sec": round(sec, 1),
           "answer": d["choices"][0]["message"]["content"],
           "prompt_tokens": u["prompt_tokens"], "completion_tokens": u["completion_tokens"],
           "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
           "cache_hit": u.get("prompt_cache_hit_tokens", 0)}
    with lock, OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


done = set()
if OUT.exists():
    for line in OUT.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        done.add((r["model"], r["arm"], r["qid"], r["rep"]))
todo = [(m, a, q["id"], k) for k in range(REPS) for m in MODELS for q in QS for a in ARMS if (m, a, q["id"], k) not in done]
print("todo", len(todo))
with ThreadPoolExecutor(8) as ex:
    for i, _ in enumerate(ex.map(job, todo)):
        if i % 20 == 0:
            print(i, flush=True)
print("done")
