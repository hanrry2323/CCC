"""入口文档门禁测试：AGENTS.md / CLAUDE.md 零硬编码 + 必需指针（CURSOR.md 已随 Cursor 弃用移除）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location("check_entry_docs", ROOT / "scripts" / "check-entry-docs.py")
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
check_entry_docs = _mod.check_entry_docs


def test_entry_docs_pass_gate() -> None:
    """通用化制度：入口文档不得含机器路径/IP/端口，且必须指向操作手册与 SSOT。"""
    violations = check_entry_docs(ROOT)
    assert violations == [], "\n".join(violations)


def test_common_entries_share_same_soul() -> None:
    """双入口必须同源：都指向同一批权威文档，防止各写一份漂移。"""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for ref in [
        "docs/product/card-hub-manual.md",
        "docs/DOC-PROTOCOL.md",
        "docs/projects/registry.yaml",
        "docs/product/hub-context-sop.md",
        "docs/product/accept-board-sop.md",
    ]:
        assert ref in agents, f"AGENTS.md 缺少 {ref}"
        assert ref in claude, f"CLAUDE.md 缺少 {ref}"
