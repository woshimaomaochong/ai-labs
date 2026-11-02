"""语音第二期汇总表：短句 / 绕口令 / 数字 vs 汉字 / 整段一口气念 5 遍的翻车数。
用法：python summary.py a|k   （a = 成年人参考音，k = 小朋友参考音）"""
import json, statistics as st, sys
from pathlib import Path
from score import per_of

P = "v2" + sys.argv[1]; MODELS = ["voxcpm2", "qwen3tts", "cosyvoice3", "audio8", "breezyvoice", "doubao"]
BAD = 0.2  # 整段念错率超过两成算翻车（漏读、跳字、打转）
# 数字写法的题有不止一种正确念法：拿每种念法比，取最接近的（汉字版那句本身也在里面）
ALT = {1: ["比分三比二，气温{t}五摄氏度，时速{v}" .format(t=t, v=v) for t in ("零下", "负")
           for v in ("一百二十公里每小时", "每小时一百二十公里", "一百二十千米每小时", "每小时一百二十千米")],
       2: ["原价一百九十九元，现价二十九点九美元，便宜了百分之八十五", "原价人民币一百九十九元，现价二十九点九美元，便宜了百分之八十五"],
       3: ["一加一等于二，三乘四等于十二，十除以四等于二点五", "一加一等于二，三乘以四等于十二，十除以四等于二点五"],
       4: ["三分之一的人选了 A，剩下三分之二选了 B", "第三分之一的人选了 A，剩下三分之二选了 B"],  # 数字版原稿多了个「第」
       6: ["二零二六年十月二十八日，谷歌发布 Genie 四", "两千零二十六年十月二十八日，谷歌发布 Genie 四"]}
HAN = json.loads(Path("texts_num.json").read_text(encoding="utf-8"))["hard"]

def load(tag, m):
    f = Path(f"eval_{tag}/{m}.jsonl")
    if not f.exists(): return None
    E = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    for e in E: e["per"] = per_of(e)
    return E

pct = lambda v: f"{v*100:4.1f}%" if v == v else "  - "
rows = {}
for m in MODELS:
    r = {}
    E = load(P, m)
    if E:
        r["短句"] = st.mean(e["per"] for e in E if e["kind"] == "hard")
        r["整段(1遍)"] = st.mean(e["per"] for e in E if e["kind"] == "para_w")
        r["速度"] = st.median(e["secs"] / e["audio_s"] for e in E if e["kind"] != "warmup")
    E = load(P + "tw", m)
    if E: r["绕口令"] = st.mean(e["per"] for e in E if e["kind"] == "hard")
    E = load(P + "num", m)
    if E:
        h = [e for e in E if e["kind"] == "hard"]
        idx = lambda e: int(e["file"].split("_")[1])
        for e in h:
            if idx(e) < 7:
                e["per"] = min(per_of(dict(e, text=t)) for t in ALT.get(idx(e), []) + [HAN[idx(e) + 7]])
        r["数字写法"] = st.mean(e["per"] for e in h if idx(e) < 7)
        r["汉字写法"] = st.mean(e["per"] for e in h if idx(e) >= 7)
    E = load(P + "rep", m)
    if E:
        r["5遍均"] = st.mean(e["per"] for e in E)
        r["翻车"] = f"{sum(e['per'] > BAD for e in E)}/{len(E)}"
        r["最差"] = max(e["per"] for e in E)
    rows[m] = r
cols = ["短句", "绕口令", "数字写法", "汉字写法", "整段(1遍)", "5遍均", "最差", "翻车", "速度"]
print(f"{'模型':12s}" + "".join(f"{c:>9s}" for c in cols))
for m, r in rows.items():
    cell = lambda c: (r[c] if isinstance(r.get(c), str) else (f"{r[c]:.2f}s" if c == "速度" else pct(r[c]))) if c in r else "-"
    print(f"{m:12s}" + "".join(f"{cell(c):>9s}" for c in cols))
Path(f"summary_{P}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
