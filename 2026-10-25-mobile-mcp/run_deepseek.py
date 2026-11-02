"""DeepSeek（deepseek-flash）+ mobile-mcp 实测：本机自写的工具调用循环，工具和分组与 run_claude.py 相同。
截图结果以图片消息附给模型（工具消息本身只放文字）。
用法：python run_deepseek.py <task_id|all> <A|B|C|ABC> [repeat] → raw/ds_<task>_<arm>_<rep>.json + results.jsonl"""
import json
import sys
import time
from pathlib import Path

import requests
import yaml

import tasks as T
from mcp_client import MCP
from run_claude import ARMS, SYSTEM

HERE = Path(__file__).resolve().parent
KEY = __import__("os").environ["DEEPSEEK_API_KEY"]  # DeepSeek 官方 API key
MODEL = "deepseek-flash"
PRICE = (2.0, 0.04, 8.0)  # 元/百万 tokens：未命中输入、命中输入、输出（2026-10-13 官方价）
MAX_STEPS = 40


def chat(msgs, tools):
    for i in range(4):
        try:
            r = requests.post("https://api.deepseek.com/chat/completions", headers={"Authorization": "Bearer " + KEY},
                              json={"model": MODEL, "messages": msgs, "tools": tools, "temperature": 0},
                              timeout=300, proxies={"http": None, "https": None})
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            print("retry", e, getattr(e, "response", None) and e.response.text[:300], file=sys.stderr)
            time.sleep(5 * (i + 1))
    raise RuntimeError("deepseek failed")


def run(mcp, schemas, task, arm, rep):
    tools = [{"type": "function", "function": {"name": s["name"], "description": s.get("description", "")[:1000],
                                               "parameters": s.get("inputSchema", {"type": "object", "properties": {}})}}
             for s in schemas if s["name"] in ARMS[arm]]
    T.reset()
    time.sleep(3)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task["goal"]}]
    log, calls = [], []
    usage = {"prompt": 0, "hit": 0, "out": 0}
    t0 = time.time()
    final, stop = "", "max_steps"
    for _ in range(MAX_STEPS):
        d = chat(msgs, tools)
        u = d.get("usage", {})
        usage["prompt"] += u.get("prompt_tokens", 0)
        usage["hit"] += u.get("prompt_cache_hit_tokens", 0)
        usage["out"] += u.get("completion_tokens", 0)
        m = d["choices"][0]["message"]
        msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls", "reasoning_content") and v})
        log.append({"assistant": m.get("content"), "tool_calls": m.get("tool_calls")})
        if not m.get("tool_calls"):
            final, stop = m.get("content") or "", "success"
            break
        images = []
        for tc in m["tool_calls"]:
            name = tc["function"]["name"]
            calls.append(name)
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
                res = mcp.tool(name, args) if name in ARMS[arm] else {"content": [{"type": "text", "text": "Error: no such tool"}]}
                text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
                for c in res.get("content", []):
                    if c.get("type") == "image":
                        images.append(f"data:{c.get('mimeType', 'image/png')};base64,{c['data']}")
            except Exception as e:  # noqa: BLE001
                text = f"Error: {e}"
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": text or "(ok)"})
            log.append({"tool": name, "args": tc["function"]["arguments"], "result": text[:3000], "images": len(images)})
        if images:  # 截图附在下一条用户消息里
            msgs.append({"role": "user", "content": [{"type": "text", "text": "这是刚才截图的画面。"}] +
                         [{"type": "image_url", "image_url": {"url": im}} for im in images]})
    dt = time.time() - t0
    (HERE / "raw" / f"ds_{task['id']}_{arm}_{rep}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = T._safe(task["check"])
    miss = usage["prompt"] - usage["hit"]
    cost_cny = (miss * PRICE[0] + usage["hit"] * PRICE[1] + usage["out"] * PRICE[2]) / 1e6
    row = {"model": "deepseek-flash", "task": task["id"], "arm": arm, "rep": rep, "ok": ok is True,
           "seconds": round(dt, 1), "steps": len(calls), "tools": calls, "input_tokens": usage["prompt"],
           "cache_hit": usage["hit"], "output_tokens": usage["out"], "cost_cny": round(cost_cny, 5),
           "final": final[:300], "stop": stop}
    with open(HERE / "results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in row.items() if k != "tools"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    tid, arms = sys.argv[1], sys.argv[2]
    rep = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    mcp = MCP()
    schemas = mcp.tools()
    try:
        for task in T.TASKS:
            if tid in ("all", task["id"]):
                for arm in arms:
                    run(mcp, schemas, task, arm, rep)
    finally:
        mcp.close()
