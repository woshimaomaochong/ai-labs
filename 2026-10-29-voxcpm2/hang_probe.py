"""绕口令里每个「行」切出来单独听写，看识别出来是什么字（服务器 venv_dl）。用法：python hang_probe.py <wav...>"""
import json, sys
import soundfile as sf
from funasr import AutoModel
asr = AutoModel(model="paraformer-zh", disable_update=True)
out = {}
for p in sys.argv[1:]:
    x, sr = sf.read(p, dtype="float32"); x = x.mean(1) if x.ndim > 1 else x
    r = asr.generate(input=p)[0]
    toks, ts = r["text"].split(" "), r.get("timestamp", [])
    res = []
    for k, (t, (a, b)) in enumerate(zip(toks, ts)):
        if t != "行": continue
        seg = x[max(0, int((a / 1000 - .04) * sr)):int((b / 1000 + .04) * sr)]
        sf.write("/tmp/seg.wav", seg, sr)
        h = asr.generate(input="/tmp/seg.wav")[0]["text"].replace(" ", "")
        res.append(dict(k=k, start=a, end=b, iso=h))
    out[p] = dict(full=r["text"].replace(" ", ""), hang=res)
    print(p.split("/")[-2], p.split("/")[-1], len(res), "个行 →", " ".join(z["iso"] or "∅" for z in res), flush=True)
json.dump(out, open("/work/hang_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
