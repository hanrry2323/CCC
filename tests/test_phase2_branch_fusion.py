"""xy072 · phase2 `list_written_cards` 合并段 branch 补写判别测试（P2-fix-01 F1）。

判别测试先行（红→绿）：
1. 工作区卡 branch 空 + 同名分支信封 branch 有值 → 返回该卡 branch=信封值（修复目标态，改码前红）。
2. wrapper 型（两路皆无 branch）→ 行为不变（防误伤）。
3. main 已关闭/打回卡 → 分支信封不重捞（守 phase2.py 合并语义，不改码前后均绿）。

运行：`.venv-hub/bin/python -m pytest tests/test_phase2_branch_fusion.py -q`
"""

from __future__ import annotations

from types import SimpleNamespace

from server.engine import phase2

_CARD_REL = "docs/dispatch/xy/xy072-p2fix-merge.md"


class _FakeCP:
    def __init__(self, rc: int, stdout: str = "") -> None:
        self.returncode = rc
        self.stdout = stdout
        self.stderr = ""


def _workspace_item(card_id: str = "xy072", state: str = "已回写") -> SimpleNamespace:
    return SimpleNamespace(
        id=card_id, state=state, title="phase2 合入缺口修复（P2-fix-01 F1）", project="xy"
    )


def _envelope_card(card_id: str = "xy072", branch: str = "codex/xy072-p2fix-merge") -> dict:
    return {
        "id": card_id,
        "state": "已回写",
        "title": "phase2 合入缺口修复（P2-fix-01 F1）",
        "project": "xy",
        "path_rel": _CARD_REL,
        "path": str(phase2._repo_root() / _CARD_REL),
        "branch": branch,
        "worktree": "",
    }


def _run(monkeypatch, workspace_ids: list[str], envelope_cards: list[dict]) -> dict:
    """打桩两路扫描源后跑 list_written_cards，返回 {card_id: card}。"""
    monkeypatch.setattr(
        "server.board.loader.load_dispatch_cards",
        lambda directory, include_archived=False: [_workspace_item(wid) for wid in workspace_ids],
    )
    monkeypatch.setattr(
        "server.board.loader.load_index_file",
        lambda dispatch_dir=None: {wid: {"path": _CARD_REL} for wid in workspace_ids},
    )
    monkeypatch.setattr(phase2, "_worktree_for", lambda project, work_id: "")
    monkeypatch.setattr(phase2, "_list_branch_written_cards", lambda: list(envelope_cards))
    return {c["id"]: c for c in phase2.list_written_cards("docs/dispatch")}


def test_workspace_empty_branch_takes_envelope_branch(monkeypatch) -> None:
    """用例1：工作区卡 branch 空 + 分支信封 branch 有值 → branch=信封值（分支信封=事实源）。"""
    cards = _run(monkeypatch, ["xy072"], [_envelope_card()])

    assert cards["xy072"]["branch"] == "codex/xy072-p2fix-merge"


def test_wrapper_shape_both_empty_branch_unchanged(monkeypatch) -> None:
    """用例2：两路皆无 branch → 不拿无 branch 的信封覆盖工作区卡（防误伤），工作区独有卡不变。"""
    cards = _run(monkeypatch, ["xy072", "xy999"], [_envelope_card(branch="")])

    assert cards["xy072"]["branch"] == ""
    assert cards["xy072"]["path_rel"] == _CARD_REL
    assert cards["xy999"]["branch"] == ""


def test_branch_envelope_not_refetched_when_main_terminal(monkeypatch) -> None:
    """用例3：main 侧已关闭/打回 → 分支信封不重捞（守合并段「main 已消费」语义）。"""
    card_md = (
        "# 任务卡 xy072 · phase2 合入缺口修复（P2-fix-01 F1）\n"
        "> 关联：P2-fix-01 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine "
        "· 项目：xy · 日期：2026-09-13 · 版本：xy072 · 状态版本：1\n\n"
        "## 目标\nx\n"
    )

    for main_state in ("已关闭", "打回（CC 审核不通过）"):
        main_md = card_md.replace("状态：已回写", f"状态：{main_state}")

        def fake_git(cmd, cwd=None):  # noqa: A002
            if cmd[0] == "for-each-ref":
                return _FakeCP(0, "refs/remotes/origin/codex/xy072-p2fix-merge\n")
            if cmd[:3] == ["diff", "--name-only", "origin/main"]:
                return _FakeCP(0, f"{_CARD_REL}\n")
            if cmd[0] == "show" and cmd[1].startswith("origin/main:"):
                return _FakeCP(0, main_md)
            if cmd[0] == "show":
                return _FakeCP(0, card_md)
            return _FakeCP(1)

        monkeypatch.setattr(phase2, "git", fake_git)
        assert phase2._list_branch_written_cards() == []
