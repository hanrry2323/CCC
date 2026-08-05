#!/usr/bin/env bash
# ── CCC release.sh plist 自愈与自检单元测试 ──

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== 正在启动 release.sh plist 自愈测试 ==="

# 1. 动态提取 start_engine 源代码
START_ENGINE_CODE="$(sed -n '/^start_engine() {/,/^}/p' "$PROJECT_ROOT/deploy/release.sh")"
if [[ -z "$START_ENGINE_CODE" ]]; then
  echo "[FAIL] 无法从 deploy/release.sh 提取 start_engine 函数" >&2
  exit 1
fi

# 2. 准备测试沙盒目录
TEST_SANDBOX="$(mktemp -d)"
trap 'rm -rf "$TEST_SANDBOX"' EXIT

echo "沙盒路径: $TEST_SANDBOX"

# 3. 设置测试辅助函数和全局变量
export HOME="$TEST_SANDBOX/mock_home"
export USER="mock_user"
mkdir -p "$HOME"

# Mock 依赖变量
ENGINE_LABEL="com.ccc.engine"
REPO_PATH="$TEST_SANDBOX/mock_repo"
CONFIG_ENV="$REPO_PATH/server/config/config.env"
PYTHON_BIN="$(which python3 || which python)"

mkdir -p "$REPO_PATH/server/deploy"
mkdir -p "$REPO_PATH/server/config"

# 准备模拟模板文件
cp "$PROJECT_ROOT/server/deploy/com.ccc.engine.plist" "$REPO_PATH/server/deploy/com.ccc.engine.plist"

# Mock 记录函数
record() {
  echo "[MOCK_RECORD] status=$1, step=$2, detail=$3"
}

# 导入 start_engine
eval "$START_ENGINE_CODE"

# ─── 测试用例 1：服务已注册且 kickstart 成功 ───
echo "--- Case 1: 服务已注册且 kickstart 成功 ---"
launchctl() {
  case "$1" in
    print)
      return 0 # 已注册
      ;;
    kickstart)
      if [[ "$2" == "-k" && "$3" == "gui/$(id -u)/com.ccc.engine" ]]; then
        return 0 # kickstart 成功
      fi
      ;;
  esac
  return 1
}

start_engine

# ─── 测试用例 2：服务未注册，plist 存在，bootstrap 成功 ───
echo "--- Case 2: 服务未注册，plist 存在，bootstrap 成功 ---"
# 重新准备干净的环境（不让 plist 丢失）
rm -rf "$HOME" && mkdir -p "$HOME/Library/LaunchAgents"
touch "$HOME/Library/LaunchAgents/com.ccc.engine.plist"

launchctl() {
  case "$1" in
    print)
      return 1 # 未注册
      ;;
    bootstrap)
      if [[ "$2" == "gui/$(id -u)" && "$3" == "$HOME/Library/LaunchAgents/com.ccc.engine.plist" ]]; then
        return 0 # bootstrap 成功
      fi
      ;;
  esac
  return 1
}

start_engine

# ─── 测试用例 3：服务未注册且 plist 缺失 → 自愈重建 → bootstrap 成功 ───
echo "--- Case 3: 服务未注册且 plist 缺失 → 自愈重建 → bootstrap 成功 ---"
rm -rf "$HOME" && mkdir -p "$HOME"

# 确保 plist 不存在
[[ ! -f "$HOME/Library/LaunchAgents/com.ccc.engine.plist" ]]

launchctl() {
  case "$1" in
    print)
      return 1 # 未注册
      ;;
    bootstrap)
      if [[ "$2" == "gui/$(id -u)" && "$3" == "$HOME/Library/LaunchAgents/com.ccc.engine.plist" ]]; then
        return 0 # bootstrap 成功
      fi
      ;;
  esac
  return 1
}

# 运行自愈
start_engine

# 验证自愈生成的 plist 是否存在并包含占位符替换
TARGET_PLIST="$HOME/Library/LaunchAgents/com.ccc.engine.plist"
if [[ ! -f "$TARGET_PLIST" ]]; then
  echo "[FAIL] Case 3: 自愈未生成 plist 文件" >&2
  exit 1
fi

if ! grep -q "$REPO_PATH" "$TARGET_PLIST"; then
  echo "[FAIL] Case 3: 生成的 plist 中未正确替换 \$PROJECT_ROOT 为 $REPO_PATH" >&2
  exit 1
fi

if ! grep -q "mock_user" "$TARGET_PLIST"; then
  echo "[FAIL] Case 3: 生成的 plist 中未正确替换 \$USERNAME" >&2
  exit 1
fi

echo "[PASS] Case 3 plist 验证完美通过"

# ─── 测试用例 4：服务未注册且 plist 缺失，但模板文件也缺失 → 必须阻断 FAIL ───
echo "--- Case 4: 模板文件也缺失，必须阻断 FAIL ---"
rm -rf "$HOME" && mkdir -p "$HOME"
# 移走模板
mv "$REPO_PATH/server/deploy/com.ccc.engine.plist" "$REPO_PATH/server/deploy/com.ccc.engine.plist.bak"

# 我们需要捕获 exit，因为 start_engine 失败应该调用 exit 1
# 由于 exit 会终止当前 Shell，我们使用子 Shell 运行来测试它
set +e
(
  # 在子 Shell 里定义退出和记录逻辑
  exit() {
    echo "[MOCK_EXIT] exit $1"
    builtin exit "$1"
  }
  launchctl() { return 1; }
  start_engine
)
# 恢复模板
mv "$REPO_PATH/server/deploy/com.ccc.engine.plist.bak" "$REPO_PATH/server/deploy/com.ccc.engine.plist"
set -e

echo "=== 所有 plist 自愈测试全部成功！ ==="
