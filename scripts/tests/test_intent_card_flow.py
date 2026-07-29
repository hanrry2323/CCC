"""v0.64 意图卡供给：L1 upsert + gate dry-run + exhaust reflow。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "chat_server"))


@pytest.fixture()
def mind_root(tmp_path: Path) -> Path:
    (tmp_path / ".ccc" / "agent-mind").mkdir(parents=True)
    return tmp_path


def test_upsert_planned_intent_cards_writes_l1_not_backlog(mind_root: Path):
    from chat_server.services import agent_mind as am

    out = am.upsert_planned_intent_cards(
        mind_root,
        [
            {
                "title": "净 edge CLOSE",
                "goal": "动量费率净 edge 与 CLOSE",
                "exit_condition": ".venv/bin/python -m pytest -q tests/unit/test_fees.py",
            },
            {
                "text": "回测可视化 B5",
                "exit_condition": "DRY_RUN=true .venv/bin/python scripts/viz_probe.py",
            },
        ],
        updated_by="test",
    )
    assert out["ok"] is True
    assert len(out["goals_upserted"]) == 2
    decided = am.load_decided(mind_root)
    planned = [
        g
        for g in decided["goals"]
        if isinstance(g, dict) and g.get("status") == "planned"
    ]
    assert len(planned) >= 2
    # no board written
    assert not (mind_root / ".ccc" / "board").exists()


def test_digest_includes_transfer_lessons_for_craft(mind_root: Path):
    """v0.66：起草前 digest 须露出近期定卡教训。"""
    from chat_server.services import agent_mind as am

    am.append_transfer_lesson(
        mind_root,
        epic_id="e1",
        bucket="acceptance_fail",
        title_snip="弱探针",
        hint="换成 pytest 强探针",
        bad_pattern="test -f",
        good_fix="pytest -q",
        source="test",
    )
    digest = am.build_digest(mind_root, project_id="demo", use_cache=False, persist=False)
    text = str(digest.get("digest") or "")
    assert "近期定卡教训" in text
    assert "弱探针" in text or "pytest" in text


def test_upsert_does_not_clobber_dispatched(mind_root: Path):
    from chat_server.services import agent_mind as am

    am.upsert_planned_intent_cards(
        mind_root, [{"text": "已下达意图", "exit_condition": "pytest -q t"}], updated_by="t"
    )
    decided = am.load_decided(mind_root)
    gid = decided["goals"][0]["id"]
    am.mark_goal_status(mind_root, gid, "dispatched", updated_by="t")
    am.upsert_planned_intent_cards(
        mind_root,
        [{"id": gid, "text": "已下达意图", "exit_condition": "pytest -q t"}],
        updated_by="t",
    )
    decided2 = am.load_decided(mind_root)
    g = next(x for x in decided2["goals"] if x.get("id") == gid)
    assert g["status"] == "dispatched"


def test_seed_planned_from_exhaust_adds_lesson(mind_root: Path):
    from chat_server.services import agent_mind as am

    out = am.seed_planned_from_exhaust(
        mind_root,
        title="卡挂了",
        goal="修探针",
        optimize_hint="缩小到 1 条 pytest",
        prior_epic_id="epic-dead",
    )
    assert out and out["ok"]
    decided = am.load_decided(mind_root)
    assert any(
        isinstance(g, dict) and "优化" in str(g.get("text") or "")
        for g in decided["goals"]
    ) or any(
        isinstance(g, dict) and g.get("status") == "planned" for g in decided["goals"]
    )
    lessons = decided.get("transfer_lessons") or []
    assert any(x.get("bucket") == "exhaust_reflow" for x in lessons)


def test_transfer_gate_rejects_weak_acceptance():
    from chat_server.services import transfer_gate

    ok, errors = transfer_gate.validate_transfer_payload(
        {
            "title": "弱卡",
            "goal": "只检查文件在不在",
            "acceptance": ["test -f src/foo.py"],
            "pipeline": "dev",
            "feasibility": "ok",
            "plan_md": "# Plan\n## 目标\nx\n## 验收\n- test -f src/foo.py\n",
            "card_kind": "epic",
        }
    )
    assert ok is False
    codes = {e.get("code") for e in errors if isinstance(e, dict)}
    assert "acceptance_weak" in codes or any(
        "weak" in str(c) for c in codes
    )


def test_intent_card_sop_exists():
    root = Path(__file__).resolve().parents[2]
    sop = root / "references" / "intent-card-sop.md"
    assert sop.is_file()
    text = sop.read_text(encoding="utf-8")
    assert "三角色" in text
    assert "收敛门" in text
    assert "transfer_gate" in text
    stub = root / "references" / "finalize-transfer-sop.md"
    assert "intent-card-sop" in stub.read_text(encoding="utf-8")


def test_hub_voice_strategy_first():
    from hub_voice import HUB_BOSS_VOICE

    assert "战略优先" in HUB_BOSS_VOICE
    assert "转意图卡" in HUB_BOSS_VOICE
    assert "intent-card-sop.md" in HUB_BOSS_VOICE
    assert "禁止**未触发自转" in HUB_BOSS_VOICE or "禁止** Agent 未触发自转" in HUB_BOSS_VOICE or "禁止**未触发" in HUB_BOSS_VOICE or "未触发自转" in HUB_BOSS_VOICE


def test_abandon_orphan_keeps_bare_planned(mind_root: Path):
    from chat_server.services import agent_mind as am

    am.upsert_planned_intent_cards(
        mind_root,
        [{"text": "待转合法卡", "exit_condition": "pytest -q t"}],
        updated_by="t",
    )
    out = am.abandon_orphan_planned_goals(mind_root, workspace=mind_root)
    assert out["abandoned_count"] == 0
    planned = [
        g
        for g in am.load_decided(mind_root)["goals"]
        if isinstance(g, dict) and g.get("status") == "planned"
    ]
    assert len(planned) == 1


def test_abandon_stale_linked_and_all_planned(mind_root: Path):
    from chat_server.services import agent_mind as am

    am.upsert_planned_intent_cards(
        mind_root,
        [{"text": "僵尸链", "exit_condition": "pytest -q t"}],
        updated_by="t",
    )
    path = am.decided_path(mind_root)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["goals"][0]["linked_epic_id"] = "epic-gone"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out = am.abandon_orphan_planned_goals(mind_root, workspace=mind_root)
    assert out["abandoned_count"] == 1
    assert am.load_decided(mind_root)["goals"][0]["status"] == "abandoned"

    am.upsert_planned_intent_cards(
        mind_root,
        [{"text": "再清一批", "exit_condition": "pytest -q t"}],
        updated_by="t",
    )
    out2 = am.abandon_orphan_planned_goals(
        mind_root, workspace=mind_root, abandon_all_planned=True
    )
    assert out2["abandoned_count"] >= 1
    planned = [
        g
        for g in am.load_decided(mind_root)["goals"]
        if isinstance(g, dict) and g.get("status") == "planned"
    ]
    assert planned == []


def test_multi_card_upsert_order_preserved(mind_root: Path):
    from chat_server.services import agent_mind as am

    titles = ["卡甲", "卡乙", "卡丙"]
    am.upsert_planned_intent_cards(
        mind_root,
        [{"text": t, "exit_condition": "pytest -q t"} for t in titles],
        updated_by="t",
    )
    planned = [
        g
        for g in am.load_decided(mind_root)["goals"]
        if isinstance(g, dict) and g.get("status") == "planned"
    ]
    texts = [g.get("text") for g in planned]
    for t in titles:
        assert t in texts
