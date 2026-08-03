"""test_audit_role.py — audit_role 关键路径回归测试 (v0.22 C3)

覆盖:
  - _audit_should_run 边界（文件不存在 / 损坏 JSON / 时间窗刚好 2h）
  - _audit_post_backlog 写 backlog 的 column 正确性
  - audit_role 整体：单 workspace 模式 + 无 git 目录的跳过逻辑
  - _auto_replenish_backlog：backlog+planned 为空时立即触发 audit_role（v0.29）
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time as _time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


# ccc-board.py 含连字符，从 scripts/ 目录加载（脚本里的内部 import 才能解析 _config / _board_store）
import os as _os

_os.chdir(str(SCRIPTS))
_spec = importlib.util.spec_from_file_location(
    "ccc_board", str(SCRIPTS / "ccc-board.py")
)
ccc_board = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ccc_board)
_audit_post_backlog = ccc_board._audit_post_backlog
_audit_classify = ccc_board._audit_classify
_audit_recent_commits = ccc_board._audit_recent_commits

# _audit_should_run 在 ccc-engine.py（同名加载）
_spec2 = importlib.util.spec_from_file_location(
    "ccc_engine", str(SCRIPTS / "ccc-engine.py")
)
ccc_engine = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(ccc_engine)
_audit_should_run = ccc_engine._audit_should_run
_auto_replenish_backlog = ccc_engine._auto_replenish_backlog
_last_empty_replenish = ccc_engine._last_empty_replenish


# ═══════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════


@pytest.fixture
def tmp_workspace(tmp_path):
    """一个最小化的假 workspace：含 .git/、.ccc/board/"""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".git").mkdir()
    (ws / ".ccc" / "board").mkdir(parents=True)
    for col in (
        "backlog",
        "planned",
        "released",
        "abnormal",
        "in_progress",
        "testing",
        "verified",
        "events",
    ):
        (ws / ".ccc" / "board" / col).mkdir()
    (ws / ".ccc" / "board" / "index.json").write_text(
        '{"backlog":0,"planned":0,"in_progress":0,"testing":0,"verified":0,"released":0,"abnormal":0}'
    )
    return ws


@pytest.fixture
def empty_last_run(tmp_path, monkeypatch):
    """强制 _audit_should_run 返回 True（删除 last-run 文件）"""
    last_run = Path.home() / ".ccc" / "audit-last-run.json"
    if last_run.exists():
        last_run.unlink()
    yield
    if last_run.exists():
        last_run.unlink()


# ═══════════════════════════════════════════
# _audit_should_run 测试
# ═══════════════════════════════════════════


def test_should_run_when_no_file(tmp_path, monkeypatch):
    """无 audit-last-run.json → 应该跑（首次）"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert _audit_should_run("test") is True


def test_should_run_when_corrupt_json(tmp_path, monkeypatch):
    """损坏 JSON → 应该跑（fail-safe）"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    f = tmp_path / ".ccc" / "audit-last-run.test.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("{not json")
    assert _audit_should_run("test") is True


def test_should_run_when_over_2h(tmp_path, monkeypatch):
    """距上次跑 > 2h → 应该跑"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    f = tmp_path / ".ccc" / "audit-last-run.test.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    f.write_text(json.dumps({"last_run": old}))
    assert _audit_should_run("test") is True


