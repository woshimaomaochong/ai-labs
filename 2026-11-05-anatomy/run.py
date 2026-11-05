"""anatomy 技能实测：同一模型、同一工具（全部在服务器容器里执行），A 组不装技能，B 组装 anatomy。
用法：python run.py <概念id|all> <A|B|C|ABC> [并发数]（C = 不装技能 + 一句话要求）
产物：raw/<概念>_<组>.jsonl（对话流）、results.jsonl；网页在服务器 work(_a)/runs/<概念>_<组>/figure.html
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "raw"
RAW.mkdir(exist_ok=True)
PY = sys.executable
CLAUDE_EXE = os.environ.get("CLAUDE_EXE", "claude")
MODEL = "claude-sonnet-5-5"
MAX_TURNS = 400
TIME_LIMIT = 100 * 60
CONTAINER = {"A": "an-lab-a", "B": "an-lab", "C": "an-lab-a"}
# C 组：不装技能，只在要求末尾多一句技能的核心思路
ONE_LINE = "请把这个概念画成一台真实的、零件很多的精细等距（isometric）机器：机器怎么动，就代表概念怎么工作。"
SKILL_MD = (HERE / "src" / "SKILL.md").read_text(encoding="utf-8")

CONCEPTS = json.loads((HERE / "concepts.json").read_text(encoding="utf-8"))

BASE = ("You are Claude Code, an AI coding agent working for a user. All of your tools run inside a Linux "
        "workspace (Debian, Node.js 22, Chromium at /usr/bin/chromium, Noto CJK fonts, npm can reach the internet). "
        "Your working folder is {dir}; keep all your files there and do not read other folders under /work/runs. "
        "Work autonomously to the end: the user will not answer questions. "
        "The deliverable is {dir}/figure.html, a standalone page that opens offline in a browser.")
SKILL = ("\n\nInstalled skill: anatomy, at /work/anatomy (relative paths in it such as kit/, scripts/, examples/, "
         "references/ are under /work/anatomy). The user invoked this skill for the request. Its SKILL.md:\n\n"
         "<skill name=\"anatomy\">\n" + SKILL_MD + "\n</skill>")

lock = threading.Lock()
REP = sys.argv[4] if len(sys.argv) > 4 else ""  # 第几轮重复（空 = 第 1 轮，"2" = 第 2 轮）


def run_one(cid, arm):
    c = next(x for x in CONCEPTS if x["id"] == cid)
    wd = f"/work/runs/{cid}_{arm}{REP}"
    cfg = HERE / f"mcp_{cid}_{arm}{REP}.json"
    cfg.write_text(json.dumps({"mcpServers": {"box": {"command": PY, "args": [str(HERE / "box_mcp.py"), CONTAINER[arm], wd]}}}),
                   encoding="utf-8")
    subprocess.run(["ssh", "-o", "LogLevel=ERROR", "gpu-server",
                    f"docker exec {CONTAINER[arm]} bash -lc 'rm -rf {wd} && mkdir -p {wd}'"], check=True)
    system = BASE.format(dir=wd) + (SKILL if arm == "B" else "")
    tools = ["mcp__box__bash", "mcp__box__write_file", "mcp__box__read_file", "mcp__box__view_image"]
    out = RAW / f"{cid}_{arm}{REP}.jsonl"
    spf = HERE / f"sys_{cid}_{arm}{REP}.txt"
    spf.write_text(system, encoding="utf-8")
    prompt = c["prompt"] + (ONE_LINE if arm == "C" else "")
    cmd = [CLAUDE_EXE, "-p", prompt, "--model", MODEL, "--system-prompt-file", str(spf), "--tools", "",
           "--setting-sources", "", "--mcp-config", str(cfg), "--strict-mcp-config",
           "--allowedTools", ",".join(tools), "--max-turns", str(MAX_TURNS),
           "--output-format", "stream-json", "--verbose"]
    empty = HERE / "empty"
    empty.mkdir(exist_ok=True)
    t0 = time.time()
    with open(out, "w", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=empty, stdin=subprocess.DEVNULL)
        try:
            p.wait(timeout=TIME_LIMIT)
            timed_out = False
        except subprocess.TimeoutExpired:
            p.kill()
            timed_out = True
    secs = time.time() - t0
    res = {}
    calls = 0
    for line in out.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("type") == "result":
            res = m
        if m.get("type") == "assistant":
            calls += sum(1 for b in m["message"].get("content", []) if b.get("type") == "tool_use")
    chk = subprocess.run(["ssh", "-o", "LogLevel=ERROR", "gpu-server",
                          f"docker exec {CONTAINER[arm]} bash -lc 'stat -c %s {wd}/figure.html 2>/dev/null || echo 0'"],
                         capture_output=True, text=True)
    row = {"concept": cid, "arm": arm, "rep": REP or "1", "model": MODEL, "secs": round(secs), "timed_out": timed_out,
           "turns": res.get("num_turns"), "tool_calls": calls, "cost_usd": res.get("total_cost_usd"),
           "usage": res.get("usage"), "subtype": res.get("subtype"),
           "html_bytes": int((chk.stdout.strip() or "0").splitlines()[-1]), "t": time.strftime("%m-%d %H:%M")}
    with lock:
        with open(HERE / "results.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps({k: row[k] for k in ("concept", "arm", "secs", "turns", "tool_calls", "cost_usd", "html_bytes")}), flush=True)


def main():
    which, arms = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    ids = [c["id"] for c in CONCEPTS] if which == "all" else which.split(",")
    jobs = [(i, a) for i in ids for a in arms]
    sem = threading.Semaphore(n)

    def go(j):
        with sem:
            try:
                run_one(*j)
            except Exception as e:  # noqa
                print("FAIL", j, e, flush=True)

    ts = [threading.Thread(target=go, args=(j,)) for j in jobs]
    for t in ts:
        t.start()
        time.sleep(3)
    for t in ts:
        t.join()


if __name__ == "__main__":
    main()
