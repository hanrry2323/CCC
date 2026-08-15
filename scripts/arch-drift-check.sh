#!/bin/bash
# ── 架构漂移门禁（第三步 · PRIME-DIRECTIVE §6.2 合入前职责）──
# 每次合入前机械检查：数据模型与权威文档一致、三层关系完整、旧代码清理。
# 4 项纯机械检查，任一失败 → 退出码 1 阻断合入（老板 2026-08-13 定：首版阻断）。
# 用法：bash scripts/arch-drift-check.sh
# 挂载：approve-merge.sh 门禁 0 之后（机审证据之前）

set -uo pipefail
CCC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$CCC_ROOT" || exit 1

failures=0

say() { printf '%s\n' "$*"; }

fail() {
  say "✗ $*"
  failures=$((failures + 1))
}

pass() { say "✓ $*"; }

# ── 1. 卡头「项目」字段 vs registry（validate.py 未查此项）────────
proj_bad=$(python3 - "$CCC_ROOT" << 'PYEOF'
import re, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from server.board.registry import load_projects  # type: ignore[import-untyped]
try:
    projs = {p.prefix for p in load_projects(str(root / "docs" / "projects" / "registry.yaml"))}
except Exception as e:
    print(f"REGISTRY_ERROR:{e}")
    raise SystemExit(0)
bad = []
for card in sorted((root / "docs" / "dispatch").glob("**/*.md")):
    text = card.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"项目：([^\s·]+)", text)
    if m and m.group(1) not in projs:
        bad.append(f"{card.name}: 项目字段「{m.group(1)}」不在 registry")
print("\n".join(bad))
PYEOF
)
if [ -n "$proj_bad" ]; then
  if echo "$proj_bad" | grep -q "^REGISTRY_ERROR"; then
    fail "registry 加载失败: $proj_bad"
  else
    while IFS= read -r line; do [ -n "$line" ] && fail "卡头项目漂移: $line"; done <<< "$proj_bad"
  fi
else
  pass "卡头「项目」字段与 registry 一致"
fi

# ── 2. 退役端口扫描（活代码/配置；历史文档白名单排除）────────────
RETIRED_PORTS="17777 7775 7778 11434"
port_hits=""
for port in $RETIRED_PORTS; do
  hits=$(grep -rn --include="*.py" --include="*.sh" --include="*.json" --include="*.yaml" --include="*.yml" --include="*.env" \
    -E "(^|[^0-9])${port}([^0-9]|$)" server/ scripts/ .github/ 2>/dev/null \
    | grep -vE "docs/archive|test_kb_seed_integrity|RETIRED_PORTS|tests/|退役端口" || true)
  if [ -n "$hits" ]; then
    port_hits="${port_hits}${hits}\n"
  fi
done
if [ -n "$port_hits" ]; then
  fail "退役端口出现在活代码/配置:"
  printf '%s\n' "$port_hits" | sed 's/^/    /'
else
  pass "退役端口未出现在活代码/配置: ${RETIRED_PORTS}"
fi

# ── 3. VERSION vs CHANGELOG 最新条目一致性 ──────────────────────
version=$(cat VERSION 2>/dev/null | tr -d 'v \n')
changelog_top=$(grep -m1 -E '^## \[v[0-9]+\.[0-9]+\.[0-9]+\]' CHANGELOG.md 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | tr -d 'v')
if [ -z "$version" ] || [ -z "$changelog_top" ]; then
  fail "VERSION 或 CHANGELOG 缺失"
elif [ "$version" != "$changelog_top" ]; then
  fail "版本不一致: VERSION=v${version} vs CHANGELOG 最新=v${changelog_top}"
else
  pass "VERSION（v${version}）与 CHANGELOG 最新条目一致"
fi

# ── 4. 死文件清单检查（清单内文件不得存在，防复活）─────────────
dead_resurrected=""
while IFS= read -r line; do
  case "$line" in
    "" | "#"*) continue ;;
  esac
  if [ -e "$CCC_ROOT/$line" ]; then
    dead_resurrected="${dead_resurrected}${line}\n"
  fi
done < scripts/arch-dead-files.txt
if [ -n "$dead_resurrected" ]; then
  fail "死文件复活（已在 arch-dead-files.txt 登记，必须不存在）:"
  printf '%s\n' "$dead_resurrected" | sed 's/^/    /'
else
  pass "死文件清单无复活（arch-dead-files.txt 登记文件全部不存在）"
fi

# ── 汇总 ───────────────────────────────────────────────────────
if [ "$failures" -gt 0 ]; then
  say ""
  say "架构漂移门禁未通过（${failures} 项）——阻断合入。"
  exit 1
fi
say ""
say "架构漂移门禁通过（4/4）。"
exit 0
