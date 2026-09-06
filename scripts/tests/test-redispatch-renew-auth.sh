#!/usr/bin/env bash
# P4.2 测试：redispatch-card.sh token 自动换发（401→/session→重试）路径 + 静态契约。
# 用本地 mock HTTP 服务器模拟看板；不访问真实服务。
# 场景：
#   A. 静态：默认 LAN 地址 + --renew-auth 旗标存在 + 脚本语法合法
#   B. 无 token 启动：/session 自动登录 → transition 成功（不依赖手工注入 token）
#   C. --renew-auth 强制登录后 transition 成功
#   D. token 不落盘 / 不进日志 / 不进 stdout
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${SCRIPT_DIR}/../redispatch-card.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/ccc-redispatch-renew.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"
FAIL=0

# ── 静态契约 ──
bash -n "$SCRIPT" || { echo "FAIL: bash -n" >&2; FAIL=1; }
grep -Fq 'BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"' "$SCRIPT" \
  || { echo "FAIL: 默认地址契约丢失" >&2; FAIL=1; }
grep -Fq -- '--renew-auth' "$SCRIPT" || { echo "FAIL: 缺少 --renew-auth" >&2; FAIL=1; }

# ── mock HTTP 服务器（仿真实 /session + /tasks/{id} + /tasks/{id}/transition 门禁语义）──
# 仿 server.py：GET /tasks/{id} 需 token（_gate_read）；transition 需 token（_check_auth）。
# 任意有效 token（以 "mock-token-" 前缀）即通过；无 token → 401。
MOCK_PORT="$(( 20000 + (RANDOM % 20000) ))"
cat > "$TMP/mock_server.py" <<'PY'
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
PORT = int(sys.argv[1])
STATE = {"session_count": 0, "trans_count": 0, "token": None}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n else b""
    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def _bearer(self):
        auth = self.headers.get("Authorization", "")
        return auth[7:] if auth.startswith("Bearer ") else ""
    def _valid(self, tok):
        return bool(tok) and tok.startswith("mock-token-")
    def do_GET(self):
        if self.path == "/health":
            self._json({"ok": True}); return
        if self.path.startswith("/tasks/"):
            if not self._valid(self._bearer()):
                self._json({"error": "this endpoint requires a token"}, 401); return
            self._json({"id": self.path.rsplit("/",1)[-1], "state": "执行中", "awaiting_human": False}); return
        self._json({"error": "not found"}, 404)
    def do_POST(self):
        if self.path == "/session":
            STATE["session_count"] += 1
            body = json.loads(self._body() or b"{}")
            if body.get("username") == "ccc" and body.get("password") == "right-pass":
                STATE["token"] = "mock-token-%d" % STATE["session_count"]
                self._json({"token": STATE["token"], "expires_at": "2099-01-01", "ttl_s": 3600})
            else:
                self._json({"error": "invalid username or password"}, 401)
            return
        if self.path.endswith("/transition"):
            STATE["trans_count"] += 1
            if not self._valid(self._bearer()):
                self._json({"error": "write endpoints require Bearer token"}, 401); return
            body = json.loads(self._body() or b"{}")
            if body.get("status") == "待分派":
                self._json({"ok": True, "status": "待分派", "state": "pending"}); return
            self._json({"error": "transition 仅支持 待分派/作废"}, 400); return
        self._json({"error": "not found"}, 404)
    do_PUT = do_POST

HTTPServer(("127.0.0.1", PORT), H).serve_forever()
PY

"$PYTHON_BIN" "$TMP/mock_server.py" "$MOCK_PORT" > "$TMP/mock.out" 2>&1 &
MOCK_PID=$!
trap 'kill $MOCK_PID 2>/dev/null; rm -rf "$TMP"' EXIT
for _ in $(seq 1 40); do
  curl -sf "http://127.0.0.1:${MOCK_PORT}/health" >/dev/null 2>&1 && break
  sleep 0.1
done

# ── 准备 web-auth.txt（现网格式，口令正确）──
cat > "$TMP/web-auth.txt" <<'EOF'
CCC Web 新口令
账号: ccc
口令: right-pass
EOF

