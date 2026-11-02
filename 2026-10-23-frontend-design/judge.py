"""成对盲评：同一道题的两版网页（A 无技能 / B 有技能）随机标成「方案1/方案2」，每对正反各评一次（消除位置偏好）。
裁判：DeepSeek（deepseek-flash 看图）、豆包（doubao-seed-2-1-pro，需在方舟开通）。
输入 shots/<文件名>/desktop_full.png、mobile_hero.png；输出 judge.jsonl。用法：python judge.py deepseek|doubao"""
import base64
import io
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import yaml
from PIL import Image

WD = Path(__file__).resolve().parent
ROOT = WD.parents[1]
ENV = __import__("os").environ
BRIEFS = {b["id"]: b for b in json.loads((WD / "briefs.json").read_text(encoding="utf-8"))}
OUT = WD / "judge.jsonl"
DIMS = ["排版与字体", "配色", "视觉层次", "贴合主题", "原创性（不像模板）", "清晰好用"]
PROMPT = """你是资深网页设计评审。客户需求：「{brief}」
下面依次是两个方案的截图：先是方案1（桌面整页、手机首屏），再是方案2（桌面整页、手机首屏）。
请只根据截图独立评审，不要猜测方案是谁做的。按 6 个维度给两个方案各打 1~5 分：{dims}。
再给出总体更好的方案（1、2，或者确实分不出时填 0），以及一句话理由。
只输出 JSON：{{"s1": {{维度: 分数}}, "s2": {{维度: 分数}}, "winner": 1|2|0, "reason": "..."}}"""
lock = threading.Lock()


def img_b64(p, w):
    im = Image.open(p).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)))
    im = im.crop((0, 0, im.width, min(im.height, w * 4)))  # 太长的整页只取前 4 屏宽的高度
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def ask(judge, content):
    if judge == "deepseek":
        url, key, model = "https://api.deepseek.com/chat/completions", ENV["DEEPSEEK_API_KEY"], "deepseek-chat"
    else:
        url, key, model = "https://ark.cn-beijing.volces.com/api/v3/chat/completions", ENV["ARK_API_KEY"], "doubao-seed-2-1-pro-260915"
    body = {"model": model, "temperature": 0.1, "messages": [{"role": "user", "content": content}]}
    if judge == "deepseek":
        body["response_format"] = {"type": "json_object"}
    r = requests.post(url, headers={"Authorization": "Bearer " + key}, json=body, timeout=300,
                      proxies={"http": None, "https": None})
    r.raise_for_status()
    t = r.json()["choices"][0]["message"]["content"]
    return json.loads(t[t.find("{"): t.rfind("}") + 1])


def job(judge, bid, order):
    first, second = order  # 例如 ("A","B")：方案1 = A
    content = []
    for arm in (first, second):
        d = WD / "shots" / f"{arm}_{bid}_0"
        content += [{"type": "image_url", "image_url": {"url": img_b64(d / "desktop_full.png", 900)}},
                    {"type": "image_url", "image_url": {"url": img_b64(d / "mobile_hero.png", 390)}}]
    content.append({"type": "text", "text": PROMPT.format(brief=BRIEFS[bid]["brief"], dims="、".join(DIMS))})
    for _ in range(3):
        try:
            d = ask(judge, content)
            win = {1: first, 2: second}.get(int(d.get("winner", 0)), "tie")
            rec = {"judge": judge, "bid": bid, "order": "".join(order), "winner": win,
                   "scores": {first: d["s1"], second: d["s2"]}, "reason": d.get("reason", "")}
            break
        except Exception as e:  # noqa: BLE001
            print("retry", judge, bid, order, e, flush=True)
    else:
        return
    with lock, OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("ok", judge, bid, "".join(order), win, flush=True)


if __name__ == "__main__":
    judge = sys.argv[1]
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["judge"], r["bid"], r["order"]))
    todo = [(judge, bid, o) for bid in BRIEFS for o in (("A", "B"), ("B", "A"))
            if (judge, bid, "".join(o)) not in done
            and all((WD / "shots" / f"{a}_{bid}_0" / "desktop_full.png").exists() for a in "AB")]
    print("todo", len(todo), flush=True)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda k: job(*k), todo))
