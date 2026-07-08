#!/bin/bash
# uninstall-ccc-roles.sh — 卸载旧角色 plist (v0.20.1)
#
# 卸载全部旧版 7 角色 launchd plist，替换为单一 engine plist。
# 保留 com.ccc.board (HTTP 看板) 和 com.ccc.flywheel-scan。
#
# 用法:
#   ./uninstall-ccc-roles.sh              # 卸载 CCC 旧角色
#   ./uninstall-ccc-roles.sh --all        # 卸载全部项目旧角色

set -uo pipefail

PLIST_DIR="${HOME}/Library/LaunchAgents"

# ── 旧角色标签列表（不包括 board / flywheel-scan）──
OLD_ROLES=("dev" "reviewer" "tester" "kb" "product" "ops" "regress")
PREFIXES=("com.ccc." "com.ccc.qx-observer.")

UNLOADED=()
REMOVED=()
SKIPPED=()

echo "=== 卸载旧角色 plist ==="

ALL_MODE=false
[[ "${1:-}" == "--all" ]] && ALL_MODE=true

for prefix in "${PREFIXES[@]}"; do
  # --all 模式下扫全部前缀；否则只扫 com.ccc.（CCC 自身）
  if ! $ALL_MODE && [[ "$prefix" != "com.ccc." ]]; then
    continue
  fi

  for role in "${OLD_ROLES[@]}"; do
    label="${prefix}${role}"
    plist="${PLIST_DIR}/${label}.plist"

    if [ ! -f "$plist" ]; then
      SKIPPED+=("$label (not found)")
      continue
    fi

    echo -n "  ${label} ... "

    # unload
    if launchctl unload "$plist" 2>/dev/null; then
      UNLOADED+=("$label")
      echo -n "unloaded "
    else
      echo -n "unload_fail "
    fi

    # remove plist file
    if rm -f "$plist"; then
      REMOVED+=("$label")
      echo "removed"
    else
      echo "remove_fail"
    fi
  done
done

echo ""
echo "=== 统计 ==="
echo "  已卸载: ${#UNLOADED[@]}"
echo "  已删除: ${#REMOVED[@]}"
echo "  跳过: ${#SKIPPED[@]}"
for s in "${SKIPPED[@]}"; do
  echo "    - $s"
done

echo ""
echo "=== 残留检查 ==="
REMAINING=$(launchctl list | grep -E 'com\.ccc\.(dev|reviewer|tester|kb|product|ops|regress)\b' || true)
if [ -n "$REMAINING" ]; then
  echo "  ⚠ 仍有残留:"
  echo "$REMAINING"
else
  echo "  无残留 ✓"
fi

echo ""
echo "Done. 可用 ./install-ccc-roles.sh 安装新版 engine."
