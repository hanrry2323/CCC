"""Gate rule fitness: card-kind review, prose ban, hollow path-aware."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture()
def ws_git(tmp_path: Path):
    ws = tmp_path / "app"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=ws, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=ws, check=True, capture_output=True
    )
    (ws / ".ccc" / "board" / "testing").mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "verdicts").mkdir(parents=True)
    (ws / "scripts").mkdir()
    return ws


def test_acceptance_prose_forbidden_for_business(ws_git: Path):
    from _acceptance_gate import check_acceptance

    tid = "biz-w1"
    (ws_git / ".ccc" / "board" / "testing" / f"{tid}.jsonl").write_text(
        json.dumps(
            {
                "id": tid,
                "title": "feature",
                "pipeline": "dev",
                "card_kind": "work",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- 写好说明文档即可\n", encoding="utf-8"
    )
    (ws_git / "scripts" / "x.py").write_text("x=1\n", encoding="utf-8")
    subprocess.run(["git", "add", "scripts/x.py"], cwd=ws_git, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"feat({tid}): x"],
        cwd=ws_git,
        check=True,
        capture_output=True,
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ws_git, text=True
    ).strip()
    r = check_acceptance(ws_git, tid, commit=head)
    assert r["ok"] is False
    assert r["reason"] == "acceptance_prose_forbidden_for_business"


def test_acceptance_prose_ok_for_ops(ws_git: Path):
    from _acceptance_gate import check_acceptance

    tid = "ops-w1"
    (ws_git / ".ccc" / "board" / "testing" / f"{tid}.jsonl").write_text(
        json.dumps(
            {
                "id": tid,
                "title": "看板卫生",
                "pipeline": "ops",
                "card_kind": "work",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- 板面干净即可\n", encoding="utf-8"
    )
    (ws_git / "scripts" / "y.py").write_text("y=1\n", encoding="utf-8")
    subprocess.run(["git", "add", "scripts/y.py"], cwd=ws_git, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore({tid}): y"],
        cwd=ws_git,
        check=True,
        capture_output=True,
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ws_git, text=True
    ).strip()
    r = check_acceptance(ws_git, tid, commit=head)
    assert r["ok"] is True
    assert r["reason"] == "acceptance_prose_with_commit"


def test_hollow_skips_script_seed_path():
    from _opencode_quality_gate import detect_hollow_opencode_run

    raw = (
        '{"path":"script_seed","ok":true,'
        '"stdout":"permission requested: external_directory; auto-rejecting"}'
    )
    assert detect_hollow_opencode_run(raw, path="script_seed") is None
    assert detect_hollow_opencode_run(raw) is None  # path in JSON


def test_hollow_prefers_stdout_not_stale_report():
    from _opencode_quality_gate import detect_hollow_opencode_run

    result = '{"exit_code":0,"stdout":"wrote docs/NOTE.md\\n"}'
    stale = (
        "permission requested: external_directory (/Users/fan/.ccc/*); "
        "auto-rejecting\nALL SELF-CHECKS PASSED\n"
    )
    # clean current stdout → should not inherit stale report hollow
    assert detect_hollow_opencode_run(result, stale) is None


def test_detect_review_kind_script_seed(ws_git: Path, monkeypatch):
    from board.context import set_workspace
    from board.roles import reviewer as rev

    set_workspace(ws_git)
    tid = "seed-w1"
    (ws_git / ".ccc" / "reports" / f"{tid}.result.json").write_text(
        json.dumps({"path": "script_seed", "ok": True}) + "\n",
        encoding="utf-8",
    )
    task = {"id": tid, "title": "paper", "executor": "python"}
    kind = rev._detect_review_kind(ws_git, task, "", "")
    assert kind == "script_seed"


def test_detect_review_kind_util_probe_open_intent(ws_git: Path):
    """Open-intent single-file probe → util_probe even with complexity=medium."""
    from board.context import set_workspace
    from board.roles import reviewer as rev

    set_workspace(ws_git)
    tid = "open-intent-r8-w1"
    (ws_git / ".ccc" / "phases").mkdir(parents=True, exist_ok=True)
    (ws_git / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        json.dumps(
            {
                "phase": 1,
                "scope": [
                    "scripts/ccc_open_intent_r8_probe.py",
                    "tests/test_ccc_open_intent_r8_probe.py",
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "# Plan\n\n## 验收\n"
        "- python3 -m py_compile scripts/ccc_open_intent_r8_probe.py\n"
        "- python3 -c \"from scripts.ccc_open_intent_r8_probe import open_intent_r8_ok; "
        "assert open_intent_r8_ok()=='CCC_OPEN_INTENT_R8_OK v0.63'\"\n"
        "- python3 -m pytest -q tests/test_ccc_open_intent_r8_probe.py\n",
        encoding="utf-8",
    )
    task = {
        "id": tid,
        "title": "CCC open-intent 闭环探针 R8",
        "complexity": "medium",
        "executor": "opencode",
    }
    kind = rev._detect_review_kind(ws_git, task, "", "")
    assert kind == "util_probe"


def test_transfer_open_intent_forces_python_and_small():
    from chat_server.services.transfer_gate import (
        resolve_complexity,
        resolve_executor_intent,
    )

    body = {
        "title": "CCC open-intent 闭环探针 R8",
        "goal": "新建 scripts/ccc_open_intent_r8_probe.py",
        "acceptance": [
            "python3 -m py_compile scripts/ccc_open_intent_r8_probe.py",
            "python3 -c \"assert True\"",
            "python3 -m pytest -q tests/test_ccc_open_intent_r8_probe.py",
        ],
        "executor_intent": "opencode",
        "skill_ref": "skills/script-seed",
        "prompt_ref": "prompts/write-code-prompt",
        "complexity": "medium",
        "pipeline": "dev",
    }
    # open-intent 机械探针 → skills/script-seed → 执行器 python（禁 opencode hang）
    assert resolve_executor_intent(body) == "python"
    assert resolve_complexity(body) == "small"


def test_resolve_executor_from_skill_maps_library():
    """skill.md「默认执行器」为标题+下一行值格式；解析不得退回 opencode。

    回归：resolve_executor_from_skill 此前只认「同行冒号/竖线」，对库内
    ``## 默认执行器\\n\\npython`` 格式返回空 → 探针卡被误判 opencode 易 hang。
    """
    from chat_server.services.transfer_gate import resolve_executor_from_skill

    assert resolve_executor_from_skill("skills/script-seed") == "python"
    assert resolve_executor_from_skill("skills/ops") == "cli"
    assert resolve_executor_from_skill("skills/write-code") == "opencode"
    assert resolve_executor_from_skill("skills/bug-fix") == "opencode"
    # 缺失/空 → 兜底 opencode（不抛）
    assert resolve_executor_from_skill("skills/not-exist") == "opencode"
    assert resolve_executor_from_skill("") == "opencode"


def test_epic_default_executor_from_skill_tag():
    """fanout 从 epic skill tag 推断执行器；不得因 NameError 静默退回 opencode。

    回归：_product_fanout 未 import sys，_epic_default_executor 里
    sys.path.insert 抛 NameError → except 吞掉 → 恒返回 opencode，
    script-seed 声明失效（探针卡仍 opencode 易 hang）。
    """
    from _product_fanout import _epic_default_executor

    assert (
        _epic_default_executor(
            {"id": "e1", "tags": ["skill:skills/script-seed"], "note": None}
        )
        == "python"
    )
    assert (
        _epic_default_executor(
            {"id": "e2", "tags": ["skill:skills/ops"], "note": None}
        )
        == "cli"
    )
    # 无 skill 信息 → 兜底 opencode（不抛）
    assert (
        _epic_default_executor({"id": "e3", "tags": [], "note": None}) == "opencode"
    )


def test_tester_requires_pass_verdict(ws_git: Path):
    from board.roles.tester import _tester_verdict_allows_verified
    from board.context import set_workspace

    set_workspace(ws_git)
    tid = "t1"
    assert _tester_verdict_allows_verified(tid) is False
    (ws_git / ".ccc" / "verdicts" / f"{tid}.verdict.md").write_text(
        "# t\n\n**Verdict:** FAIL\n", encoding="utf-8"
    )
    assert _tester_verdict_allows_verified(tid) is False
    (ws_git / ".ccc" / "verdicts" / f"{tid}.verdict.md").write_text(
        "# t\n\n**Verdict:** PASS\n", encoding="utf-8"
    )
    assert _tester_verdict_allows_verified(tid) is True