def test_should_not_run_within_2h(tmp_path, monkeypatch):
    """距上次跑 1h → 不应该跑（红线 X8）"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    f = tmp_path / ".ccc" / "audit-last-run.test.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    f.write_text(json.dumps({"last_run": recent}))
    assert _audit_should_run("test", interval_hours=2) is False


# ═══════════════════════════════════════════
# _audit_post_backlog 测试
# ═══════════════════════════════════════════


def test_post_backlog_hard_disabled_by_default(tmp_workspace):
    """v0.42.4: 自动投入硬禁 → 不写 backlog。"""
    items = ["bug 1 in module X", "bug 2 in module Y", "bug 3 in module Z"]
    n = _audit_post_backlog(str(tmp_workspace), items, "review")
    assert n == 0
    backlog = tmp_workspace / ".ccc" / "board" / "backlog"
    assert list(backlog.glob("*.jsonl")) == []


def test_post_backlog_creates_tasks_when_inject_allowed(tmp_workspace, monkeypatch):
    """投 3 个 review 类 → backlog 出现 3 个 JSONL（仅测试注入路径时临时开闸）。"""
    import _ccc_control as ctrl

    monkeypatch.setattr(ctrl, "INVENT_HARD_DISABLED", False)
    monkeypatch.setattr(ctrl, "may_invent", lambda: True)
    monkeypatch.setattr(ctrl, "may_auto_inject_tasks", lambda: True)
    items = ["bug 1 in module X", "bug 2 in module Y", "bug 3 in module Z"]
    n = _audit_post_backlog(str(tmp_workspace), items, "review")
    assert n == 3

    backlog = tmp_workspace / ".ccc" / "board" / "backlog"
    files = list(backlog.glob("*.jsonl"))
    assert len(files) == 3

    # 校验 task_id 格式: audit-review-YYYYMMDD-HHMM-<uuid8>
    for f in files:
        tid = json.loads(f.read_text())["id"]
        assert tid.startswith("audit-review-")
        # uuid 部分：8 个 hex 字符
        suffix = tid.split("-")[-1]
        assert len(suffix) == 8
        assert all(c in "0123456789abcdef" for c in suffix)


def test_post_backlog_empty_returns_zero(tmp_workspace):
    """空列表 → 返回 0，backlog 不动"""
    assert _audit_post_backlog(str(tmp_workspace), [], "review") == 0
    backlog = tmp_workspace / ".ccc" / "board" / "backlog"
    assert len(list(backlog.glob("*.jsonl"))) == 0


# ═══════════════════════════════════════════
# _audit_recent_commits / _audit_classify 测试
# ═══════════════════════════════════════════


def test_recent_commits_no_git(tmp_path):
    """无 .git → 返回空字符串（不抛错）"""
    no_git = tmp_path / "no_git"
    no_git.mkdir()
    out = _audit_recent_commits(str(no_git))
    assert out == ""


def test_classify_separates_lint_and_mypy():
    """lint warning → auto，mypy error → review"""
    lint_out = "F401 unused import"
    mypy_out = "file.py:5: error: Name 'x' is not defined"
    findings = _audit_classify("/any", "fake commit log", lint_out, mypy_out)

    # lint 列入 auto（无 "error" 字符串）
    assert any("lint" in x for x in findings["auto"])
    # mypy error 列入 review
    assert any("type" in x for x in findings["review"])


def test_classify_empty_inputs():
    """全空输入 → 全空 findings"""
    findings = _audit_classify("/any", "", "", "")
    assert findings == {"auto": [], "review": [], "decision": []}


# ═══════════════════════════════════════════
# FileBoardStore 兜底 (N1)
# ═══════════════════════════════════════════


def test_post_backlog_on_bare_workspace_refused(tmp_path, monkeypatch):
    """裸 workspace：硬禁下不投 backlog（且不抛错）。"""
    bare_ws = tmp_path / "bare"
    bare_ws.mkdir()
    assert not (bare_ws / ".ccc" / "board").exists()
    n = _audit_post_backlog(str(bare_ws), ["item 1", "item 2"], "review")
    assert n == 0


def test_post_backlog_on_bare_workspace_when_allowed(tmp_path, monkeypatch):
    """开闸后裸 workspace → FileBoardStore 自动建目录并投卡。"""
    import _ccc_control as ctrl

    monkeypatch.setattr(ctrl, "may_invent", lambda: True)
    monkeypatch.setattr(ctrl, "may_auto_inject_tasks", lambda: True)
    bare_ws = tmp_path / "bare"
    bare_ws.mkdir()
    n = _audit_post_backlog(str(bare_ws), ["item 1", "item 2"], "review")
    assert n == 2
    assert (bare_ws / ".ccc" / "board" / "backlog").exists()
    assert len(list((bare_ws / ".ccc" / "board" / "backlog").glob("*.jsonl"))) == 2


# ═══════════════════════════════════════════════════════════════
# _auto_replenish_backlog 测试（plan: backlog-auto-replenish, v0.29）
# ═══════════════════════════════════════════════════════════════


class _FakeStore:
    """极简 store 替身：list_tasks 返回可控结果。"""

    def __init__(self, backlog=None, planned=None):
        self._backlog = backlog if backlog is not None else []
        self._planned = planned if planned is not None else []

    def list_tasks(self, column: str):
        if column == "backlog":
            return self._backlog
        if column == "planned":
            return self._planned
        return []


@pytest.fixture
def reset_replenish_state():
    """每个 case 前清空 _last_empty_replenish，避免跨 case 干扰。"""
    _last_empty_replenish.clear()
    yield
    _last_empty_replenish.clear()


def test_replenish_hard_disabled(
    tmp_workspace, reset_replenish_state, monkeypatch
):
    """v0.42.4: auto_replenish 永久禁用，即使 cfg/invent 打开也不触发。"""
    ccc_engine.cfg.auto_replenish = True
    called = []

    def fake_audit_role(workspace=None):
        called.append(workspace)
        return []

    monkeypatch.setattr(ccc_engine.ccc_board, "audit_role", fake_audit_role)
    monkeypatch.setattr(ccc_engine, "_may_invent", lambda: True)

    store = _FakeStore(backlog=[], planned=[])
    program_dir = tmp_workspace.parent

    triggered = _auto_replenish_backlog(tmp_workspace, store, program_dir)

    assert triggered is False
    assert called == []


def test_replenish_skips_when_backlog_has_items(
    tmp_workspace, reset_replenish_state, monkeypatch
):
    """backlog 不为空 → 不调用 audit_role"""
    called = []

    def fake_audit_role(workspace=None):
        called.append(workspace)
        return []

    monkeypatch.setattr(ccc_engine.ccc_board, "audit_role", fake_audit_role)

    store = _FakeStore(backlog=[{"id": "existing"}], planned=[])
    program_dir = tmp_workspace.parent

    triggered = _auto_replenish_backlog(tmp_workspace, store, program_dir)

    assert triggered is False
    assert called == []


def test_replenish_skips_when_planned_has_items(
    tmp_workspace, reset_replenish_state, monkeypatch
):
    """planned 不为空 → 不调用 audit_role"""
    called = []

    def fake_audit_role(workspace=None):
        called.append(workspace)
        return []

    monkeypatch.setattr(ccc_engine.ccc_board, "audit_role", fake_audit_role)

    store = _FakeStore(backlog=[], planned=[{"id": "planned-1"}])
    program_dir = tmp_workspace.parent

    triggered = _auto_replenish_backlog(tmp_workspace, store, program_dir)

    assert triggered is False
    assert called == []


def test_replenish_cooldown_irrelevant_when_hard_disabled(
    tmp_workspace, reset_replenish_state, monkeypatch
):
    """硬禁后多次调用均不触发。"""
    called = []

    def fake_audit_role(workspace=None):
        called.append(workspace)
        return []

    monkeypatch.setattr(ccc_engine.ccc_board, "audit_role", fake_audit_role)
    ccc_engine.cfg.auto_replenish = True
    monkeypatch.setattr(ccc_engine, "_may_invent", lambda: True)

    store = _FakeStore(backlog=[], planned=[])
    program_dir = tmp_workspace.parent

    first = _auto_replenish_backlog(tmp_workspace, store, program_dir)
    second = _auto_replenish_backlog(tmp_workspace, store, program_dir)
    assert first is False
    assert second is False
    assert called == []
