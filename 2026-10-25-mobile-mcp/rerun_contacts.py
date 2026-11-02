"""2026-10-25 联系人判定改严后重跑：两个联系人任务 × 两个模型 × 三组 × 两轮 = 24 次。
旧行从 results.jsonl 移到 results_before_contactfix.jsonl（备份），新行追加；每次跑完存一份通讯录原文到 raw/contacts_*.txt。
用法：python rerun_contacts.py [claude|ds|all]"""
import json
import sys
from pathlib import Path

import tasks as T
import run_claude as RC
import run_deepseek as RD
from mcp_client import MCP

HERE = Path(__file__).resolve().parent
IDS = ("contact_en", "contact_zh")


def drop_old(model):
    p = HERE / "results.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    keep = [r for r in rows if not (r["model"] == model and r["task"] in IDS)]
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")


def dump(tag):
    (HERE / "raw" / f"contacts_{tag}.txt").write_text(T.contacts(), encoding="utf-8")


which = sys.argv[1] if len(sys.argv) > 1 else "all"
tasks = [t for t in T.TASKS if t["id"] in IDS]
if which in ("claude", "all"):
    drop_old("claude-haiku")
    for rep in (0, 1):
        for t in tasks:
            for arm in "ABC":
                RC.run(t, arm, rep)
                dump(f"claude_{t['id']}_{arm}_{rep}")
if which in ("ds", "all"):
    drop_old("deepseek-flash")
    mcp = MCP()
    schemas = mcp.tools()
    try:
        for rep in (0, 1):
            for t in tasks:
                for arm in "ABC":
                    RD.run(mcp, schemas, t, arm, rep)
                    dump(f"ds_{t['id']}_{arm}_{rep}")
    finally:
        mcp.close()
