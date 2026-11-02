"""两个听写员对照：同一批配音，Paraformer 和 Nemotron 各听一遍，按同一把尺子（带声调拼音）算念错率。
用法：python cross.py"""
import json, statistics as st, sys
from pathlib import Path
sys.path.insert(0, "../lab")
from score import per_of

nemo = {}
for l in Path("res/tts.json").read_text(encoding="utf-8").splitlines():
    d = json.loads(l); p = d["file"].split("/ttsout/")[1]; nemo[p] = d["text"]
rows, agree = {}, []
for tag in ("v2arep", "v2anum", "dbnum"):
    for f in sorted(Path("../lab/raw", tag).glob("*/eval.jsonl")):
        m = f.parent.name
        for l in f.read_text(encoding="utf-8").splitlines():
            e = json.loads(l); key = f"{tag}/{m}/{e['file']}"
            if key not in nemo or e["kind"] not in ("hard", "para_w"): continue
            a, b = per_of(e), per_of(dict(e, hyp=nemo[key]))
            grp = "整段" if e["kind"] == "para_w" else "数字题"
            rows.setdefault((grp, m), []).append((a, b))
            agree.append(((a > 0.2) == (b > 0.2), key, a, b))
print(f"{'':6s}{'模型':12s}{'Paraformer':>11s}{'Nemotron':>10s}{'条数':>6s}")
for (grp, m), v in sorted(rows.items()):
    print(f"{grp:6s}{m:12s}{st.mean(x for x, _ in v)*100:10.1f}%{st.mean(y for _, y in v)*100:9.1f}%{len(v):6d}")
n = sum(a for a, *_ in agree)
print(f"\n「念错超过两成=翻车」这个判断，两个听写员一致 {n}/{len(agree)} 条；不一致的：")
for ok, k, a, b in agree:
    if not ok: print(f"  {k}  Paraformer {a:.0%}  Nemotron {b:.0%}")
