"""给 Claude 盲评做拼图：每道题两版随机放左右（方案1/方案2），对照表写进 blind_key.json（评完才读）。
输出 blind/<bid>.png：上排两版桌面整页缩略（各宽 560，最高 2600），下排两版手机首屏。
评完后 python blind.py --merge 把 blind_scores.json（按方案1/2记）换算成 A/B，追加进 judge.jsonl（judge=claude）。"""
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WD = Path(__file__).resolve().parent
BIDS = [b["id"] for b in json.loads((WD / "briefs.json").read_text(encoding="utf-8"))]
KEY, OUT = WD / "blind_key.json", WD / "blind"
FONT = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 40)


def make():
    OUT.mkdir(exist_ok=True)
    key = json.loads(KEY.read_text(encoding="utf-8")) if KEY.exists() else {}
    rng = random.Random(20261022)
    for bid in BIDS:
        if not all((WD / "shots" / f"{a}_{bid}_0" / "desktop_full.png").exists() for a in "AB"):
            continue
        if bid not in key:
            key[bid] = rng.sample(["A", "B"], 2)  # [方案1, 方案2]
        cols = []
        for arm in key[bid]:
            d = WD / "shots" / f"{arm}_{bid}_0"
            full = Image.open(d / "desktop_full.png").convert("RGB")
            full = full.resize((560, round(full.height * 560 / full.width)))
            full = full.crop((0, 0, 560, min(full.height, 2600)))
            mob = Image.open(d / "mobile_hero.png").convert("RGB")
            mob = mob.resize((300, round(mob.height * 300 / mob.width)))
            cols.append((full, mob))
        h = max(c[0].height for c in cols) + max(c[1].height for c in cols) + 140
        cv = Image.new("RGB", (1200, h), "white")
        dr = ImageDraw.Draw(cv)
        for k, (full, mob) in enumerate(cols):
            x = 20 + k * 600
            dr.text((x, 10), f"方案{k + 1}", fill="black", font=FONT)
            cv.paste(full, (x, 70))
            cv.paste(mob, (x + 130, 90 + max(c[0].height for c in cols)))
        cv.save(OUT / f"{bid}.png")
    KEY.write_text(json.dumps(key), encoding="utf-8")


def merge():
    key = json.loads(KEY.read_text(encoding="utf-8"))
    sc = json.loads((WD / "blind_scores.json").read_text(encoding="utf-8"))
    with (WD / "judge.jsonl").open("a", encoding="utf-8") as f:
        for bid, d in sc.items():
            p1, p2 = key[bid]
            win = {1: p1, 2: p2}.get(d["winner"], "tie")
            rec = {"judge": "claude", "bid": bid, "order": p1 + p2, "winner": win,
                   "scores": {p1: d["s1"], p2: d["s2"]}, "reason": d.get("reason", "")}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            # analyze 按两次一致合并；Claude 只评一次，再写一条同结论的反序记录占位
            rec2 = dict(rec, order=p2 + p1)
            f.write(json.dumps(rec2, ensure_ascii=False) + "\n")
    print("merged", len(sc))


if __name__ == "__main__":
    merge() if "--merge" in sys.argv else make()
