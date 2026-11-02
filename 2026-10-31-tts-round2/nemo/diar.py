"""Nemotron 说话人分辨打分：把它切出的每段文字按字对回台词稿（difflib 逐字对齐），
算：分出几个人、每句是否分给对的人、每句转出了多少字（抢话的句子单独看）。
用法：python diar.py res/spk.json"""
import json, re, sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

clean = lambda t: re.sub(r"[^\w]|_", "", t.lower())
TRUTH = {"media/dialog.wav": "dialog_truth.json", "media/overlap.wav": "overlap_truth.json",
         "media/bgvoice.wav": "bgvoice_truth.json", "media/final_mix.wav": "dialog_truth.json"}
for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    d = json.loads(l); segs = d.get("segments") or []
    truth = json.loads(Path(TRUTH[d["file"]]).read_text(encoding="utf-8"))
    print(f"== {d['file']}  结束方式 {d.get('stop')}  分段 {len(segs)}" + (f"  无时间：{d['untimed']}" if d.get("untimed") else ""))
    if not segs: continue
    R, rl = "", []
    for i, t in enumerate(truth):
        c = clean(t["text"]); R += c; rl += [i] * len(c)
    H, hs = "", []
    for s in segs:
        c = clean(s["text"]); H += c; hs += [s["speaker"]] * len(c)
    got = defaultdict(Counter)  # 台词第 i 句 → 被标成各号说话人的字数
    for a, b, n in SequenceMatcher(None, R, H, autojunk=False).get_matching_blocks():
        for k in range(n): got[rl[a + k]][hs[b + k]] += 1
    vote = defaultdict(Counter)
    for i, c in got.items():
        for spk, n in c.items(): vote[spk][truth[i]["who"]] += n
    m = {spk: c.most_common(1)[0][0] for spk, c in vote.items()}
    extra = len(H) - sum(sum(c.values()) for c in got.values())
    print("  它分出的人：", {spk: dict(c) for spk, c in sorted(vote.items())}, "→ 对应", m)
    ok = cov_ov = n_ov = cov_no = n_no = 0
    for i, t in enumerate(truth):
        c = got.get(i, Counter()); n = sum(c.values()); cov = n / max(1, len(clean(t["text"])))
        main = c.most_common(1)[0][0] if c else None; right = main is not None and m.get(main) == t["who"]; ok += right
        ov = (i > 0 and t["start"] < truth[i - 1]["end"]) or (i + 1 < len(truth) and truth[i + 1]["start"] < t["end"])
        if ov: cov_ov += cov; n_ov += 1
        else: cov_no += cov; n_no += 1
        if not right or cov < 0.85:
            print(f"   {'×' if not right else '·'} 第{i+1:2d}句 {t['who']} 转出 {cov:4.0%} 标成 {dict(c)}  {t['text'][:24]}")
    print(f"  分对的句子 {ok}/{len(truth)}；平均转出字数 不抢话 {cov_no/max(1,n_no):.0%}" + (f"，抢话的句子 {cov_ov/n_ov:.0%}（{n_ov} 句）" if n_ov else "") + f"；对不上台词的多余字 {extra}")
