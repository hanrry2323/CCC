#!/usr/bin/env bash
# ── CCC 出卡模板：生成标准任务卡骨架（T52 自动化基建 第 1 件） ──
#
# 生成 `T<序号>-<slug>.md` 到目标任务卡目录，包含标准卡头字段与
# 目标/红线/范围/步骤/验收标准/回写要求/回写区 七个骨架节；
# 自动查重（编号唯一 + 同名卡拒绝）+ 编号自增；写卡后自动联动
# `server/board/validate.py` 门禁校验（不合规卡直接报错）。
#
# 用法：
#   scripts/new-card.sh [选项]
#
# 选项：
#   --title "标题"            卡标题（必填；slug 由标题 ASCII 词派生，空则用 --slug）
#   --project <前缀>          卡头「项目」字段（默认 ccc）
#   --executor "Claude Code"  卡头「执行体」字段（默认 $CCC_CARD_EXECUTOR 或 Claude Code）
#   --acceptance "Codex"      卡头「验收」字段（默认 $CCC_CARD_ACCEPTANCE 或 Codex）
#   --related "关联文本"       卡头「关联」字段（默认 "阶段 3 P1"）
#   --dispatch engine|manual  卡头「派发」字段（默认 engine）
#   --dispatch-dir <目录>     任务卡目录（默认 docs/dispatch；测试可用临时目录）
#   --id T90-test             显式卡编号（跳过自动自增；格式 T<数字|-slug>）
#   --slug <slug>             文件名 slug 覆盖（默认从标题派生）
#   --dry-run                 只打印卡内容与目标路径，不写文件
#   --quiet                   不打印写卡日志
#
# 环境变量（零硬编码，可覆盖默认值）：
#   CCC_CARD_EXECUTOR / CCC_CARD_ACCEPTANCE / CCC_PYTHON_BIN

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── 默认值（可用环境变量覆盖） ──
DISPATCH_DIR="${CCC_DISPATCH_DIR:-docs/dispatch}"
PROJECT_PREFIX="${CCC_CARD_PROJECT:-ccc}"
EXECUTOR="${CCC_CARD_EXECUTOR:-Claude Code}"
ACCEPTANCE="${CCC_CARD_ACCEPTANCE:-Codex}"
RELATED="${CCC_CARD_RELATED:-阶段 3 P1}"
DISPATCH="${CCC_CARD_DISPATCH:-engine}"
PYTHON_BIN="${CCC_PYTHON_BIN:-}"

TITLE=""
ID_OVERRIDE=""
SLUG_OVERRIDE=""
DRY_RUN=false
QUIET=false

usage() {
  sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title) TITLE="$2"; shift 2 ;;
    --project) PROJECT_PREFIX="$2"; shift 2 ;;
    --executor) EXECUTOR="$2"; shift 2 ;;
    --acceptance) ACCEPTANCE="$2"; shift 2 ;;
    --related) RELATED="$2"; shift 2 ;;
    --dispatch) DISPATCH="$2"; shift 2 ;;
    --dispatch-dir) DISPATCH_DIR="$2"; shift 2 ;;
    --id) ID_OVERRIDE="$2"; shift 2 ;;
    --slug) SLUG_OVERRIDE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --quiet) QUIET=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] 未知参数: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$TITLE" ]]; then
  echo "[ERROR] 缺少 --title（卡标题必填）" >&2
  usage
  exit 2
fi

# 解析 python 解释器（写卡后联动 validate 需要）
if [[ -z "$PYTHON_BIN" ]]; then
  for cand in /usr/local/bin/python3 python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then PYTHON_BIN="$cand"; break; fi
  done
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "[ERROR] 未找到 python3（设置 CCC_PYTHON_BIN 指定）" >&2
  exit 2
fi

