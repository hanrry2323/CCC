"""B1：executors 注册表一致性测试（裁定单 2026-09-12-cc-v3-ruling）。
1. 槽位数=8，含「验收席-DSH」。
2. 主链「验收席」行命令仍=cc-auditor.sh（R1 防误改守卫）。
3. 原 7 槽逐字段不变（测试内嵌基线指纹，来源=git 历史 2f58f073a；备份文件被仓 .gitignore 的 *.bak-* 规则排除，不入仓不可依赖）。
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "server" / "config" / "executors.json"


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


_BASELINE7 = [('开发执行体', 'DSH', 'dsh-executor.sh'), ('维护执行体', '执行会话 / 自动化值班组件', 'dsh-executor.sh'), ('管理席', '可替换调度插件（现役外脑 Z Code；桌面端休眠）', ''), ('验收席', '后段 CC CLI（claude wrapper，主链 phase2）', 'cc-auditor.sh'), ('只读取证/审计执行体', '自动化值班组件（headless）', 'bash'), ('开发执行体-195', 'PI@195', 'pi-remote-executor.sh'), ('开发执行体-252', 'PI@252', 'pi-remote-executor-252.sh')]


def test_first_seven_slots_fingerprint():
    b = _load(SRC)["executors"]
    assert len(b) == 8
    got = [(e["角色"], e["当前绑定"], e["命令"].rsplit("/", 1)[-1]) for e in b[:7]]
    assert got == _BASELINE7
