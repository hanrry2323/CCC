"""board.roles.verify — 最小可跑通唯一验收入口（verify）。

产品语义：plan → code → **verify** → done|blocked。
实现可复用 reviewer（Claude 副闸）+ tester（探针）+ engine pytest；
对外日志与 mind 文案只认 verify 一扇门，不再主推「先 reviewer 再 tester 再 kb」。

权威：docs/product/loop-engineer-authority.md「最小可跑通 v1」。
"""
from __future__ import annotations

from pathlib import Path


def verify_role() -> None:
    """兼容角色名：委托 engine 统一门禁顺序（勿在角色层另开双跳叙事）。"""
    from board.roles.reviewer import reviewer_role
    from board.roles.tester import tester_role

    reviewer_role()
    tester_role()


def run_verify_gate(ws: Path, tid: str) -> bool:
    """唯一 verify 入口 → engine.gates.run_verify_gate。"""
    from engine.gates import run_verify_gate as _gate

    return _gate(ws, tid)


__all__ = ["verify_role", "run_verify_gate"]
