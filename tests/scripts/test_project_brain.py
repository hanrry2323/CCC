"""project_brain — qb 样板六层认领编译。"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "chat_server"))


def test_compile_brain_qb_shaped(tmp_path: Path):
    from chat_server.services import agent_mind, project_brain

    (tmp_path / "CLAUDE.md").write_text(
        "# Demo\n\n## 项目脑索引（CCC）\n\n"
        "| 层 | 路径 |\n|----|------|\n"
        "| 规划 / 未来待办 | docs/DEV_PLAN_v1.1.md |\n"
        "| 当前产品意图 | .ccc/agent-mind/decided.json |\n"
        "| 开发过程 | .ccc/board/ |\n\n铁律：DRY_RUN\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DEV_PLAN_v1.1.md").write_text(
        "# Plan\n\n| VIP | 单机 |\n| P1 | alpha |\n",
        encoding="utf-8",
    )
    (tmp_path / ".ccc").mkdir()
    (tmp_path / ".ccc" / "profile.md").write_text(
        "# profile\n权威 apps/demo\n", encoding="utf-8"
    )
    agent_mind.merge_decided(
        tmp_path,
        {
            "goals": [
                {
                    "text": "VIP paper probe",
                    "exit_condition": "DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py",
                    "status": "planned",
                }
            ],
            "constraints": ["禁止第二树"],
        },
    )
    out = project_brain.compile_brain(tmp_path, project_id="demo")
    assert out["ok"] is True
    assert "项目脑包" in out["brain"]
    assert "DEV_PLAN_v1.1.md" in out["brain"]
    assert out["brain_meta"]["plan_path"] == "docs/DEV_PLAN_v1.1.md"
    assert "VIP paper probe" in out["brain"]
    assert "TODO.md" not in out["brain"] or "禁止" in out["brain"]


def test_build_digest_includes_brain(tmp_path: Path):
    from chat_server.services import agent_mind

    (tmp_path / "CLAUDE.md").write_text("# X\n定位测试\n", encoding="utf-8")
    (tmp_path / ".ccc").mkdir()
    agent_mind.clear_digest_cache()
    dig = agent_mind.build_digest(tmp_path, project_id="x", use_cache=False)
    assert dig.get("brain")
    assert "定位测试" in dig["brain"]
    assert "inject" in dig
    assert dig["inject"].startswith(dig["digest"].rstrip()[:20]) or "项目脑包" in dig["inject"]


def test_ccc_skips_business_brain(tmp_path: Path):
    from chat_server.services import agent_mind

    (tmp_path / "CLAUDE.md").write_text("# CCC orch\n", encoding="utf-8")
    (tmp_path / ".ccc").mkdir()
    dig = agent_mind.build_digest(tmp_path, project_id="ccc", use_cache=False)
    assert dig.get("brain") == ""
