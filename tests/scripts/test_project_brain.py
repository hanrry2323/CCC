"""project_brain — qb 样板六层认领编译。"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
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
        "# Plan\n\n## VIP 纸面\n\n| VIP | 单机 |\n\n"
        "## alpha 其它\n\n无关段落 filler " + ("x" * 800) + "\n\n"
        "## momentum 口径\n\nCLOSE 与净 edge；shared cost。\n",
        encoding="utf-8",
    )
    (tmp_path / ".ccc").mkdir()
    (tmp_path / ".ccc" / "profile.md").write_text(
        "# profile\n权威 apps/demo\n", encoding="utf-8"
    )
    (tmp_path / "src" / "strategies").mkdir(parents=True)
    (tmp_path / "src" / "strategies" / "momentum.py").write_text(
        "class Momentum:\n    pass\n", encoding="utf-8"
    )
    agent_mind.merge_decided(
        tmp_path,
        {
            "goals": [
                {
                    "text": "momentum 口径对齐 CLOSE 净 edge",
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
    assert "momentum" in out["brain"].lower()
    assert "momentum 口径" in out["brain"] or "CLOSE" in out["brain"]
    assert out["brain_meta"].get("plan_index")
    assert any("momentum" in t.lower() for t in out["brain_meta"]["plan_index"])
    assert "模块目录" in out["brain"]
    assert "momentum" in (out["brain_meta"].get("modules_line") or "")
    assert "TODO.md" not in out["brain"] or "禁止" in out["brain"]


def test_read_plan_smart_prefers_goal_section(tmp_path: Path):
    from chat_server.services import project_brain

    plan = tmp_path / "DEV_PLAN.md"
    plan.write_text(
        "# Plan\n\n## 无关开头\n\n" + ("filler\n" * 200) + "\n"
        "## momentum 费用\n\nshared round_trip_cost 与净 edge。\n\n"
        "## 其它尾巴\n\n" + ("z\n" * 100),
        encoding="utf-8",
    )
    text, index = project_brain.read_plan_smart(
        plan, cap=400, keywords=["momentum", "edge", "cost"]
    )
    assert "momentum 费用" in text
    assert "净 edge" in text or "round_trip" in text
    assert any("momentum" in t.lower() for t in index)
    # Should not be dominated by only the head filler
    assert text.count("filler") < 50


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
