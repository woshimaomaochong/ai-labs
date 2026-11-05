"""汇总：成本/耗时/工具调用（results.jsonl）、截图检查（shots/*/shoot.json）、盲评（judge.jsonl）。输出 stats.json 并打印。
用法：python stats.py [A,B,C]"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

WD = Path(__file__).resolve().parent
ARMS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["A", "B", "C"]
CONCEPTS = [c["id"] for c in json.loads((WD / "concepts.json").read_text(encoding="utf-8"))]
out = {}

runs = [json.loads(l) for l in (WD / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
for arm in ARMS:
    base, rep = arm[0], (arm[1:] or "1")
    rs = [r for r in runs if r["arm"] == base and str(r.get("rep", "1")) == rep and r["html_bytes"] > 0]
    o = out.setdefault(arm, {})
    if rs:
        o["n"] = len(rs)
        o["cost_usd"] = round(mean(r["cost_usd"] for r in rs), 3)
        o["cost_fen"] = round(mean(r["cost_usd"] for r in rs) * 7.1 * 100, 1)
        o["secs"] = round(mean(r["secs"] for r in rs))
        o["tool_calls"] = round(mean(r["tool_calls"] for r in rs), 1)
        o["out_tokens"] = round(mean(r["usage"]["output_tokens"] for r in rs if r.get("usage")))
        o["html_kb"] = round(mean(r["html_bytes"] for r in rs) / 1024, 1)
    sh = [json.loads((WD / "shots" / f"{c}_{arm}" / "shoot.json").read_text(encoding="utf-8"))
          for c in CONCEPTS if (WD / "shots" / f"{c}_{arm}" / "shoot.json").exists()]
    if sh:
        o["pages_with_errors"] = sum(1 for s in sh if s["errors"])
        o["svg_shapes"] = round(mean(s.get("svg_shapes", 0) for s in sh))
        o["phone_hscroll"] = sum(1 for s in sh if s.get("phone_hscroll"))
        o["moves_idle"] = sum(1 for s in sh if s.get("idle_change", 0) > 0.002)

jrows = [json.loads(l) for l in (WD / "judge.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()] \
    if (WD / "judge.jsonl").exists() else []
want = ",".join(ARMS)
for judge in sorted({r["judge"] for r in jrows}):
    rows = [r for r in jrows if r["judge"] == judge and r.get("set", "A,B,C") == want]
    acc = defaultdict(lambda: defaultdict(list))
    best = defaultdict(int)
    for r in rows:
        if r.get("best"):
            best[r["best"]] += 1
        for arm, s in r["scores"].items():
            f = [x for x in s.get("facts", []) if isinstance(x, (int, float))]
            if f:
                acc[arm]["facts_pct"].append(sum(f) / (2 * len(f)) * 100)
                acc[arm]["facts_shown_by_motion"].append(sum(1 for x in f if x == 2))
            for k in ("看得懂", "像实物", "精致"):
                if isinstance(s.get(k), (int, float)):
                    acc[arm][k].append(s[k])
            e = str(s.get("错误", "0")).strip()
            acc[arm]["has_error"].append(0 if e in ("0", "", "无", "没有") else 1)
    for arm in ARMS:
        a = acc.get(arm, {})
        out[arm][f"judge_{judge}"] = {k: round(mean(v), 2) for k, v in a.items() if v}
        out[arm][f"judge_{judge}"]["best_votes"] = best.get(arm, 0)
        out[arm][f"judge_{judge}"]["rounds"] = len(rows)

(WD / f"stats_{'_'.join(ARMS)}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
