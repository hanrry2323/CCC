#!/bin/bash
# ccc-hook.sh — 通用钩子入口（v0.8 新增）
#
# 职责：提供 4 个标准钩子点，ccc-exec-launcher.sh / ccc-finish.sh 调用。
#       每个钩子点执行 ~/.ccc/hooks/<hook-name>.sh（用户自定义）。
#       用户脚本 exit 0 = 通过，非 0 = 阻断。
#
# 钩子点：
#   pre-exec   — phase 启动前（如残留扫描、参数校验）
#   post-exec  — phase 完成后（如自动 commit、状态写回）
#   pre-commit — commit 前（如 lint、secret 扫描）
#   on-error   — phase 失败时（如告警、清理）
#
# 用法：
#   bash ccc-hook.sh <hook-point> [args...]
#     exit 0 = 通过 / 非 0 = 阻断
#
# 红线：钩子必须轻量（< 30s），禁止在钩子里跑耗时的 phase。

set -uo pipefail

HOOK_POINT="${1:?usage: ccc-hook.sh <hook-point> [args...]}"
shift

HOOK_DIR="${HOME}/.ccc/hooks"
USER_HOOK="$HOOK_DIR/${HOOK_POINT}.sh"

if [[ ! -f "$USER_HOOK" ]]; then
  # 用户没定义 = 默认通过
  echo "[ccc-hook] $HOOK_POINT: no user hook ($USER_HOOK), pass"
  exit 0
fi

if [[ ! -x "$USER_HOOK" ]]; then
  echo "[ccc-hook] 警告: $USER_HOOK 不可执行，尝试 chmod +x" >&2
  chmod +x "$USER_HOOK" || { echo "[ccc-hook] chmod 失败，跳过" >&2; exit 0; }
fi

echo "[ccc-hook] running $HOOK_POINT: $USER_HOOK $*"
START=$(date +%s)

# 钩子超时：默认 30s（红线：钩子必须轻量），可被 CCC_HOOK_TIMEOUT 覆盖
HOOK_TIMEOUT="${CCC_HOOK_TIMEOUT:-30}"
TIMEOUT_CMD=""
if command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_CMD="gtimeout"
elif command -v timeout >/dev/null 2>&1; then
  TIMEOUT_CMD="timeout"
elif command -v perl >/dev/null 2>&1; then
  # macOS 没 coreutils timeout, 用 perl 兜底
  TIMEOUT_CMD="perl"
fi

if [[ "$TIMEOUT_CMD" == "gtimeout" || "$TIMEOUT_CMD" == "timeout" ]]; then
  "$TIMEOUT_CMD" "$HOOK_TIMEOUT" bash "$USER_HOOK" "$@"
  RC=$?
elif [[ "$TIMEOUT_CMD" == "perl" ]]; then
  # perl alarm 实现 timeout: 父进程 alarm N 秒后给子进程组发 SIGTERM
  # 用 'bash' 把 USER_HOOK 后的所有 args 当 bash 命令执行
  perl -e '
    $SIG{ALRM} = sub { kill TERM => -$$; };
    alarm shift @ARGV;
    exec @ARGV;
  ' "$HOOK_TIMEOUT" bash "$USER_HOOK" "$@"
  RC=$?
else
  bash "$USER_HOOK" "$@"
  RC=$?
fi

DUR=$(( $(date +%s) - START ))
echo "[ccc-hook] $HOOK_POINT exit=$RC duration=${DUR}s"

if [[ $RC -ne 0 ]]; then
  echo "[ccc-hook] ❌ 钩子 $HOOK_POINT 失败 (exit=$RC)，阻断"
  exit $RC
fi
exit 0
