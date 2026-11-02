"""用声学特征判断每个「行」读 xíng 还是 háng（服务器 venv_dl）。
x 是舌面擦音（高频嘶声），h 是舌根擦音（低频）；ing 和 ang 的元音第一共振峰也不同。
做法：识别时间戳定位每个「行」→ 取开头 70ms 的高频能量比（4~10kHz / 全频）和后段的谱质心。
用法：python hang_acoustic.py <wav...>"""
import json, sys
import numpy as np, soundfile as sf, librosa
from funasr import AutoModel
EXP = list("xhxhhxhhxxhxhhxhhx")  # 18 个「行」的正确读法（x=xíng, h=háng）
asr = AutoModel(model="paraformer-zh", disable_update=True)
out = {}
for p in sys.argv[1:]:
    x, sr = sf.read(p, dtype="float32"); x = x.mean(1) if x.ndim > 1 else x
    if sr != 24000: x = librosa.resample(x, orig_sr=sr, target_sr=24000); sr = 24000
    r = asr.generate(input=p)[0]
    toks, ts = r["text"].split(" "), r.get("timestamp", [])
    import difflib, re
    REF = re.sub(r"[^一-鿿]", "", "人要是行，干一行，行一行。一行行，行行行；要是不行，干一行，不行一行。一行不行，行行不行。")
    chars = [(t, a) for t, (a, b) in zip(toks, ts) if len(t) == 1]
    sm = difflib.SequenceMatcher(None, REF, "".join(c for c, _ in chars), autojunk=False)
    pos = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("equal", "replace") and i2 - i1 == j2 - j1:
            for k in range(i2 - i1): pos[i1 + k] = j1 + k
    hang_ref = [i for i, c in enumerate(REF) if c == "行"]
    feats = []
    for n, i in enumerate(hang_ref):
        if i not in pos or chars[pos[i]][0] != "行":
            feats.append(dict(n=n, hi=None)); continue
        a = chars[pos[i]][1]
        s = int(a / 1000 * sr); seg = x[max(0, s - int(.03 * sr)): s + int(.09 * sr)]  # 声母附近
        S = np.abs(librosa.stft(seg, n_fft=512, hop_length=128)) ** 2
        f = librosa.fft_frequencies(sr=sr, n_fft=512)
        hi = S[(f >= 4000)].sum(0) / (S.sum(0) + 1e-12)
        feats.append(dict(n=n, start=a, hi=float(hi.max())))  # 声母最「嘶」的一帧的高频占比
    out[p] = dict(full=r["text"].replace(" ", ""), feats=feats)
    got = "".join("?" if z["hi"] is None else ("x" if z["hi"] > .4 else "h") for z in feats)
    wrong = [n + 1 for n, (g, e) in enumerate(zip(got, EXP)) if g != "?" and g != e]
    print(p.split("/")[-2], p.split("/")[-1], "正确", "".join(EXP), "| 实际", got, "| 错位", wrong, "| 高频", " ".join("--" if z["hi"] is None else f"{z['hi']:.2f}" for z in feats), flush=True)
json.dump(out, open("/work/hang_acoustic.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
