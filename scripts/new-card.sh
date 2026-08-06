#!/usr/bin/env bash
# ── CCC 出卡模板：生成标准任务卡骨架（命名定死 · 见 docs/DOC-PROTOCOL.md §2） ──
#
# 生成 `<前缀><三位序号>-<slug>.md` 到 `<dispatch-dir>/<前缀>/` 子目录，
# 包含标准卡头字段与 目标/红线/范围/步骤/验收标准/回写要求/回写区 七节；
# 前缀序号自增（同前缀最大序号 +1，三位补零）+ 同名/同编号查重 + slug 校验；
# 写卡后自动联动 `server/board/validate.py` 门禁（不合规卡直接删除报错）。
#
# 命名公式（硬）：docs/dispatch/<prefix>/<prefix><NNN>-<slug>.md
#   prefix = registry 前缀 = 子目录 = 卡头「项目」（2-4 位小写）
#   NNN    = 三位数字，同前缀唯一
#   slug   = [a-z0-9]+(-[a-z0-9]+)*
# 分支惯例：codex/<文件名去.md>；禁止新 T*.md；禁止前缀 qh。
#
# 用法：
#   scripts/new-card.sh [选项]
#
# 选项：
#   --title "标题"            卡标题（必填；slug 由标题 ASCII 词派生，空则用 --slug）
#   --project <前缀>          项目前缀 = 子目录名 = 卡头「项目」（默认 ccc；见 T-mapping.md）
#   --executor "OpenCode"     卡头「执行体」（默认 $CCC_CARD_EXECUTOR 或 OpenCode）
#   --acceptance "Claude Code" 卡头「验收」（默认按执行体交叉；OpenCode→Claude Code）
#   --related "关联文本"       卡头「关联」字段（默认 "阶段 3 P1"）
#   --dispatch engine|manual  卡头「派发」字段（默认 engine）
#   --dispatch-dir <目录>     任务卡目录（默认 docs/dispatch；测试可用临时目录）
#   --id <前缀><NNN>[-slug]   显式卡编号（跳过自增；如 ccc064-auto-naming）
#   --slug <slug>             文件名 slug 覆盖（默认从标题派生；小写字母数字+单连字符）
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
EXECUTOR="${CCC_CARD_EXECUTOR:-OpenCode}"
ACCEPTANCE_EXPLICIT=false
ACCEPTANCE="${CCC_CARD_ACCEPTANCE:-}"
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
    --acceptance) ACCEPTANCE="$2"; ACCEPTANCE_EXPLICIT=true; shift 2 ;;
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

# 交叉验收默认：未显式 --acceptance 时按执行体配对（OpenCode↔Claude Code）
if [[ "$ACCEPTANCE_EXPLICIT" != true ]]; then
  case "$EXECUTOR" in
    "OpenCode"|"opencode") ACCEPTANCE="Claude Code" ;;
    "Claude Code"|"Claude"|"claude") ACCEPTANCE="OpenCode" ;;
    *) ACCEPTANCE="${CCC_CARD_ACCEPTANCE:-Claude Code}" ;;
  esac
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

# ── T54：前缀 = 子目录名 = 卡头「项目」；粗校验（2-4 位小写字母），未知前缀由 validate 拦截 ──
if [[ ! "$PROJECT_PREFIX" =~ ^[a-z]{2,4}$ ]]; then
  echo "[ERROR] 前缀非法: ${PROJECT_PREFIX}（须 2-4 位小写字母；合法表见 docs/projects/registry.yaml · DOC-PROTOCOL §2）" >&2
  exit 2
fi
# QuantHive 禁止走 CCC（双轨独立）
if [[ "$PROJECT_PREFIX" == "qh" ]]; then
  echo "[ERROR] 前缀 qh（QuantHive）禁止走 CCC Engine 出卡；QuantHive 独立轨道开发" >&2
  exit 2
fi

