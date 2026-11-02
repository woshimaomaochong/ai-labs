"""评分（服务器容器 venv_dl 里跑）：Paraformer 转写 → 错字率；逐句音高/响度 → 稳定性。
用法：python evaluate.py <out 目录，如 /work/out/temp>；结果写 <目录>/<模型>/eval.jsonl"""
import json, re, sys
from pathlib import Path
import numpy as np, soundfile as sf
import cn2an
from funasr import AutoModel

ROOT = Path(sys.argv[1])
asr = AutoModel(model="paraformer-zh", disable_update=True)  # 带逐字时间戳


def norm(t):
    t = t.lower().replace("％", "%")
    try:
        t = cn2an.transform(t, "cn2an")  # 识别结果里的中文数字 → 阿拉伯数字
    except Exception:
        pass
    return re.sub(r"[^\w%.]|_", "", t).replace("。", "")


def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r)), r, h


def f0_median(x, sr):
    import librosa
    if sr != 16000:
        x = librosa.resample(x, orig_sr=sr, target_sr=16000); sr = 16000
    f, v, _ = librosa.pyin(x, fmin=70, fmax=500, sr=sr, frame_length=1024)
    f = f[v & ~np.isnan(f)]
    return float(np.median(f)) if len(f) else None


def rms_db(x):
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9))


def load(p):
    x, sr = sf.read(p, dtype="float32")
    return (x.mean(1) if x.ndim > 1 else x), sr


for mdir in sorted(d for d in ROOT.iterdir() if d.is_dir()):
    recs = [json.loads(l) for l in (mdir / "metrics.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    seen, out = set(), (mdir / "eval.jsonl").open("w", encoding="utf-8")
    for r in recs:
        if r["kind"] == "warmup" or r["file"] in seen:
            continue
        seen.add(r["file"])
        x, sr = load(mdir / r["file"])
        res = asr.generate(input=str(mdir / r["file"]), sentence_timestamp=False)[0]
        hyp = res["text"].replace(" ", "")
        c, rn, hn = cer(r["text"], hyp)
        e = dict(r, hyp=hyp, cer=round(c, 4), ref_n=rn, hyp_n=hn, f0=f0_median(x, sr), db=rms_db(x))
        if r["kind"] == "para_w":  # 用逐字时间戳切回各句
            ts = res.get("timestamp") or []
            chars = [ch for ch in res["text"].split(" ") if ch]
            sents = next(p["sentences"] for p in json.loads(Path("/work/texts.json").read_text(encoding="utf-8"))["paragraphs"]
                         if r["file"].startswith(f"para_{p['id']}_whole"))
            lens = [len(norm(s)) for s in sents]
            total = sum(lens); per = []
            if ts:
                n, k = len(ts), 0
                for L in lens:  # 按原稿各句字数占比分配识别出来的字
                    cnt = max(1, round(L / total * n)); seg = ts[k:k + cnt]; k += cnt
                    if not seg: break
                    a, b = seg[0][0] / 1000, seg[-1][1] / 1000
                    y = x[int(a * sr):int(b * sr)]
                    per.append(dict(start=a, end=b, f0=f0_median(y, sr), db=rms_db(y)))
            e["sentences"] = per
        out.write(json.dumps(e, ensure_ascii=False) + "\n"); out.flush()
        print(mdir.name, r["file"], round(c, 3), flush=True)
