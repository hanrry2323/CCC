#!/bin/bash
# ccc-notify.sh — macOS 桌面通知 + 落告警文件（v0.8 升级链 L1/L2/L3 用）
#
# 职责：发桌面通知 + 落 ~/.ccc/alerts/<时间戳>.md 双通道
#   - L1: 仅日志（不发通知）
#   - L2: 桌面通知 + 告警文件
#   - L3: 桌面通知（sound=Basso）+ 告警文件 + 飞书置顶（v0.8 未接）
#
# 静默门（不调 osascript，仍可落告警文件）：
#   - CCC_NOTIFY=0
#   - CCC_DRY_RUN=1
#   - PYTEST_CURRENT_TEST 已设置（pytest 自动注入）
#
# 用法：
#   bash ccc-notify.sh <level> <title> <message>   # L1|L2|L3 三级告警
#   bash ccc-notify.sh <title> <message>           # Engine 简版（桌面通知）
#
# 退出码：0 = 成功 / 1 = 参数错

set -uo pipefail

_ccc_notify_muted() {
  # 测试 / dry-run：禁止弹 macOS 桌面通知（避免污染本机通知中心）
  if [[ "${CCC_NOTIFY:-1}" == "0" ]]; then
    return 0
  fi
  if [[ "${CCC_DRY_RUN:-0}" == "1" ]]; then
    return 0
  fi
  if [[ -n "${PYTEST_CURRENT_TEST:-}" ]]; then
    return 0
  fi
  return 1
}

_ccc_display_notification() {
  # $1=message $2=title [$3=subtitle-for-L3-only via TITLE already composed]
  local message="$1"
  local title="$2"
  local sound="${3:-}"
  if _ccc_notify_muted; then
    echo "[ccc-notify] muted (skip osascript): $title"
    return 0
  fi
  if [[ -n "$sound" ]]; then
    osascript \
      -e 'on run argv' \
      -e 'display notification (item 1 of argv) with title (item 2 of argv) subtitle "需要老板拍板" sound name "Basso"' \
      -e 'end run' \
      -- "$message" "$title" \
      >/dev/null 2>&1 || true
  else
    osascript \
      -e 'on run argv' \
      -e 'display notification (item 1 of argv) with title (item 2 of argv)' \
      -e 'end run' \
      -- "$message" "$title" \
      >/dev/null 2>&1 || true
  fi
}

# Engine 简版：2 参数 → 直接发桌面通知，不阻塞
if [[ $# -eq 2 ]]; then
  TITLE="$1"
  MESSAGE="$2"
  if _ccc_notify_muted; then
    echo "[ccc-notify] muted (skip osascript): $TITLE"
    exit 0
  fi
  osascript \
    -e 'on run argv' \
    -e 'display notification (item 2 of argv) with title (item 1 of argv)' \
    -e 'end run' \
    -- "$TITLE" "$MESSAGE" \
    >/dev/null 2>&1 || true
  exit 0
fi

LEVEL="${1:-}"
TITLE="${2:-}"
MESSAGE="${3:-}"

if [[ -z "$LEVEL" || -z "$TITLE" || -z "$MESSAGE" ]]; then
  echo "usage: ccc-notify.sh <L1|L2|L3> <title> <message>" >&2
  exit 1
fi

ALERT_DIR="${CCC_ALERT_DIR:-${HOME}/.ccc/alerts}"
mkdir -p "$ALERT_DIR"

# 验 level
case "$LEVEL" in
  L1|L2|L3) ;;
  *) echo "未知 level: $LEVEL（应为 L1|L2|L3）" >&2; exit 1 ;;
esac

TS=$(date +%Y%m%d-%H%M%S)
ALERT_FILE="$ALERT_DIR/${TS}-${LEVEL}.md"

# 告警文件（永久存档，agent 巡检可读）
cat > "$ALERT_FILE" <<EOF
# CCC Alert: $TITLE

- **时间**: $(date '+%Y-%m-%d %H:%M:%S')
- **级别**: $LEVEL
- **标题**: $TITLE
- **消息**: $MESSAGE
- **主机**: $(hostname)
- **用户**: $(whoami)
EOF

# 桌面通知
case "$LEVEL" in
  L1)
    echo "[ccc-notify] L1 (log only) $TITLE: $MESSAGE"
    ;;
  L2)
    _ccc_display_notification "$MESSAGE" "CCC L2: $TITLE"
    echo "[ccc-notify] L2 sent: $TITLE"
    ;;
  L3)
    _ccc_display_notification "$MESSAGE" "CCC L3: $TITLE" "Basso"
    echo "[ccc-notify] L3 sent: $TITLE"
    ;;
esac

echo "$ALERT_FILE"
exit 0