# 解析目标目录（相对路径按仓库根解析）
case "$DISPATCH_DIR" in
  /*) TARGET_DIR="$DISPATCH_DIR" ;;
  *)  TARGET_DIR="$PROJECT_ROOT/$DISPATCH_DIR" ;;
esac

# ── 编号：--id 覆盖 or 自动自增 ──
declare -a CARD_IDS=()
next_num=0
if [[ -d "$TARGET_DIR" ]]; then
  for f in "$TARGET_DIR"/T[0-9]*.md; do
    [[ -e "$f" ]] || continue
    base="$(basename "$f" .md)"
    CARD_IDS+=("$base")
    if [[ "$base" =~ ^T([0-9]+) ]]; then
      n=$((10#${BASH_REMATCH[1]}))
      (( n > next_num )) && next_num=$n
    fi
  done
fi

if [[ -n "$ID_OVERRIDE" ]]; then
  CARD_ID="$ID_OVERRIDE"
  # 查重：显式 ID 的数字前缀已存在（如 --id T1 命中 T1-t52.md）则拒绝
  id_num="$(printf '%s' "$CARD_ID" | sed -nE 's/^T([0-9]+).*/\1/p')"
  for existing in "${CARD_IDS[@]:-}"; do
    existing_num="$(printf '%s' "$existing" | sed -nE 's/^T([0-9]+).*/\1/p')"
    if [[ -n "$id_num" && -n "$existing_num" && "$id_num" == "$existing_num" ]]; then
      echo "[ERROR] 卡编号冲突：${CARD_ID} 与 ${existing} 重复（T${id_num} 已存在）" >&2
      exit 3
    fi
  done
else
  CARD_ID="T$(( next_num + 1 ))"
fi

# ── slug：显式 or 从标题派生（ASCII 词；中文标题回落 task） ──
if [[ -n "$SLUG_OVERRIDE" ]]; then
  SLUG="$SLUG_OVERRIDE"
else
  # 只保留 ASCII 字母数字，其余折叠为单个 '-'（BSD sed 对 `\+` 字符类重复支持不稳，用 tr -c）
  SLUG="$(printf '%s' "$TITLE" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed 's/-\{1,\}/-/g; s/^-//; s/-$//')"
  [[ -z "$SLUG" ]] && SLUG="task"
fi

CARD_FILE="${CARD_ID}-${SLUG}.md"
CARD_PATH="$TARGET_DIR/$CARD_FILE"
if [[ -e "$CARD_PATH" ]]; then
  echo "[ERROR] 同名卡已存在：$CARD_PATH" >&2
  exit 3
fi

# ── 卡骨架 ──
TODAY="$(date +%Y-%m-%d)"
read -r -d '' CARD_BODY <<EOF || true
# 任务卡 ${CARD_ID} · ${TITLE}（${EXECUTOR} 执行）

> 关联：${RELATED} · 执行体：${EXECUTOR} · 验收：${ACCEPTANCE} · 状态：待分派 · 派发：${DISPATCH} · 项目：${PROJECT_PREFIX} · 日期：${TODAY}

## 目标

（一句话，可验收。）

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）

## 范围

（明确本卡改动范围，白名单式列出。）

## 步骤

1. （可执行步骤，每步有可验证产物）

## 验收标准

1. （可执行的验收点，附命令/可观察结果）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据。

## 回写区

**执行体**：${EXECUTOR} · 日期：
EOF

if [[ "$DRY_RUN" == true ]]; then
  echo "# [dry-run] 目标文件: $CARD_PATH"
  printf '%s\n' "$CARD_BODY"
  exit 0
fi

mkdir -p "$TARGET_DIR"
printf '%s\n' "$CARD_BODY" > "$CARD_PATH"

# ── 联动 validate 门禁：不合规卡拒绝并删除 ──
if ( cd "$PROJECT_ROOT" && "$PYTHON_BIN" -m server.board.validate "$TARGET_DIR" ); then
  [[ "$QUIET" != true ]] && echo "[OK] 出卡成功 + validate 通过: $CARD_PATH"
  exit 0
else
  echo "[ERROR] validate 校验失败，已删除生成卡：$CARD_PATH" >&2
  rm -f "$CARD_PATH"
  exit 1
fi
