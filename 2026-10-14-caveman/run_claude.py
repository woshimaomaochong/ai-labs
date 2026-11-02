"""Claude 主场：用 claude -p 开干净会话（不读项目设置、不开工具、系统提示换成实验提示），模型 claude-haiku-5-5。
结果追加到 raw.jsonl，字段与 DeepSeek 组一致；cost 记官方返回的美元（stats.py 换算）。"""
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WD = Path(__file__).resolve().parent
CLEAN = Path(sys.argv[1])  # 空目录，避免读到任何 CLAUDE.md
QS = json.loads((WD / "questions.json").read_text(encoding="utf-8"))
# 接口不允许空系统提示，A 组用中性一句
ARMS = {"A": "你是一个乐于助人的助手。", "B": "请简洁回答。", "C": (WD / "caveman_SKILL.md").read_text(encoding="utf-8")}
MODEL = "claude-haiku-5-5"
CLAUDE_EXE = "C:/nvm4w/nodejs/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
REPS = 3
OUT = WD / "raw.jsonl"
lock = threading.Lock()


def job(key):
    arm, qid, rep = key
    q = next(x for x in QS if x["id"] == qid)
    for _ in range(3):
        p = subprocess.run([CLAUDE_EXE, "-p", q["q"], "--model", MODEL, "--system-prompt", ARMS[arm], "--tools", "",
                            "--setting-sources", "", "--output-format", "json"],
                           cwd=CLEAN, capture_output=True, text=True, encoding="utf-8", timeout=600)
        try:
            d = json.loads(p.stdout)
            if d.get("is_error"):
                raise ValueError(d.get("result"))
            break
        except Exception as e:  # noqa: BLE001
            print("retry", key, e, p.stderr[:300], file=sys.stderr)
    else:
        return
    u = d["usage"]
    rec = {"model": MODEL, "arm": arm, "qid": qid, "rep": rep, "sec": round(d["duration_ms"] / 1000, 1),
           "answer": d["result"],
           "prompt_tokens": u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"],
           "completion_tokens": u["output_tokens"],
           "reasoning_tokens": (u.get("output_tokens_details") or {}).get("thinking_tokens", 0),
           "cache_hit": u["cache_read_input_tokens"], "cost_usd": d["total_cost_usd"]}
    with lock, OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


done = set()
for line in OUT.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if r["model"] == MODEL:
        done.add((r["arm"], r["qid"], r["rep"]))
todo = [(a, q["id"], k) for k in range(REPS) for q in QS for a in ARMS if (a, q["id"], k) not in done]
print("todo", len(todo), flush=True)
with ThreadPoolExecutor(4) as ex:
    list(ex.map(job, todo))
print("done")
