"""Claude Code + mobile-mcp 实测（README 推荐用法）：claude -p 干净会话，只给 mobile-mcp 工具。
C 组「默认全开」：读元素、截图、批量命令都给，看模型自己怎么选。
A 组「读界面」：可读元素列表，不能截图；B 组「看截图」：只能截图 + 坐标点击。
用法：python run_claude.py <task_id|all> <A|B|C|ABC> [repeat]  → raw/claude_<task>_<arm>_<rep>.jsonl + results.jsonl"""
import json
import sys
import time
from pathlib import Path
import subprocess

import tasks as T

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RAW.mkdir(exist_ok=True)
MODEL = "claude-haiku-5-5"
CLAUDE_EXE = "C:/nvm4w/nodejs/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
MCP_CFG = HERE / "mcp_config.json"
MCP_CFG.write_text(json.dumps({"mcpServers": {"mobile": {
    "command": "ssh", "args": ["-o", "ConnectTimeout=10", "gpu-server",
                               "docker exec -i -e MOBILEMCP_DISABLE_TELEMETRY=1 -e ANDROID_HOME=/work -w /work mm-lab "
                               "node /work/mm/node_modules/@mobilenext/mobile-mcp/lib/index.js"]}}}), encoding="utf-8")

COMMON = ["mobile_list_available_devices", "mobile_list_apps", "mobile_get_foreground_app", "mobile_launch_app",
          "mobile_terminate_app", "mobile_get_screen_size", "mobile_click_on_screen_at_coordinates",
          "mobile_double_tap_on_screen", "mobile_long_press_on_screen_at_coordinates", "mobile_press_button",
          "mobile_swipe_on_screen", "mobile_type_keys", "mobile_get_orientation"]
# batch_commands 可带 listElementsAtEnd 读元素（试跑时 B 组被拒后用它绕回去），所以只放进 C 组
ARMS = {"A": COMMON + ["mobile_list_elements_on_screen"], "B": COMMON + ["mobile_take_screenshot"],
        "C": COMMON + ["mobile_list_elements_on_screen", "mobile_take_screenshot", "mobile_batch_commands"]}
ALL = ARMS["C"] + ["mobile_save_screenshot", "mobile_open_url", "mobile_set_orientation",
                   "mobile_fold_device", "mobile_set_location", "mobile_clipboard", "mobile_get_device_logs",
                   "mobile_list_crashes", "mobile_get_crash", "mobile_start_screen_recording",
                   "mobile_stop_screen_recording", "mobile_install_app", "mobile_uninstall_app",
                   "mobile_login_to_cloud_provider", "mobile_list_remote_devices", "mobile_allocate_remote_device",
                   "mobile_release_remote_device"]
SYSTEM = (f"你在操作一台安卓手机，设备 ID 是 {T.DEVICE}。只能用提供的手机工具完成用户的任务。"
          "任务完成后用一句话说明结果；如果做不到，说明卡在哪里。")
MAX_TURNS = 40


def run(task, arm, rep):
    allowed = [f"mcp__mobile__{n}" for n in ARMS[arm]]
    denied = [f"mcp__mobile__{n}" for n in ALL if n not in ARMS[arm]]
    T.reset()
    time.sleep(3)
    out = RAW / f"claude_{task['id']}_{arm}_{rep}.jsonl"
    t0 = time.time()
    cmd = [CLAUDE_EXE, "-p", task["goal"], "--model", MODEL, "--system-prompt", SYSTEM, "--tools", "",
           "--setting-sources", "", "--mcp-config", str(MCP_CFG), "--strict-mcp-config",
           "--allowedTools", ",".join(allowed), "--disallowedTools", ",".join(denied),
           "--max-turns", str(MAX_TURNS), "--output-format", "stream-json", "--verbose"]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=900, cwd=str(RAW))
        lines = p.stdout.decode("utf-8", "replace").splitlines()
    except subprocess.TimeoutExpired as e:
        lines = (e.stdout or b"").decode("utf-8", "replace").splitlines()
    dt = time.time() - t0
    out.write_text("\n".join(lines), encoding="utf-8")
    ok = T._safe(task["check"])
    msgs = [json.loads(l) for l in lines if l.startswith("{")]
    res = next((m for m in msgs if m.get("type") == "result"), {})
    calls = [c["name"].replace("mcp__mobile__", "") for m in msgs if m.get("type") == "assistant"
             for c in m["message"].get("content", []) if c.get("type") == "tool_use"]
    u = res.get("usage", {})
    row = {"model": "claude-haiku", "task": task["id"], "arm": arm, "rep": rep, "ok": ok is True,
           "seconds": round(dt, 1), "steps": len(calls), "tools": calls,
           "input_tokens": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
           "output_tokens": u.get("output_tokens", 0), "cost_usd": res.get("total_cost_usd"),
           "final": (res.get("result") or "")[:300], "stop": res.get("subtype")}
    with open(HERE / "results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in row.items() if k != "tools"}, ensure_ascii=False), flush=True)
    return row


if __name__ == "__main__":
    tid, arms = sys.argv[1], sys.argv[2]
    rep = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    for task in T.TASKS:
        if tid in ("all", task["id"]):
            for arm in arms:
                run(task, arm, rep)
