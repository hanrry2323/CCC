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

  # 4. Claude Code symlink (optional)
  if [ -L "$CLAUDE_TARGET" ]; then
    local claude_real
    claude_real="$(readlink "$CLAUDE_TARGET")"
    if [ "$claude_real" = "$CCC_DIR" ]; then
      echo "  [OK]   Claude Code symlink: $CLAUDE_TARGET → $CCC_DIR"
    else
      echo "  [WARN] Claude Code symlink target mismatch: $claude_real"
    fi
  else
    echo "  [WARN] Claude Code symlink not found: $CLAUDE_TARGET (optional — skip if not using Claude Code)"
  fi

  # 5. ZCode symlink
  if [ -L "$ZCODE_TARGET" ]; then
    local zcode_real
    zcode_real="$(readlink "$ZCODE_TARGET")"
    if [ "$zcode_real" = "$CCC_DIR" ]; then
      echo "  [OK]   ZCode symlink: $ZCODE_TARGET → $CCC_DIR"
    else
      echo "  [FAIL] ZCode symlink target mismatch: $zcode_real (expected $CCC_DIR)"
      errors=$((errors + 1))
    fi
  else
    echo "  [WARN] ZCode symlink not found: $ZCODE_TARGET"
    echo "         Run without --check to install, or link manually: ln -sfn $CCC_DIR $ZCODE_TARGET"
  fi

  # 6. references/ structure
  local ref_count
  ref_count="$(find "$CCC_DIR/references" -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$ref_count" -ge 6 ]; then
    echo "  [OK]   references/ has $ref_count files"
  else
    echo "  [FAIL] references/ has only $ref_count files (expected >=6)"
    errors=$((errors + 1))
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

  # --- Claude Code symlink (optional) ---
  if [ -d "$HOME/.claude/skills" ] || mkdir -p "$HOME/.claude/skills" 2>/dev/null; then
    if [ -L "$CLAUDE_TARGET" ] || [ -d "$CLAUDE_TARGET" ]; then
      rm -f "$CLAUDE_TARGET"
    fi
    ln -sfn "$CCC_DIR" "$CLAUDE_TARGET"
    echo "  [OK] Claude Code: $CLAUDE_TARGET → $CCC_DIR"
  else
    echo "  [WARN] ~/.claude/skills/ not accessible — skipping Claude Code symlink"
  fi

  # --- ZCode symlink ---
  mkdir -p "$(dirname "$ZCODE_TARGET")"
  if [ -L "$ZCODE_TARGET" ] || [ -d "$ZCODE_TARGET" ]; then
    rm -f "$ZCODE_TARGET"
  fi
  ln -sfn "$CCC_DIR" "$ZCODE_TARGET"
  echo "  [OK] ZCode: $ZCODE_TARGET → $CCC_DIR"

  echo ""

  # --- Output setup snippets ---
  echo "=== Cursor .cursorrules snippet (append to project .cursorrules) ==="
  echo ""
  echo "ref: $CCC_DIR/SKILL.md"
  echo ""

  echo "=== AGENTS.md reference snippet (paste into project AGENTS.md) ==="
  echo ""
  echo "CCC protocol: read $CCC_DIR/SKILL.md for multi-phase plan-execute-verify workflow"
  echo ""

  echo "Done. Run with --check to verify."
}

# ---- Main ----
if [ "${1:-}" = "--check" ]; then
  check_install
else
  do_install
fi