export CCC_BOARD_URL="http://127.0.0.1:${MOCK_PORT}"
export CCC_WEB_AUTH_FILE="$TMP/web-auth.txt"
unset CCC_BOARD_TOKEN

# ── 场景 B：无 token 启动 → 自动登录 → transition 成功 ──
OUT_B="$(HOME="$TMP" bash "$SCRIPT" cccB001 2>&1)"
RC_B=$?
if [[ $RC_B -ne 0 ]]; then echo "FAIL B: rc=$RC_B out=$OUT_B" >&2; FAIL=1; fi
if ! grep -q '\[OK\] cccB001' <<< "$OUT_B"; then echo "FAIL B: 无 [OK] cccB001 -> $OUT_B" >&2; FAIL=1; fi

# ── 场景 C：--renew-auth 强制登录（仍须成功）──
OUT_C="$(HOME="$TMP" bash "$SCRIPT" --renew-auth cccC001 2>&1)"
RC_C=$?
if [[ $RC_C -ne 0 ]]; then echo "FAIL C: rc=$RC_C out=$OUT_C" >&2; FAIL=1; fi
if ! grep -q '\[OK\] cccC001' <<< "$OUT_C"; then echo "FAIL C: 无 [OK] cccC001 -> $OUT_C" >&2; FAIL=1; fi

# ── 场景 D：token 不落盘 / 不进日志 / 不进 stdout ──
LEAK_FILE="$(grep -rl 'mock-token-\|right-pass' "$TMP" 2>/dev/null \
  | grep -vE 'mock_server.py|mock\.out|web-auth\.txt' || true)"
if [[ -n "$LEAK_FILE" ]]; then
  echo "FAIL D: token/口令泄漏到非白名单文件: $LEAK_FILE" >&2
  FAIL=1
fi
if grep -q 'mock-token-' <<< "$OUT_B$OUT_C" 2>/dev/null; then echo "FAIL D: token 出现在 stdout" >&2; FAIL=1; fi
if grep -q 'right-pass' <<< "$OUT_B$OUT_C" 2>/dev/null; then echo "FAIL D: 口令出现在 stdout" >&2; FAIL=1; fi

# ── 场景 E：凭据错误 → 登录失败 → 干净失败（exit 1，无半成功假象）──
cat > "$TMP/web-auth-bad.txt" <<'EOF'
账号: ccc
口令: wrong-pass
EOF
OUT_E="$(HOME="$TMP" bash "$SCRIPT" --renew-auth --dispatch-dir /nonexistent cccE001 2>&1 | sed 's/CCC_WEB_AUTH_FILE/CCC_WEB_AUTH_FILE/' )"
# 用显式恩错误凭据文件重跑（无法经 env 注入到 --renew-auth 场景已覆盖 B/C；此处只检查错误路径）
cat > "$TMP/web-auth-bad2.txt" <<'EOF'
账号: ccc
口令: wrong-pass2
EOF
OUT_E2="$(CCC_WEB_AUTH_FILE="$TMP/web-auth-bad2.txt" HOME="$TMP" bash "$SCRIPT" --renew-auth cccE001 2>&1)"
RC_E=$?
if [[ $RC_E -eq 0 ]]; then echo "FAIL E: 错误凭据未失败（rc=0）out=$OUT_E2" >&2; FAIL=1; fi
if ! grep -q '登录失败\|未含 token\|换发' <<< "$OUT_E2"; then echo "FAIL E: 无清晰失败提示 -> $OUT_E2" >&2; FAIL=1; fi
if grep -q '\[OK\] cccE001' <<< "$OUT_E2"; then echo "FAIL E: 错误凭据却输出 [OK]" >&2; FAIL=1; fi

if [[ "$FAIL" -eq 0 ]]; then
  echo "PASS: redispatch 401→自动换发→重试 + --renew-auth + token 不落盘 全部通过"
  exit 0
else
  echo "FAIL: 存在失败场景" >&2
  exit 1
fi