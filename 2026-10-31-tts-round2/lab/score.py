"""在 eval.jsonl 的转写结果上重新计分（本机，miniconda 有 pypinyin）。
念错率 = 汉字按带声调拼音逐字比（同音字不算错）；数字两边都转成中文读法再比；英文词单独列出交给人耳。
用法：python score.py <eval 目录>"""
import json, math, re, statistics as st, sys
from pathlib import Path
from pypinyin import lazy_pinyin, Style

DIG = "零一二三四五六七八九"


def num_cn(m):
    s = m.group(0)
    if "." in s:
        a, b = s.split("."); return num_cn(re.match(r"\d+", a)) + "点" + "".join(DIG[int(c)] for c in b)
    n = int(s)
    if n == 0: return "零"
    out, units = "", [(10**8, "亿"), (10**4, "万"), (1000, "千"), (100, "百"), (10, "十")]
    def part(n):
        r, z = "", False
        for v, u in units[2:]:
            q, n = divmod(n, v)
            if q: r += ("零" if z else "") + DIG[q] + u; z = False
            elif r: z = True
        if n: r += ("零" if z and r else "") + DIG[n]
        return r
    for v, u in units[:2]:
        q, n = divmod(n, v)
        if q: out += part(q) + u
    out += part(n) if n else ""
    return re.sub(r"^一十", "十", out)


def canon(t, hyp=None):
    """hyp：识别结果。紧跟字母的数字是型号（RTX 4090、K90），逐位读也算对——按识别结果选读法；单独的数字（价格）只认数值读法。"""
    t = t.lower().replace("％", "%")
    t = re.sub(r"(\d{4})年", lambda m: "".join(DIG[int(c)] for c in m.group(1)) + "年", t)  # 年份逐位读
    if hyp is not None:
        def model_no(m):
            digits = "".join(DIG[int(c)] for c in m.group(2))
            return m.group(1) + (digits if digits in hyp and num_cn(re.match(r"\d+", m.group(2))) not in hyp else m.group(2))
        t = re.sub(r"([a-z]\s*)(\d+)(?![\d.%])", model_no, t)
    t = re.sub(r"(\d+(?:\.\d+)?)%", lambda m: "百分之" + num_cn(re.match(r"[\d.]+", m.group(1))), t)
    t = re.sub(r"\d+(?:\.\d+)?", num_cn, t)
    t = t.replace("两", "二")  # 「两个」「二个」都对
    eng = re.findall(r"[a-z]+", t)
    zh = re.sub(r"[^\u4e00-\u9fff]", "", t)
    return lazy_pinyin(zh, style=Style.TONE3, neutral_tone_with_five=True), eng


def edits(r, h):
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return d[len(h)]


def semis(fs):
    fs = [f for f in fs if f]; md = st.median(fs); return [12 * math.log2(f / md) for f in fs]


def per_of(e):  # 一条结果的念错率（带声调拼音逐字比）
    hyp_zh = re.sub(r"\d+(?:\.\d+)?", num_cn, e["hyp"].lower())
    (rp, _), (hp, _) = canon(e["text"], hyp_zh), canon(e["hyp"])
    return edits(rp, hp) / max(1, len(rp))


if __name__ == "__main__":
    D = Path(sys.argv[1]); rows = {}
    for f in sorted(D.glob("*.jsonl")):
        if f.stem.endswith("_metrics"): continue
        E = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]
        bad = []
        for e in E:
            hyp_zh = re.sub(r"\d+(?:\.\d+)?", num_cn, e["hyp"].lower())
            (rp, re_), (hp, he) = canon(e["text"], hyp_zh), canon(e["hyp"])
            e["per"] = edits(rp, hp) / max(1, len(rp))
            if e["per"] > 0 and e["kind"] == "hard":
                bad.append((e["file"], e["text"], e["hyp"]))
            e["eng_ref"], e["eng_hyp"] = re_, he
        hard = [e for e in E if e["kind"] == "hard"]; para = [e for e in E if e["kind"] in ("para_s", "para_w")]
        ps = [e for e in E if e["kind"] == "para_s"]; pw = [e for e in E if e["kind"] == "para_w"]
        s_sd = [st.pstdev(semis([e["f0"] for e in ps if e["file"].startswith(pid + "_s")])) for pid in sorted({e["file"].split("_s")[0] for e in ps})]
        w_sd = [st.pstdev(semis([s["f0"] for s in e["sentences"]])) for e in pw]
        s_db = [st.pstdev([e["db"] for e in ps if e["file"].startswith(pid + "_s")]) for pid in sorted({e["file"].split("_s")[0] for e in ps})]
        w_db = [st.pstdev([s["db"] for s in e["sentences"]]) for e in pw]
        rtf = [e["secs"] / e["audio_s"] for e in E if e["kind"] != "warmup"]
        rows[f.stem] = dict(hard_per=st.mean(e["per"] for e in hard), para_per=st.mean([e["per"] for e in para] or [float("nan")]),
                            pitch_sd_sent=st.mean(s_sd or [float('nan')]), pitch_sd_whole=st.mean(w_sd or [float('nan')]), db_sd_sent=st.mean(s_db or [float('nan')]), db_sd_whole=st.mean(w_db or [float('nan')]),
                            rtf=st.median(rtf), bad=bad)
        print(f"{f.stem:9s} 难读句念错率 {rows[f.stem]['hard_per']*100:4.1f}%  整段念错率 {rows[f.stem]['para_per']*100:4.1f}%  "
              f"句间音高波动 逐句 {st.mean(s_sd or [float('nan')]):.2f} / 整段 {st.mean(w_sd or [float('nan')]):.2f}  音量波动 逐句 {st.mean(s_db or [float('nan')]):.2f} / 整段 {st.mean(w_db or [float('nan')]):.2f} dB  生成1秒 {st.median(rtf):.2f}s")
        for b in bad: print("   ", b[0][:11], "|", b[1], "→", b[2])
    (D / "scores.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
