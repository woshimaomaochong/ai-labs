"""汇总 raw.jsonl + judge.jsonl → stats.json，并打印对比表。
价格：DeepSeek 官方高峰价（元/百万 tokens，2026-10-13 查）。回答字数只数非空白字符。"""
import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

WD = Path(__file__).resolve().parent
PRICE = {"deepseek-flash": (2.0, 0.04, 8.0), "deepseek-v4-pro": (9.0, 0.30, 27.0)}  # 未命中输入, 命中输入, 输出
raw = [json.loads(x) for x in (WD / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
jd = {}
if (WD / "judge.jsonl").exists():
    for x in (WD / "judge.jsonl").read_text(encoding="utf-8").splitlines():
        j = json.loads(x)
        jd[(j["model"], j["arm"], j["qid"], j["rep"])] = j


def cost(r):
    if "cost_usd" in r:  # Claude 组用 claude -p 返回的官方标价费用，按 7.1 折人民币
        return r["cost_usd"] * 7.1
    miss, hit, out = PRICE[r["model"]]
    return ((r["prompt_tokens"] - r["cache_hit"]) * miss + r["cache_hit"] * hit + r["completion_tokens"] * out) / 1e6


for r in raw:
    r["chars"] = len("".join(r["answer"].split()))
    r["answer_tokens"] = r["completion_tokens"] - r["reasoning_tokens"]
    r["cost"] = cost(r)
    j = jd.get((r["model"], r["arm"], r["qid"], r["rep"]))
    if j:
        r["cover"] = sum(j["covered"]) / len(j["covered"])
        r["nerr"] = len(j["errors"])
        r["readable"] = j["readable"]

# 按 (模型, 题) 先对 3 次重复取平均，再在 12 题上比较，题目是配对单位
cell = defaultdict(list)
for r in raw:
    cell[(r["model"], r["qid"], r["arm"])].append(r)
FIELDS = ["chars", "answer_tokens", "reasoning_tokens", "completion_tokens", "prompt_tokens", "cost", "sec",
          "cover", "nerr", "readable"]


def avg(rs, f):
    v = [r[f] for r in rs if f in r]
    return st.mean(v) if v else None


models = sorted({r["model"] for r in raw})
qids = sorted({r["qid"] for r in raw})
out = {}
for m in models + ["all"]:
    ms = models if m == "all" else [m]
    res = {}
    for a in "ABC":
        res[a] = {f: st.mean([avg(cell[(mm, q, a)], f) for mm in ms for q in qids if avg(cell[(mm, q, a)], f) is not None] or [0])
                  for f in FIELDS}
    # C 相对 B 的逐题变化（配对），并做置换检验（随机交换 B/C 标签 10000 次）
    diffs = {}
    for f in ["chars", "answer_tokens", "reasoning_tokens", "completion_tokens", "prompt_tokens", "cost", "cover", "nerr", "readable"]:
        pairs = [(avg(cell[(mm, q, "B")], f), avg(cell[(mm, q, "C")], f)) for mm in ms for q in qids]
        pairs = [p for p in pairs if None not in p]
        d = [c - b for b, c in pairs]
        if not d:
            continue
        obs = st.mean(d)
        rnd = random.Random(1)
        n = 0
        for _ in range(10000):
            s = st.mean([x if rnd.random() < .5 else -x for x in d])
            n += abs(s) >= abs(obs) - 1e-12
        cwins = sum(1 for x in d if x < 0) if f not in ("cover", "readable") else sum(1 for x in d if x > 0)
        diffs[f] = {"mean_diff": obs, "p": n / 10000, "n": len(d), "C_better": cwins}
    res["C_vs_B"] = diffs
    out[m] = res

(WD / "stats.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for m, res in out.items():
    print("==", m)
    for a in "ABC":
        x = res[a]
        print(a, " ".join(f"{f}={x[f]:.4f}" if f == "cost" else f"{f}={x[f]:.1f}" if x[f] is not None else f"{f}=-" for f in FIELDS))
    for f, d in res["C_vs_B"].items():
        print("  C-B", f, f"{d['mean_diff']:+.4f}", "p=", d["p"], "C更好", d["C_better"], "/", d["n"])
