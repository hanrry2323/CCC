"""B1：executors 注册表一致性测试（裁定单 2026-09-12-cc-v3-ruling）。
1. 槽位数=8，含「验收席-DSH」。
2. 主链「验收席」行命令仍=cc-auditor.sh（R1 防误改守卫）。
3. 原 7 槽逐字段不变（与 .bak-before-plugin01-b1 比对）。
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "server" / "config" / "executors.json"
BAK = REPO / "server" / "config" / "executors.json.bak-before-plugin01-b1"


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_slot_count_and_b1():
    R = _load(SRC)
    roles = [e["角色"] for e in R["executors"]]
    assert len(roles) == 8, roles
    assert "验收席-DSH" in roles


def test_main_auditor_unchanged():
    R = _load(SRC)
    zr = [e for e in R["executors"] if e["角色"] == "验收席"][0]
    assert zr["命令"].endswith("cc-auditor.sh")
    assert zr["当前绑定"] == "后段 CC CLI（claude wrapper，主链 phase2）"


def test_first_seven_slots_identical():
    a = _load(BAK)["executors"]
    b = _load(SRC)["executors"]
    assert a == b[:7]
