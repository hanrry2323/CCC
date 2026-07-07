#!/bin/bash
# ccc-notify.sh — macOS 桌面通知 + 落告警文件（v0.8 升级链 L1/L2/L3 用）
#
# 职责：发桌面通知 + 落 ~/.ccc/alerts/<时间戳>.md 双通道
#   - L1: 仅日志（不发通知）
#   - L2: 桌面通知 + 告警文件
#   - L3: 桌面通知（sound=Basso）+ 告警文件 + 飞书置顶（v0.8 未接）
#
# 用法：
#   bash ccc-notify.sh <level> <title> <message>
#     level: L1 | L2 | L3
#
# 退出码：0 = 成功 / 1 = 参数错

set -uo pipefail

LEVEL="${1:?usage: ccc-notify.sh <L1|L2|L3> <title> <message>}"
TITLE="${2:?usage: ccc-notify.sh <L1|L2|L3> <title> <message>}"
MESSAGE="${3:?usage: ccc-notify.sh <L1|L2|L3> <title> <message>}"

ALERT_DIR="${HOME}/.ccc/alerts"
mkdir -p "$ALERT_DIR"

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
    # L1: 不发通知，只日志
    echo "[ccc-notify] L1 (log only) $TITLE: $MESSAGE"
    ;;
  L2)
    # L2: 通知 + 默认声音
    osascript -e "display notification \"$MESSAGE\" with title \"CCC L2: $TITLE\"" >/dev/null 2>&1
    echo "[ccc-notify] L2 sent: $TITLE"
    ;;
  L3)
    # L3: 通知 + 强烈声音 + subtitle 强调
    osascript -e "display notification \"$MESSAGE\" with title \"CCC L3: $TITLE\" subtitle \"需要老板拍板\" sound name \"Basso\"" >/dev/null 2>&1
    echo "[ccc-notify] L3 sent: $TITLE"
    ;;
  *)
    echo "未知 level: $LEVEL（应为 L1/L2/L3）" >&2
    exit 1
    ;;
esac

echo "$ALERT_FILE"
exit 0
