"""豆包小何（日报同款设置）跑同一份测试稿。本机运行（调云端接口）。"""
import asyncio, json, os, subprocess, sys, time
from pathlib import Path
# doubao_tts 是我们自己对豆包语音合成 2.0 接口的封装（未开源），可换成火山引擎官方 SDK；音色 zh_female_xiaohe_uranus_bigtts
import yaml
from doubao_tts import DoubaoTTS
T = json.loads(Path(os.environ.get("TEXTS", "texts.json")).read_text(encoding="utf-8"))
import os
OUT = Path(os.environ.get("DB_OUT", "out/doubao")); OUT.mkdir(parents=True, exist_ok=True)
tts = DoubaoTTS({"app_id": os.environ["DOUBAO_APP_ID"], "access_key": os.environ["DOUBAO_ACCESS_KEY"],
                 "speaker": "zh_female_xiaohe_uranus_bigtts"})
log = (OUT / "metrics.jsonl").open("a", encoding="utf-8")

async def gen(text, fn, kind):
    if (OUT / fn).exists(): return
    mp3 = OUT / (fn[:-4] + ".mp3"); t0 = time.time()
    await tts.synthesize(text, str(mp3)); dt = time.time() - t0
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(mp3), str(OUT / fn)], check=True); mp3.unlink()
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(OUT / fn)], capture_output=True, text=True).stdout)
    log.write(json.dumps(dict(model="doubao", kind=kind, file=fn, text=text, secs=round(dt, 3), audio_s=round(d, 3)), ensure_ascii=False) + "\n"); log.flush()

async def main():
    if os.environ.get("WHOLE_REPEAT"):
        for k in range(int(os.environ["WHOLE_REPEAT"])):
            for p in T["paragraphs"]: await gen("".join(p["sentences"]), f"para_{p['id']}_whole_rep{k}.wav", "para_w")
        print("done rep"); return
    for i, s in enumerate(T["hard"]):
        for r in range(int(os.environ.get("HARD_REPS", 2))): await gen(s, f"hard_{i:02d}_r{r}.wav", "hard")
    for p in T["paragraphs"]:
        for j, s in enumerate(p["sentences"]): await gen(s, f"para_{p['id']}_s{j}.wav", "para_s")
        await gen("".join(p["sentences"]), f"para_{p['id']}_whole.wav", "para_w")
    print("done", len(list(OUT.glob("*.wav"))))
asyncio.run(main())
