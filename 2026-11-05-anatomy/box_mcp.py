"""最小 MCP 服务器（stdio）：把 AI 的所有操作转到服务器容器里执行，本机不跑任何生成或第三方代码。
用法：python box_mcp.py <容器名> <容器内工作目录>
工具：bash / write_file / read_file / view_image
"""
import base64
import json
import shlex
import subprocess
import sys

SSH = "gpu-server"
CONTAINER, WORKDIR = sys.argv[1], sys.argv[2]
MAX_OUT = 30000
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")


def dexec(cmd, stdin=None, timeout=600):
    full = ["ssh", "-o", "ServerAliveInterval=30", "-o", "LogLevel=ERROR", SSH,
            f"docker exec -i -w {shlex.quote(WORKDIR)} {CONTAINER} bash -lc {shlex.quote(cmd)}"]
    p = subprocess.run(full, input=stdin, capture_output=True, timeout=timeout + 30)
    return p.returncode, p.stdout, p.stderr


def text(s):
    return {"content": [{"type": "text", "text": s}]}


def t_bash(a):
    t = max(5, min(int(a.get("timeout_sec", 300)), 900))
    try:
        rc, out, err = dexec(f"timeout {t} bash -c {shlex.quote(a['command'])}", timeout=t)
    except subprocess.TimeoutExpired:
        return text("ERROR: command timed out")
    s = (out + err).decode("utf-8", "replace")
    s = s if len(s) <= MAX_OUT else s[:MAX_OUT // 2] + "\n...[truncated]...\n" + s[-MAX_OUT // 2:]
    return text(f"{s}\n[exit {rc}]")


def t_write(a):
    p = a["path"]
    rc, out, err = dexec(f"mkdir -p \"$(dirname {shlex.quote(p)})\" && cat > {shlex.quote(p)}",
                         stdin=a["content"].encode("utf-8"))
    return text(f"wrote {p}" if rc == 0 else f"ERROR: {err.decode('utf-8','replace')}")


def t_read(a):
    p, off, lim = a["path"], int(a.get("offset", 1)), int(a.get("limit", 2000))
    rc, out, err = dexec(f"sed -n '{off},{off + lim - 1}p' {shlex.quote(p)} | cat -n | sed 's/^ *\\([0-9]*\\)/\\1/' ; true")
    if rc != 0 or not out:
        return text(f"ERROR or empty: {err.decode('utf-8','replace')}")
    s = out.decode("utf-8", "replace")
    if off > 1:  # 行号从 offset 开始
        s = "\n".join(f"{int(l.split(chr(9),1)[0]) + off - 1}\t{l.split(chr(9),1)[1]}" if "\t" in l else l
                      for l in s.splitlines())
    return text(s[:120000])


def t_image(a):
    p = a["path"]
    rc, out, err = dexec(f"base64 -w0 {shlex.quote(p)}")
    if rc != 0:
        return text(f"ERROR: {err.decode('utf-8','replace')}")
    raw = base64.b64decode(out)
    if len(raw) > 4_500_000:
        return text("ERROR: image larger than 4.5MB, capture a smaller crop")
    mime = "image/jpeg" if p.lower().endswith((".jpg", ".jpeg")) else "image/webp" if p.lower().endswith(".webp") else "image/png"
    return {"content": [{"type": "image", "data": out.decode(), "mimeType": mime}]}


TOOLS = {
    "bash": (t_bash, "Run a bash command in the Linux workspace (Node 22, Chromium at /usr/bin/chromium, no GUI). "
             "Working directory is the task folder. Returns stdout+stderr and exit code.",
             {"command": {"type": "string"}, "timeout_sec": {"type": "integer", "description": "default 300, max 900"}},
             ["command"]),
    "write_file": (t_write, "Create or overwrite a text file in the workspace.",
                   {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    "read_file": (t_read, "Read a text file with line numbers.",
                  {"path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, ["path"]),
    "view_image": (t_image, "Look at a PNG/JPEG/WebP image file from the workspace (e.g. a screenshot you captured).",
                   {"path": {"type": "string"}}, ["path"]),
}


def reply(i, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": i}
    msg["result" if error is None else "error"] = result if error is None else {"code": -32000, "message": error}
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    if not line.strip():
        continue
    m = json.loads(line)
    meth, i = m.get("method"), m.get("id")
    if meth == "initialize":
        reply(i, {"protocolVersion": m["params"].get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}}, "serverInfo": {"name": "box", "version": "1"}})
    elif meth == "tools/list":
        reply(i, {"tools": [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": pr, "required": rq}}
                            for n, (_, d, pr, rq) in TOOLS.items()]})
    elif meth == "tools/call":
        n = m["params"]["name"]
        try:
            reply(i, TOOLS[n][0](m["params"].get("arguments", {})))
        except Exception as e:  # noqa
            reply(i, {"content": [{"type": "text", "text": f"ERROR: {e}"}], "isError": True})
    elif i is not None:
        reply(i, {})
