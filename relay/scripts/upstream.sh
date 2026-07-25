#!/usr/bin/env bash
# AI Loop Router — upstreams.json 管理助手
# 直接编辑 JSON 文件，proxy 通过 fs.watchFile 自动热重载
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPSTREAMS_FILE="${LOOP_UPSTREAMS_FILE:-$ROOT/upstreams.json}"
ADMIN_URL="${LOOP_ADMIN_URL:-http://127.0.0.1:4000}"

usage() {
  cat <<'EOF'
用法:
  bash scripts/upstream.sh list
  bash scripts/upstream.sh add <name> <base_url> <api_key> [--models flash] [--priority 99]
  bash scripts/upstream.sh toggle <name> [on|off]
  bash scripts/upstream.sh remove <name>
  bash scripts/upstream.sh test <name>

环境变量:
  LOOP_UPSTREAMS_FILE  上游配置文件路径 (默认: upstreams.json)
  LOOP_ADMIN_URL       Admin API 地址 (默认: http://127.0.0.1:4000)
EOF
}

py() {
  python3 - "$@" <<'PY'
import json, sys, os

path = os.environ.get("UPSTREAMS_FILE")
cmd = sys.argv[1]

def load():
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit("upstreams file must be a JSON array")
    return data

def save(data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

if cmd == "add":
    name, base_url, api_key = sys.argv[2], sys.argv[3], sys.argv[4]
    models = ["flash"]
    priority = 99
    i = 5
    while i < len(sys.argv):
        if sys.argv[i] == "--models":
            models = [sys.argv[i + 1]]
            i += 2
        elif sys.argv[i] == "--priority":
            priority = int(sys.argv[i + 1])
            i += 2
        else:
            raise SystemExit(f"unknown option: {sys.argv[i]}")
    data = load()
    if any(u.get("name") == name for u in data):
        raise SystemExit(f"upstream already exists: {name}")
    entry = {
        "name": name,
        "base_url": base_url,
        "api_key": api_key,
        "tier": models[0],
        "tier_priority": priority,
        "models": models,
        "upstream_model": models[0],
    }
    data.append(entry)
    save(data)
    print(f"added: {name}")

elif cmd == "toggle":
    name = sys.argv[2]
    state = sys.argv[3] if len(sys.argv) > 3 else None
    data = load()
    found = False
    for u in data:
        if u.get("name") == name:
            found = True
            if state == "on":
                u.pop("enabled", None)
            elif state == "off":
                u["enabled"] = False
            else:
                u["enabled"] = not (u.get("enabled") is False)
            enabled = u.get("enabled") is not False
            save(data)
            print(f"toggled: {name} → {'on' if enabled else 'off'}")
            break
    if not found:
        raise SystemExit(f"not found: {name}")

elif cmd == "remove":
    name = sys.argv[2]
    data = load()
    new = [u for u in data if u.get("name") != name]
    if len(new) == len(data):
        raise SystemExit(f"not found: {name}")
    save(new)
    print(f"removed: {name}")

else:
    raise SystemExit(f"unknown py cmd: {cmd}")
PY
}

cmd="${1:-}"
shift || true

case "${cmd}" in
  list)
    if command -v curl >/dev/null 2>&1; then
      curl -sf "${ADMIN_URL}/admin/upstreams" | python3 -m json.tool 2>/dev/null || curl -sf "${ADMIN_URL}/admin/upstreams"
    else
      python3 -m json.tool "${UPSTREAMS_FILE}"
    fi
    ;;
  add)
    [[ $# -ge 3 ]] || { usage; exit 1; }
    UPSTREAMS_FILE="${UPSTREAMS_FILE}" py add "$@"
    ;;
  toggle)
    [[ $# -ge 1 ]] || { usage; exit 1; }
    UPSTREAMS_FILE="${UPSTREAMS_FILE}" py toggle "$@"
    ;;
  remove)
    [[ $# -ge 1 ]] || { usage; exit 1; }
    UPSTREAMS_FILE="${UPSTREAMS_FILE}" py remove "$@"
    ;;
  test)
    [[ $# -ge 1 ]] || { usage; exit 1; }
    name="$1"
    curl -sf -X POST "${ADMIN_URL}/admin/upstreams/test" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"${name}\"}" | python3 -m json.tool 2>/dev/null || \
    curl -sf -X POST "${ADMIN_URL}/admin/upstreams/test" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"${name}\"}"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "未知命令: ${cmd}" >&2
    usage
    exit 1
    ;;
esac
