"""声纹相似度：CAM++ 说话人模型（funasr），每段输出与参考录音的余弦相似度。
注意：CosyVoice3 克隆时也用 CAM++ 声纹做条件，这个分数可能偏向它。用法：python spk_sim.py <ref.wav> <目录...>"""
import json, sys
from pathlib import Path
import numpy as np
from funasr import AutoModel
m = AutoModel(model="cam++", disable_update=True)

def emb(p):
    e = m.generate(input=str(p))[0]["spk_embedding"].reshape(-1).float().cpu().numpy(); return e / np.linalg.norm(e)

ref = emb(sys.argv[1])
for d in sys.argv[2:]:
    d = Path(d); out = {}
    for f in sorted(d.glob("*.wav")):
        if f.stem == "warmup" or "_rep" in f.stem: continue
        out[f.name] = float(np.dot(ref, emb(f)))
    (d / "spk_sim.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    v = list(out.values()); print(d.parent.name + "/" + d.name, "相似度均值", round(float(np.mean(v)), 3), "最低", round(min(v), 3), "最高", round(max(v), 3), "n", len(v), flush=True)
