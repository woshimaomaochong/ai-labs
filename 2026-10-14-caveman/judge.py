"""盲评：deepseek-v4-pro 只看到问题、事先写好的要点和一份回答（不知道是哪组），逐条判要点是否覆盖、有无错误、普通人读得懂吗。
结果追加到 judge.jsonl（已评的不重评）。"""
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import yaml

WD = Path(__file__).resolve().parent
KEY = __import__("os").environ["DEEPSEEK_API_KEY"]  # DeepSeek 官方 API key
QS = {q["id"]: q for q in json.loads((WD / "questions.json").read_text(encoding="utf-8"))}
OUT = WD / "judge.jsonl"
lock = threading.Lock()

PROMPT = """你是严格的评卷老师。下面是一个用户问题、事先定好的评分要点，以及一份回答。
逐条判断回答是否覆盖了每个要点（意思到了就算，不要求字面一致；回答说法与要点矛盾算没覆盖）。
再找出回答里的事实错误或可能误导用户的地方（没有就留空）。
最后给「普通人读得懂吗」打 1~5 分（5=一读就懂，1=像电报看不懂）。

问题：{q}

要点：
{points}

回答：
<<<
{a}
>>>

只输出 JSON：{{"covered": [每个要点 true/false，共 {n} 个], "errors": ["..."], "readable": 1到5的整数}}"""


def key(r):
    return (r["model"], r["arm"], r["qid"], r["rep"])


def job(r):
    q = QS[r["qid"]]
    pts = "\n".join(f"{i+1}. {p}" for i, p in enumerate(q["points"]))
    msg = PROMPT.format(q=q["q"], points=pts, a=r["answer"], n=len(q["points"]))
    for i in range(4):
        try:
            resp = requests.post("https://api.deepseek.com/chat/completions", headers={"Authorization": "Bearer " + KEY},
                                 json={"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": msg}],
                                       "response_format": {"type": "json_object"}},
                                 timeout=300, proxies={"http": None, "https": None})
            resp.raise_for_status()
            j = json.loads(resp.json()["choices"][0]["message"]["content"])
            cov = [bool(x) for x in j["covered"]][:len(q["points"])]
            if len(cov) != len(q["points"]):
                raise ValueError("covered length")
            out = {"model": r["model"], "arm": r["arm"], "qid": r["qid"], "rep": r["rep"],
                   "covered": cov, "errors": j.get("errors") or [], "readable": int(j["readable"])}
            with lock, OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
            return
        except Exception as e:  # noqa: BLE001
            print("retry", key(r), e, file=sys.stderr)
            time.sleep(5 * (i + 1))


raw = [json.loads(x) for x in (WD / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
done = set()
if OUT.exists():
    done = {key(json.loads(x)) for x in OUT.read_text(encoding="utf-8").splitlines()}
todo = [r for r in raw if key(r) not in done]
random.seed(7)
random.shuffle(todo)
print("todo", len(todo))
with ThreadPoolExecutor(8) as ex:
    list(ex.map(job, todo))
print("done")
