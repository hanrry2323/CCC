#!/bin/bash
#
# install-ccc-as-skill.sh — 跨工具安装 CCC skill
#
# 功能:
#   1. 检测平台 (macOS / Linux / Windows WSL)
#   2. 在 ~/.mavis/skills/ccc-protocol 创建 symlink → ~/program/CCC
#   3. 在 ~/.claude/skills/ccc-protocol/ 创建 symlink（如果 Claude Code skills 路径存在）
#   4. 在 ~/.zcode/skills/ccc-protocol 创建 symlink（如果 ZCode skills 路径存在）
#   5. --check 模式: 验证安装状态 (6 项)
#   6. 输出 Cursor/AGENTS.md 引用片段
#
# 用法:
#   bash install-ccc-as-skill.sh          # 执行安装
#   bash install-ccc-as-skill.sh --check  # 仅检查不安装

set -euo pipefail

CCC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_FILE="$CCC_DIR/SKILL.md"
MAVIS_TARGET="$HOME/.mavis/skills/ccc-protocol"
CLAUDE_TARGET="$HOME/.claude/skills/ccc-protocol"
ZCODE_TARGET="$HOME/.zcode/skills/ccc-protocol"

# ---- Platform detection ----
detect_platform() {
  case "$(uname -s)" in
    Darwin)  echo "macOS" ;;
    Linux)
      if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "WSL"
      else
        echo "Linux"
      fi
      ;;
    MINGW*|MSYS*|CYGWIN*) echo "Windows" ;;
    *)                     echo "Unknown:$(uname -s)" ;;
  esac
}

# ---- Check mode ----
check_install() {
  local errors=0

  # 1. SKILL.md existence
  if [ -f "$SKILL_FILE" ]; then
    echo "  [OK]   SKILL.md found: $SKILL_FILE"
  else
    echo "  [FAIL] SKILL.md missing: $SKILL_FILE"
    errors=$((errors + 1))
  fi

  # 2. SKILL.md frontmatter
  if grep -q "name: ccc-protocol" "$SKILL_FILE" 2>/dev/null; then
    echo "  [OK]   SKILL.md contains name: ccc-protocol"
  else
    echo "  [FAIL] SKILL.md missing 'name: ccc-protocol'"
    errors=$((errors + 1))
  fi

  # 3. Mavis symlink
  if [ -L "$MAVIS_TARGET" ]; then
    local mavis_real
    mavis_real="$(readlink "$MAVIS_TARGET")"
    if [ "$mavis_real" = "$CCC_DIR" ]; then
      echo "  [OK]   Mavis symlink: $MAVIS_TARGET → $CCC_DIR"
    else
      echo "  [FAIL] Mavis symlink points to $mavis_real (expected $CCC_DIR)"
      errors=$((errors + 1))
    fi
  else
    echo "  [WARN] Mavis symlink not found: $MAVIS_TARGET"
    echo "         Run without --check to install, or link manually: ln -sfn $CCC_DIR $MAVIS_TARGET"
  fi

  # 4–5. 个人 Claude Code / ZCode symlink — 已退役（平台开发只认 Cursor）
  echo "  [SKIP] Claude Code / ZCode skill symlink（退役；平台改动只用 Cursor，见 docs/product/dev-channel.md）"
  if [ -L "$CLAUDE_TARGET" ] || [ -L "$ZCODE_TARGET" ]; then
    echo "  [INFO] 若仍存在旧 symlink，可手动删除；不影响 Engine 执行器"
  fi

  # 6. references/ structure
  local ref_count
  ref_count="$(find "$CCC_DIR/references" -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$ref_count" -ge 1 ]; then
    echo "  [OK]   references/ has $ref_count files"
  else
    echo "  [WARN] references/ empty"
  fi
  # Summary
  echo ""
  if [ "$errors" -eq 0 ]; then
    echo "OK"
    return 0
  else
    echo "ERRORS: $errors"
    return 1
  fi
}

# ---- Install mode ----
do_install() {
  local platform
  platform="$(detect_platform)"
  echo "Platform: $platform"
  echo "CCC dir:  $CCC_DIR"
  echo ""

  # --- Mavis symlink ---
  mkdir -p "$(dirname "$MAVIS_TARGET")"
  if [ -L "$MAVIS_TARGET" ] || [ -d "$MAVIS_TARGET" ]; then
    rm -f "$MAVIS_TARGET"
  fi
  ln -sfn "$CCC_DIR" "$MAVIS_TARGET"
  echo "  [OK] Mavis: $MAVIS_TARGET → $CCC_DIR"

  # --- Claude Code / ZCode symlink — 退役（平台只认 Cursor）---
  echo "  [SKIP] Claude Code / ZCode skill symlink（退役；见 docs/product/dev-channel.md）"

  echo ""

  # --- Output setup snippets ---
  echo "=== Cursor（唯一平台开发工具）==="
  echo ""
  echo "权威：docs/product/loop-engineer-authority.md · docs/product/dev-channel.md"
  echo "SKILL： $CCC_DIR/SKILL.md"
  echo ""

  echo "Done. Run with --check to verify."
}
# ---- Main ----
if [ "${1:-}" = "--check" ]; then
  check_install
else
  do_install
fi
