"""三组盲评：同一概念的 A（不装技能）/ B（装 anatomy）/ C（一句话要求）随机标成方案1/2/3，
换两种顺序各评一次（消除位置偏好）。裁判：DeepSeek（看图）、豆包 Seed（看图）。
输入 shots/<概念>_<组>/desktop.png、after.png、shoot.json；输出 judge.jsonl。
用法：python judge.py deepseek|doubao|claude [A,B,C | A2,B2]"""
import base64
import io
import json
import os
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

WD = Path(__file__).resolve().parent
CONCEPTS = json.loads((WD / "concepts.json").read_text(encoding="utf-8"))
OUT = WD / "judge.jsonl"
ARMS = sys.argv[2].split(",") if len(sys.argv) > 2 else ["A", "B", "C"]  # 例：A2,B2 评第二轮
PROMPT = """你在评审几张「交互式科普插图」网页。题目：解释「{name}」是怎么工作的。观众是没学过编程的普通人。
下面依次给出 {n} 个方案。每个方案两张截图：刚打开时、点过按钮/拖动之后，另附页面上的文字。请只根据这些材料独立评审，不要猜是谁做的。

一、对每个方案，逐条判断下面 {k} 个要点在图里有没有讲到：0 = 没有；1 = 只在文字里说了；2 = 画面里的东西动起来/状态变化就能看出来。
要点：{facts}
二、每个方案各打 1~5 分：
- 看得懂：没基础的人看完能不能明白这个概念
- 像实物：是不是一台让人一眼认出的真实机器/物件（而不是方框箭头图表）
- 精致：做工细节、好不好看
- 有错误：图里有没有讲错的地方（填 0 表示没发现，否则写出错在哪）
三、哪个方案整体最能让普通人看懂（填方案编号），一句话理由。
只输出 JSON：{{"s": {{"1": {{"facts": [..], "看得懂": n, "像实物": n, "精致": n, "错误": "0或说明"}}, ...}}, "best": n, "reason": "..."}}"""
lock = threading.Lock()


def img_b64(p, w=900):
    im = Image.open(p).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def ask(judge, content):
    if judge == "deepseek":
        url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/") + "/chat/completions"
        key, model = os.environ["DEEPSEEK_API_KEY"], os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
    else:
        url, key, model = "https://ark.cn-beijing.volces.com/api/v3/chat/completions", os.environ["ARK_API_KEY"], "doubao-seed-2-1-pro-260915"
    body = {"model": model, "temperature": 0.1, "messages": [{"role": "user", "content": content}]}
    if judge == "deepseek":
        body["response_format"] = {"type": "json_object"}
    r = requests.post(url, headers={"Authorization": "Bearer " + key}, json=body, timeout=400,
                      proxies={"http": None, "https": None})
    r.raise_for_status()
    t = r.json()["choices"][0]["message"]["content"]
    return json.loads(t[t.find("{"): t.rfind("}") + 1])


def ask_claude(c, order, rnd):
    """Claude Opus 当裁判：图片放进只含匿名文件的空目录，claude -p 只给 Read 工具去看。"""
    import shutil
    import subprocess
    d = WD / "judge_claude" / f"{c['id']}_{rnd}"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    lines = []
    for k, arm in enumerate(order):
        src = WD / "shots" / f"{c['id']}_{arm}"
        for nm in ("desktop", "after"):
            im = Image.open(src / f"{nm}.png").convert("RGB")
            im.thumbnail((1100, 1100))
            im.save(d / f"方案{k + 1}_{'刚打开' if nm == 'desktop' else '操作之后'}.jpg", quality=85)
        sj = json.loads((src / "shoot.json").read_text(encoding="utf-8"))
        lines.append(f"【方案{k + 1}】页面文字：" + (sj.get("visible_text") or "")[:1200])
    (d / "页面文字.txt").write_text("\n\n".join(lines), encoding="utf-8")
    prompt = PROMPT.format(name=c["name"], n=len(order), k=len(c["facts"]),
                           facts="；".join(f"{i + 1}. {f}" for i, f in enumerate(c["facts"])))
    prompt += ("\n\n材料都在当前目录：每个方案两张图（方案N_刚打开.jpg、方案N_操作之后.jpg），以及 页面文字.txt。"
               "请用 Read 工具逐个看完再评。最后只输出 JSON。")
    exe = os.environ.get("CLAUDE_EXE", "claude")
    r = subprocess.run([exe, "-p", prompt, "--model", "claude-opus-5-5", "--tools", "Read", "--allowedTools", "Read",
                        "--setting-sources", "", "--output-format", "json"], cwd=d, capture_output=True,
                       text=True, encoding="utf-8", timeout=900, stdin=subprocess.DEVNULL)
    t = json.loads(r.stdout)["result"]
    return json.loads(t[t.find("{"): t.rfind("}") + 1])


def job(judge, c, order, rnd):
    content = [{"type": "text", "text": PROMPT.format(name=c["name"], n=len(order), k=len(c["facts"]),
                                                      facts="；".join(f"{i + 1}. {f}" for i, f in enumerate(c["facts"])))}]
    for k, arm in enumerate(order):
        d = WD / "shots" / f"{c['id']}_{arm}"
        sj = json.loads((d / "shoot.json").read_text(encoding="utf-8"))
        content += [{"type": "text", "text": f"\n【方案{k + 1}】刚打开："},
                    {"type": "image_url", "image_url": {"url": img_b64(d / "desktop.png")}},
                    {"type": "text", "text": "操作之后："},
                    {"type": "image_url", "image_url": {"url": img_b64(d / "after.png")}},
                    {"type": "text", "text": "页面文字：" + (sj.get("visible_text") or "")[:1200]}]
    try:
        r = ask_claude(c, order, rnd) if judge == "claude" else ask(judge, content)
    except Exception as e:  # noqa
        print("FAIL", judge, c["id"], order, e, flush=True)
        return
    row = {"judge": judge, "concept": c["id"], "order": "|".join(order), "round": rnd, "set": ",".join(ARMS),
           "scores": {order[int(k) - 1]: v for k, v in r.get("s", {}).items() if k.isdigit() and int(k) <= len(order)},
           "best": order[int(r["best"]) - 1] if str(r.get("best", "")).isdigit() and 0 < int(r["best"]) <= len(order) else None,
           "reason": r.get("reason")}
    with lock, OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(judge, c["id"], row["order"], "best", row["best"], flush=True)


def main():
    judge = sys.argv[1]
    rng = random.Random(20261103)
    jobs = []
    for c in CONCEPTS:
        if not all((WD / "shots" / f"{c['id']}_{a}" / "after.png").exists() for a in ARMS):
            print("skip", c["id"])
            continue
        o1 = rng.sample(list(ARMS), len(ARMS))
        jobs += [(judge, c, o1, 1), (judge, c, o1[::-1], 2)]  # 正序、倒序各一次
    with ThreadPoolExecutor(1 if judge == "claude" else 4) as ex:
        list(ex.map(lambda j: job(*j), jobs))


if __name__ == "__main__":
    main()
