"""录屏版实测：与 run_claude.py 同样的干净会话和工具分组，另外用手机自带 screenrecord 录屏，并给每一步记时间戳。
用法：python rec_run.py <task_id> <A|B|C> <tag> → rec/<tag>.mp4 + rec/<tag>.json（steps: t 秒, tool, input, text）"""
import json
import subprocess
import sys
import time
from pathlib import Path

import tasks as T
from run_claude import ARMS, ALL, CLAUDE_EXE, MCP_CFG, MODEL, SYSTEM, MAX_TURNS

HERE = Path(__file__).resolve().parent
REC = HERE / "rec"
REC.mkdir(exist_ok=True)
ADB = T.ADB


def dexec(cmd, detach=False, timeout=120):
    d = "-d " if detach else ""
    return subprocess.run(["ssh", "-o", "ConnectTimeout=10", "gpu-server",
                           f"docker exec {d}mm-lab bash -lc '{cmd}'"], capture_output=True, timeout=timeout)


def main(tid, arm, tag):
    task = next(t for t in T.TASKS if t["id"] == tid)
    T.reset()
    time.sleep(3)
    dexec(f"{ADB} shell rm -f /sdcard/rec.mp4")
    dexec(f"{ADB} shell screenrecord --bit-rate 6000000 --time-limit 180 /sdcard/rec.mp4", detach=True)
    time.sleep(1.5)
    t0 = time.time()
    allowed = [f"mcp__mobile__{n}" for n in ARMS[arm]]
    denied = [f"mcp__mobile__{n}" for n in ALL if n not in ARMS[arm]]
    cmd = [CLAUDE_EXE, "-p", task["goal"], "--model", MODEL, "--system-prompt", SYSTEM, "--tools", "",
           "--setting-sources", "", "--mcp-config", str(MCP_CFG), "--strict-mcp-config",
           "--allowedTools", ",".join(allowed), "--disallowedTools", ",".join(denied),
           "--max-turns", str(MAX_TURNS), "--output-format", "stream-json", "--verbose"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=str(HERE / "raw"))
    steps, result = [], {}
    for line in p.stdout:
        t = round(time.time() - t0, 2)
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("type") == "assistant":
            for c in m["message"].get("content", []):
                if c.get("type") == "tool_use":
                    steps.append({"t": t, "tool": c["name"].replace("mcp__mobile__", ""), "input": c["input"]})
                elif c.get("type") == "text" and c["text"].strip():
                    steps.append({"t": t, "say": c["text"].strip()[:400]})
        elif m.get("type") == "user":
            for c in m["message"].get("content", []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    cc = c.get("content")
                    txt = cc if isinstance(cc, str) else " ".join(x.get("text", "") for x in cc if isinstance(x, dict))
                    steps.append({"t": t, "result": txt[:300]})
        elif m.get("type") == "result":
            result = m
    p.wait()
    dt = round(time.time() - t0, 2)
    time.sleep(2)
    dexec(f"pkill -INT screenrecord; sleep 3; {ADB} shell pkill -INT screenrecord; sleep 3; {ADB} pull /sdcard/rec.mp4 /work/rec_{tag}.mp4")
    subprocess.run(["scp", "-q", f"gpu-server:/srv/lab/mobile-mcp/work/rec_{tag}.mp4", str(REC / f"{tag}.mp4")], check=True)
    ok = T._safe(task["check"])
    u = result.get("usage", {})
    meta = {"task": tid, "goal": task["goal"], "arm": arm, "ok": ok is True, "seconds": dt,
            "record_offset": 1.5, "cost_usd": result.get("total_cost_usd"), "final": result.get("result"),
            "input_tokens": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
            "n_calls": sum(1 for s in steps if "tool" in s), "steps": steps}
    (REC / f"{tag}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(tag, "ok" if ok is True else "FAIL", meta["n_calls"], "calls", dt, "s", meta["cost_usd"])


if __name__ == "__main__":
    main(*sys.argv[1:4])
