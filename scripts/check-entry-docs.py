#!/usr/bin/env python3
"""入口文档门禁：AGENTS.md / CLAUDE.md 零硬编码 + 必需指针。

规则（2026-08-08 · 通用化制度）：
1. 入口文档不得出现机器路径 / IP / 端口（真值源 = registry.yaml / topology.md / 工具绑定表）。
2. 通用入口（AGENTS.md / CLAUDE.md）必须指向：制卡发卡操作手册、DOC-PROTOCOL、registry。
（CURSOR.md 随 Cursor 弃用 2026-08-14 移除）

用法：
    python3 scripts/check-entry-docs.py          # 检查仓库根入口文档
    python3 scripts/check-entry-docs.py --json   # JSON 输出（供 CI）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ENTRY_DOCS = ["AGENTS.md", "CLAUDE.md"]

# 禁止出现在入口文档的模式（机器细节应进真值源）
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"/Users/", "机器绝对路径"),
    (r"192\.168\.", "局域网 IP"),
    (r":7788", "生产端口 7788"),
    (r":6100", "端口 6100"),
    (r":6102", "端口 6102"),
    (r":7775", "退役端口 7775"),
    (r":7777", "退役端口 7777"),
    (r":4102", "退役端口 4102"),
]

# 通用入口必须指向的文档（防双入口漂移）
REQUIRED_REFERENCES = [
    "docs/product/card-hub-manual.md",
    "docs/DOC-PROTOCOL.md",
    "docs/projects/registry.yaml",
]

def check_entry_docs(root: Path | None = None) -> list[str]:
    """返回违规清单；空列表 = 通过。"""
    root = root or ROOT
    violations: list[str] = []
    for name in ENTRY_DOCS:
        path = root / name
        if not path.is_file():
            violations.append(f"[{name}] 入口文档缺失")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, label in FORBIDDEN_PATTERNS:
            if re.search(pattern, text):
                violations.append(f"[{name}] 含{label}（{pattern}）——机器细节应进 registry/topology/绑定表")
        required = REQUIRED_REFERENCES
        for ref in required:
            if ref not in text:
                violations.append(f"[{name}] 缺少必需指针：{ref}")
    return violations


def main() -> int:
    violations = check_entry_docs()
    if "--json" in sys.argv:
        print(json.dumps({"ok": not violations, "violations": violations}, ensure_ascii=False))
    else:
        if violations:
            print("[FAIL] 入口文档门禁未通过：", file=sys.stderr)
            for v in violations:
                print(f"  - {v}", file=sys.stderr)
        else:
            print("[OK] 入口文档门禁通过（零硬编码 + 必需指针齐全）")
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main())
