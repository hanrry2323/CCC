#!/usr/bin/env bash
# 模拟 Hub 首次空 body、第二次正常 transfer — 验证同 CRID 重试契约（对齐 Desktop APIClient）。
# 用法：
#   CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-hub-empty-transfer-retry.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

UPSTREAM="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
PROXY_PORT="${CCC_EMPTY_RETRY_PORT:-18777}"
CRID="empty-retry-$(date +%s)-$$"
STATE="/tmp/ccc-empty-retry-state-$$"
rm -f "$STATE"

python3 - "$UPSTREAM" "$PROXY_PORT" "$USER" "$PASS" "$STATE" <<'PY' &
import base64, json, sys, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

upstream, port, user, passwd, state_path = sys.argv[1:6]
auth = "Basic " + base64.b64encode(f"{user}:{passwd}".encode()).decode()
count = {"n": 0}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        count["n"] += 1
        with open(state_path, "w") as f:
            f.write(str(count["n"]))
        if count["n"] == 1 and self.path.rstrip("/").endswith("/transfer"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"")
            return
        req = urllib.request.Request(
            upstream.rstrip("/") + self.path,
            data=body,
            headers={
                "Authorization": auth,
                "Content-Type": self.headers.get("Content-Type") or "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type") or "application/json")
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_GET(self):
        req = urllib.request.Request(
            upstream.rstrip("/") + self.path,
            headers={"Authorization": auth},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.headers.get("Content-Type") or "application/json")
            self.end_headers()
            self.wfile.write(data)

HTTPServer(("127.0.0.1", int(port)), H).serve_forever()
PY
PROXY_PID=$!
cleanup() { kill "$PROXY_PID" 2>/dev/null || true; rm -f "$STATE"; }
trap cleanup EXIT
sleep 0.4

echo "== empty-transfer-retry via proxy :${PROXY_PORT} → ${UPSTREAM} =="

# Probe upstream
curl -sf --connect-timeout 5 -u "${USER}:${PASS}" "${UPSTREAM}/api/desktop/projects" >/dev/null

BODY=$(python3 - <<PY
import json
print(json.dumps({
  "project_id": "${PROJECT}",
  "thread_id": "${PROJECT}::empty-retry",
  "client_request_id": "${CRID}",
  "title": "Empty transfer retry smoke",
  "goal": "首响空 body 后同 CRID 重试成功",
  "acceptance": ["第二次 transfer 返回 epic_id"],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "python",
  "complexity": "small",
  "plan_md": "# Plan\\n\\n## 目标\\nretry\\n\\n## 验收\\n- epic_id\\n",
}))
PY
)

# Attempt 1: empty body (proxy)
code1=$(curl -s -o /tmp/ccc-empty-r1.bin -w "%{http_code}" -u "${USER}:${PASS}" \
  -H 'Content-Type: application/json' -d "${BODY}" \
  "http://127.0.0.1:${PROXY_PORT}/api/desktop/transfer")
test "$code1" = "200"
test ! -s /tmp/ccc-empty-r1.bin
echo "attempt1 empty body ok"

# Attempt 2: same CRID → real Hub via proxy
curl -sf -u "${USER}:${PASS}" -H 'Content-Type: application/json' -d "${BODY}" \
  "http://127.0.0.1:${PROXY_PORT}/api/desktop/transfer" | tee /tmp/ccc-empty-r2.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
print("attempt2 epic", d["epic_id"], "idempotent", d.get("idempotent_replay"))
'

# Attempt 3: idempotent replay
curl -sf -u "${USER}:${PASS}" -H 'Content-Type: application/json' -d "${BODY}" \
  "http://127.0.0.1:${PROXY_PORT}/api/desktop/transfer" | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id")
assert d.get("idempotent_replay") is True, d
print("attempt3 idempotent ok")
'

echo "== smoke-hub-empty-transfer-retry PASS =="