# 解析目标目录（相对路径按仓库根解析）
case "$DISPATCH_DIR" in
  /*) TARGET_DIR="$DISPATCH_DIR" ;;
  *)  TARGET_DIR="$PROJECT_ROOT/$DISPATCH_DIR" ;;
esac
PREFIX_DIR="$TARGET_DIR/$PROJECT_PREFIX"

# ── 编号：--id 覆盖 or 前缀内自动自增（同前缀最大序号 +1，三位补零） ──
next_num=0
if [[ -d "$PREFIX_DIR" ]]; then
  for f in "$PREFIX_DIR"/"$PROJECT_PREFIX"[0-9][0-9][0-9]-*.md; do
    [[ -e "$f" ]] || continue
    base="$(basename "$f" .md)"
    if [[ "$base" =~ ^"$PROJECT_PREFIX"([0-9]{3}) ]]; then
      n=$((10#${BASH_REMATCH[1]}))
      (( n > next_num )) && next_num=$n
    fi
  done
fi

if [[ -n "$ID_OVERRIDE" ]]; then
  # 显式编号：<前缀><NNN> 或 <前缀><NNN>-<slug>；前缀必须与 --project 一致
  if [[ "$ID_OVERRIDE" =~ ^([a-z]{2,4})([0-9]{3})(-[a-z0-9]+(-[a-z0-9]+)*)?$ ]]; then
    id_prefix="${BASH_REMATCH[1]}"
    id_num="${BASH_REMATCH[2]}"
    id_slug="${BASH_REMATCH[3]:1}"  # 去前导 '-'，空则从标题派生
    if [[ "$id_prefix" != "$PROJECT_PREFIX" ]]; then
      echo "[ERROR] --id 前缀 ${id_prefix} 与 --project ${PROJECT_PREFIX} 不一致（前缀=子目录名=卡头项目）" >&2
      exit 3
    fi
    # 查重：同前缀同序号已存在则拒绝
    for f in "$PREFIX_DIR"/"$PROJECT_PREFIX"[0-9][0-9][0-9]-*.md; do
      [[ -e "$f" ]] || continue
      existing="$(basename "$f" .md)"
      if [[ "$existing" =~ ^"$PROJECT_PREFIX"([0-9]{3}) && "${BASH_REMATCH[1]}" == "$id_num" ]]; then
        echo "[ERROR] 卡编号冲突：${ID_OVERRIDE} 与 ${existing} 重复（${PROJECT_PREFIX}${id_num} 已存在）" >&2
        exit 3
      fi
    done
  else
    echo "[ERROR] --id 格式非法: $ID_OVERRIDE（须 <前缀><三位序号>[-slug]，如 ccc064-auto-naming）" >&2
    exit 3
  fi
  CARD_ID="${id_prefix}${id_num}"
  [[ -n "$id_slug" ]] && SLUG_OVERRIDE="$id_slug"
else
  CARD_ID="$(printf '%s%03d' "$PROJECT_PREFIX" "$(( next_num + 1 ))")"
fi

# ── slug：显式 or 从标题派生（ASCII 词；中文标题回落 task）；T54 校验小写字母数字+单连字符 ──
if [[ -n "$SLUG_OVERRIDE" ]]; then
  SLUG="$SLUG_OVERRIDE"
else
  # 只保留 ASCII 字母数字，其余折叠为单个 '-'（BSD sed 对 `\+` 字符类重复支持不稳，用 tr -c）
  SLUG="$(printf '%s' "$TITLE" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed 's/-\{1,\}/-/g; s/^-//; s/-$//')"
  [[ -z "$SLUG" ]] && SLUG="task"
fi
if [[ ! "$SLUG" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo "[ERROR] slug 非法: ${SLUG}（须小写字母数字开头结尾，可含单连字符分隔）" >&2
  exit 2
fi

CARD_FILE="${CARD_ID}-${SLUG}.md"
CARD_PATH="$PREFIX_DIR/$CARD_FILE"
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
2. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
3. **停手**：禁止写 \`## 机审区\` / \`## 验收区\` / 置「已关闭」。等 2017 机审 → 老板「验收看板」终验。

## 验收标准

1. （可执行的验收点，附命令/可观察结果）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 \`## 机审区\`；人工终验听「验收看板」后写 \`## 验收区\`+已关闭。

## 回写区

**执行体**：${EXECUTOR} · 日期：
EOF

if [[ "$DRY_RUN" == true ]]; then
  echo "# [dry-run] 目标文件: $CARD_PATH"
  printf '%s\n' "$CARD_BODY"
  exit 0
fi

mkdir -p "$PREFIX_DIR"
printf '%s\n' "$CARD_BODY" > "$CARD_PATH"

# ── 联动 validate 门禁：不合规卡拒绝并删除 ──
# ccc003 修复：validate 前先刷新卡片索引（走 server.board 加载/落盘，使新卡入索引），
# 否则已有索引时新卡未入 index → validate 对账报「索引缺失」误删新卡。禁止手改索引缓存。
if ! ( cd "$PROJECT_ROOT" && "$PYTHON_BIN" -c "
import sys
from server.board.loader import load_dispatch_cards
load_dispatch_cards(sys.argv[1])
" "$TARGET_DIR" ); then
  echo "[ERROR] 刷新卡片索引失败：$TARGET_DIR" >&2
  rm -f "$CARD_PATH"
  exit 1
fi

if ( cd "$PROJECT_ROOT" && "$PYTHON_BIN" -m server.board.validate "$TARGET_DIR" ); then
  [[ "$QUIET" != true ]] && echo "[OK] 出卡成功 + validate 通过: $CARD_PATH"
  exit 0
else
  echo "[ERROR] validate 校验失败，已删除生成卡：$CARD_PATH" >&2
  rm -f "$CARD_PATH"
  exit 1
fi
