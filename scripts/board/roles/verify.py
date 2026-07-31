"""board.roles.verify — 最小可跑通单一验收入口（verify）。

产品语义：plan→code→**verify**→done。
实现复用 reviewer（Claude 副闸）+ tester（探针）+ engine pytest；
对外叙事不再强调双跳。权威：loop-engineer-authority「最小可跑通 v1」。
"""
from __future__ import annotations

from pathlib import Path

from board.roles.reviewer import reviewer_role
from board.roles.tester import tester_role


def verify_role() -> None:
    """兼容角色调度名：先 reviewer 再 tester（与门禁顺序对齐由 gates 统一）。"""
    reviewer_role()
    tester_role()


def run_verify_gate(ws: Path, tid: str) -> bool:
    """单一 verify 入口 → 委托 engine.gates reviewer+tester 门禁。"""
    from engine.gates import _run_reviewer_tester_gate

    return _run_reviewer_tester_gate(ws, tid)


__all__ = ["verify_role", "run_verify_gate"]
