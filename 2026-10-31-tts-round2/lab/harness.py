"""三个开源 TTS 共用的测试流程（在服务器容器里运行）。
每个模型实现 load() / prepare(ref_wav, ref_text) / synth(text) -> (np.float32 一维波形, 采样率)。
任务：hard（难读句，每句 2 次）、para_s（整段逐句合成）、para_w（整段一次合成），记录用时和显存。
用法：python run_<模型>.py <参考wav> <参考原文> <输出目录名>"""
import json, sys, time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

import os
TEXTS = json.loads(Path(os.environ.get("TEXTS", "/work/texts.json")).read_text(encoding="utf-8"))


def run(name, model):
    ref_wav, ref_text, tag = sys.argv[1], sys.argv[2], sys.argv[3]
    out = Path("/work/out") / tag / name
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "metrics.jsonl").open("a", encoding="utf-8")
    t = time.time(); model.load(); load_s = time.time() - t
    model.prepare(ref_wav, ref_text)
    torch.cuda.reset_peak_memory_stats()

    def gen(text, fn, kind):
        torch.cuda.synchronize(); t0 = time.time()
        wav, sr = model.synth(text)
        torch.cuda.synchronize(); dt = time.time() - t0
        sf.write(out / fn, wav, sr)
        rec = dict(model=name, kind=kind, file=fn, text=text, secs=round(dt, 3),
                   audio_s=round(len(wav) / sr, 3), sr=sr)
        log.write(json.dumps(rec, ensure_ascii=False) + "\n"); log.flush()
        print(name, kind, fn, f"{dt:.1f}s / {len(wav) / sr:.1f}s", flush=True)

    gen("大家好，这是一段热身。", "warmup.wav", "warmup")  # 首次调用含编译/缓存，不计入
    import os
    if os.environ.get("WHOLE_REPEAT"):  # 只测整段一次合成的翻车率：每段重复 N 次
        for k in range(int(os.environ["WHOLE_REPEAT"])):
            for p in TEXTS["paragraphs"]:
                gen("".join(p["sentences"]), f"para_{p['id']}_whole_rep{k}.wav", "para_w")
        print("done", name); return
    for i, s in enumerate(TEXTS["hard"]):
        for r in range(int(os.environ.get("HARD_REPS", 2))):
            gen(s, f"hard_{i:02d}_r{r}.wav", "hard")
    for p in TEXTS["paragraphs"]:
        for j, s in enumerate(p["sentences"]):
            gen(s, f"para_{p['id']}_s{j}.wav", "para_s")
        gen("".join(p["sentences"]), f"para_{p['id']}_whole.wav", "para_w")
    peak = torch.cuda.max_memory_allocated() / 2**30
    (out / "summary.json").write_text(json.dumps(dict(model=name, load_s=round(load_s, 1), peak_vram_gb=round(peak, 2),
                                                      torch=torch.__version__), ensure_ascii=False), encoding="utf-8")
    print("done", name, f"peak {peak:.2f} GB")


def to_np(x):
    if isinstance(x, torch.Tensor):
        x = x.detach().float().cpu().numpy()
    x = np.asarray(x, dtype=np.float32)
    return x.reshape(-1) if x.ndim > 1 and min(x.shape) == 1 else (x.mean(0) if x.ndim > 1 else x)
