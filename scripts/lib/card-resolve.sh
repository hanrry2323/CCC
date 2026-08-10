#!/usr/bin/env bash
# resolve_card：按卡号唯一解析卡文件（V7：多命中禁止 head -1 猜，直接报错）。
# 独立文件供 approve-merge.sh 与测试共享，防止实现漂移。

resolve_card() {
  local id="$1"
  local hits
  hits="$(find docs/dispatch -type f -name "${id}-*.md" 2>/dev/null || true)"
  if [[ -z "$hits" ]]; then
    echo "[ERROR] 找不到卡：${id}" >&2
    return 1
  fi
  local count
  count="$(printf '%s\n' "$hits" | grep -c . )"
  if [[ "$count" -gt 1 ]]; then
    echo "[ERROR] 卡号二义性：${id} 命中 ${count} 个卡文件（head -1 有歧义，禁止猜）:" >&2
    printf '%s\n' "$hits" | sed 's/^/  /' >&2
    return 1
  fi
  echo "$hits"
}
