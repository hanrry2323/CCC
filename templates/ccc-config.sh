#!/bin/bash
# ~/.ccc/config — CCC 全局配置
# 由 install-ccc-roles.sh source，导出所有 plist/role 用的变量

# === 路径 ===
# CCC 项目家目录
export CCC_HOME="${CCC_HOME:-/Users/apple/program/CCC}"

# 契约目录（.ccc/ 下）
export CCC_CONTRACT_DIR="${CCC_CONTRACT_DIR:-.ccc}"

# === 看板 HTTP 服务 ===
export BOARD_PORT="${BOARD_PORT:-7777}"
export BOARD_HOST="${BOARD_HOST:-127.0.0.1}"  # 0.0.0.0 = 局域网

# === 角色频率（秒）===
export PRODUCT_INTERVAL="${PRODUCT_INTERVAL:-14400}"   # 4h
export DEV_INTERVAL="${DEV_INTERVAL:-600}"             # 10min
export REVIEWER_INTERVAL="${REVIEWER_INTERVAL:-7200}" # 2h
export TESTER_INTERVAL="${TESTER_INTERVAL:-14400}"     # 4h
export OPS_INTERVAL="${OPS_INTERVAL:-1800}"             # 30min
export REGRESS_INTERVAL="${REGRESS_INTERVAL:-86400}"   # daily 23:30
# kb 用 StartCalendarInterval
export KB_HOUR="${KB_HOUR:-23}"
export KB_MINUTE="${KB_MINUTE:-0}"
export REGRESS_HOUR="${REGRESS_HOUR:-23}"
export REGRESS_MINUTE="${REGRESS_MINUTE:-30}"

# === 角色（7 个）===
ROLES=(product dev reviewer tester ops kb regress)
LABELS_CN=(产品经理 开发 审查 测试 运维 归档 回测)
export PRODUCT_LABEL="产品经理"
export DEV_LABEL="开发"
export REVIEWER_LABEL="审查"
export TESTER_LABEL="测试"
export OPS_LABEL="运维"
export KB_LABEL="归档"
export REGRESS_LABEL="回测"

# === 后端 agent ===
# opencode 是 dev 角色用的，config 可改
export OPENCODE_BIN="${OPENCODE_BIN:-opencode}"
export OPENCODE_MODEL="${OPENCODE_MODEL:-loop/flash}"

# === 重试与容错 ===
export DEV_MAX_RETRY="${DEV_MAX_RETRY:-5}"        # 最大重试次数 → 异常列
export DEV_BACKOFF_INIT="${DEV_BACKOFF_INIT:-60}"  # 退避初始秒数
export MAX_STALE_HOURS="${MAX_STALE_HOURS:-6}"      # in_progress 超时阈值
export DEV_MAX_EXEC_TIME="${DEV_MAX_EXEC_TIME:-3600}"  # 单次执行最大秒数

# === opencode CLI 调用 ===
export AGENT_PLANNER="${AGENT_PLANNER:-claude}"
export AGENT_PLANNER_BASE_URL="${AGENT_PLANNER_BASE_URL:-http://127.0.0.1:4000}"
