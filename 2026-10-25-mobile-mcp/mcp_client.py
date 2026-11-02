"""最小 MCP 客户端：经 ssh → docker exec 用 stdio 连接服务器容器里的 mobile-mcp。
密钥只在本机；容器里只有 mobile-mcp 和 adb，设备是本机模拟器（隧道接入）。"""
import json
import subprocess
import threading
import queue

DEVICE = "172.17.0.1:15555"
CMD = ["ssh", "-o", "ConnectTimeout=10", "gpu-server",
       "docker exec -i -e MOBILEMCP_DISABLE_TELEMETRY=1 -e ANDROID_HOME=/work -w /work mm-lab "
       "node /work/mm/node_modules/@mobilenext/mobile-mcp/lib/index.js"]


class MCP:
    def __init__(self):
        self.p = subprocess.Popen(CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.q = queue.Queue()
        self.n = 0
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._err, daemon=True).start()
        self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "ai-daily-test", "version": "0.1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _read(self):
        for line in self.p.stdout:
            line = line.strip()
            if line.startswith(b"{"):
                self.q.put(json.loads(line))

    def _err(self):
        for line in self.p.stderr:
            s = line.decode("utf-8", "replace").strip()
            if s and "post-quantum" not in s and "store now" not in s and "upgraded" not in s:
                print("[mcp]", s[:200])

    def _send(self, msg):
        self.p.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        self.p.stdin.flush()

    def call(self, method, params=None, timeout=120):
        self.n += 1
        rid = self.n
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        while True:
            m = self.q.get(timeout=timeout)
            if m.get("id") == rid:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m["result"]

    def tools(self):
        return self.call("tools/list")["tools"]

    def tool(self, name, args=None, timeout=120):
        return self.call("tools/call", {"name": name, "arguments": args or {}}, timeout=timeout)

    def close(self):
        try:
            self.p.stdin.close()
            self.p.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    m = MCP()
    ts = m.tools()
    print(len(ts), "tools:", ", ".join(t["name"] for t in ts))
    print(json.dumps(m.tool("mobile_list_available_devices"), ensure_ascii=False)[:500])
    r = m.tool("mobile_list_elements_on_screen", {"device": DEVICE})
    txt = "".join(c.get("text", "") for c in r["content"] if c["type"] == "text")
    print(len(txt), "chars;", txt[:1500])
    m.close()
