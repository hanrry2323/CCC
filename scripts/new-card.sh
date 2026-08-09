#!/usr/bin/env bash
# ── CCC 出卡模板：生成标准任务卡骨架（命名定死 · 见 docs/DOC-PROTOCOL.md §2） ──
#
# 生成 `<前缀><三位序号>-<slug>.md` 到 `<dispatch-dir>/<前缀>/` 子目录，
# 包含标准卡头字段与 目标/红线/范围/步骤/验收标准/回写要求/人工批注/回写区 八节；
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
#   --acceptance "Claude Code" 卡头「验收」（默认自验收：与执行体同工具）
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

# 自验收默认：未显式 --acceptance 时验收 = 执行体本身（谁开发谁验收）
if [[ "$ACCEPTANCE_EXPLICIT" != true ]]; then
  ACCEPTANCE="${CCC_CARD_ACCEPTANCE:-$EXECUTOR}"
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
  # 方案链编号保护 Check (Step 5)
  if ! "$PYTHON_BIN" -c "
import sys, re, os
from pathlib import Path

card_id = sys.argv[1]
match = re.match(r'^([a-z]{2,4})(\d{3})$', card_id.lower())
if not match:
    sys.exit(0)
pref, num_str = match.groups()
num = int(num_str)

projects_dir = Path('docs/projects')
if not projects_dir.is_dir():
    sys.exit(0)

for p in projects_dir.glob('**/plans/*.md'):
    try:
        text = p.read_text(encoding="utf-8")
        for line in text.splitlines():
            if '关联卡：' in line:
                ids = re.findall(r'([a-z]{2,4})(\d{3})', line.lower())
                proj_ids = [int(n) for pr, n in ids if pr == pref]
                if proj_ids:
                    min_id, max_id = min(proj_ids), max(proj_ids)
                    if min_id <= num <= max_id:
                        print(f'[ERROR] 方案链编号保护：自动编号 {card_id} 落在方案 {p.name} 已声明的编号区间 [{pref}{min_id:03d}, {pref}{max_id:03d}] 内。为了防止吃掉方案链保留编号，要求显式使用 --id 编号，或者将附加卡/修复卡显式指定编号。', file=sys.stderr)
                        sys.exit(1)
    except Exception:
        pass
sys.exit(0)
" "$CARD_ID"; then
    exit 3
fi
  [[ "$QUIET" != true ]] && echo "[提示] 附加卡/修复卡建议使用 --id 显式编号，避免占用方案主链的自动编号空间。"
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

# ── 基准文件节：从 docs/projects/<prefix>/ 自动生成（注册即带基准，缺基准时给指引） ──
BASELINE=""
PROJ_README="$PROJECT_ROOT/docs/projects/$PROJECT_PREFIX/README.md"
PROJ_PLANS="$PROJECT_ROOT/docs/projects/$PROJECT_PREFIX/plans"
if [[ -f "$PROJ_README" ]]; then
  BASELINE="- 项目基准（README·权威索引）：\`docs/projects/$PROJECT_PREFIX/README.md\`"
fi
if [[ -d "$PROJ_PLANS" && -n "$(ls "$PROJ_PLANS" 2>/dev/null)" ]]; then
  if [[ -n "$BASELINE" ]]; then BASELINE+="
"; fi
  BASELINE+="- 方案池：\`docs/projects/$PROJECT_PREFIX/plans/\`（关联方案见卡头「关联」）"
fi
if [[ -z "$BASELINE" ]]; then
  BASELINE="- 本项目暂无基准文件。执行前必须先补齐项目基准（\`docs/projects/$PROJECT_PREFIX/README.md\` 五节档案），再执行本卡；缺少基准的卡视为流程缺陷，机审打回。"
fi

read -r -d '' CARD_BODY <<EOF || true
# 任务卡 ${CARD_ID} · ${TITLE}（${EXECUTOR} 执行）

> 关联：${RELATED} · 执行体：${EXECUTOR} · 验收：${ACCEPTANCE} · 状态：待分派 · 派发：${DISPATCH} · 项目：${PROJECT_PREFIX} · 日期：${TODAY}

## 基准文件（先看）

${BASELINE}

## 目标

（一句话，可验收。）

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 \`## 人工批注\`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

（明确本卡改动范围，白名单式列出。）

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 \`git fetch origin && git rebase origin/main\`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 \`## 机审区\` / \`## 验收区\` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. （可执行的验收点，附命令/可观察结果）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成 `## 维护区` 四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：${EXECUTOR} · 日期：

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：\`关联方案\` 状态/关联卡是否已同步？[是/否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：
2. **教训沉淀**：本卡是否产出可复用教训？[有/无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是/否]（是 → 项目档案 \`docs/projects/<prefix>/README.md\` 同步更新）
   - 说明：
4. **线路图**：项目近况/下一步是否变化？[是/否]（是 → \`docs/roadmap.md\` 或档案「线路/近况」更新）
   - 说明：

## 批注落实

（若卡含 \`## 人工批注\`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

（中枢在出卡时注入，执行体（开发大模型）读到本节后优先遵循。）

## 机审提示

（中枢在出卡时注入，验收体（机审大模型）读到本节后优先遵循。）
EOF

if [[ "$DRY_RUN" == true ]]; then
  echo "# [dry-run] 目标文件: $CARD_PATH"
  printf '%s\n' "$CARD_BODY"
  exit 0
fi

mkdir -p "$PREFIX_DIR"
printf '%s\n' "$CARD_BODY" > "$CARD_PATH"

# ── 中枢 Prompt 注入：从 registry + README + KB 生成 LLM 专用提示段 ──
# 注入执行提示（给开发大模型）和机审提示（给验收大模型），
# 仅当卡文件含空占位段时才注入，已有内容不覆盖。
if ( cd "$PROJECT_ROOT" && "$PYTHON_BIN" -m server.board.prompt_inject "$CARD_PATH" --project "$PROJECT_PREFIX" --title "$TITLE" ); then
  [[ "$QUIET" != true ]] && echo "[OK] 提示段注入成功"
else
  # 注入失败不阻塞出卡（提示段为可选增强）
  [[ "$QUIET" != true ]] && echo "[WARN] 提示段注入失败（卡已生成，提示段保持占位符）" >&2
fi

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
