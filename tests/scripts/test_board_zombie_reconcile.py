"""test_board_zombie_reconcile.py — 看板 zombie 副本清理回归测试 (v0.24-p5)

覆盖:
  - _board_store.FileBoardStore.move_task 原子性：dst 已存在时不双份
  - board-reconcile 多副本 task：保留 status 匹配的副本、删 zombie
  - board-reconcile status 字段不一致：修正为目录列
  - board-reconcile 干净状态下零改动
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import shutil
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _board_store import FileBoardStore  # noqa: E402

# 加载 board-reconcile.py 作为独立模块
_spec = importlib.util.spec_from_file_location(
    "board_reconcile", str(SCRIPTS / "board-reconcile.py")
)
board_reconcile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(board_reconcile)
reconcile = board_reconcile.reconcile


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """建一个临时 workspace，FileBoardStore 接 workspace（不是 board 目录）"""
    board = tmp_path / ".ccc" / "board"
    board.mkdir(parents=True)
    (board / "events").mkdir()
    return tmp_path


@pytest.fixture
def tmp_board(tmp_workspace: Path) -> Path:
    """board 目录快捷访问"""
    return tmp_workspace / ".ccc" / "board"


def _write_task(board: Path, col: str, tid: str, status: str = None) -> Path:
    """在指定列写一个 task jsonl"""
    col_dir = board / col
    col_dir.mkdir(parents=True, exist_ok=True)
    p = col_dir / f"{tid}.jsonl"
    obj = {
        "id": tid,
        "title": f"task {tid}",
        "description": "test",
        "status": status or col,
        "created_at": "2026-07-11T00:00:00Z",
        "updated_at": "2026-07-11T00:00:00Z",
        "assignee": None,
        "tags": [],
    }
    p.write_text(json.dumps(obj, ensure_ascii=False) + "\n")
    return p


# --- move_task 原子性 ---

def test_move_task_atomic_dst_preexists(tmp_board: Path, tmp_workspace: Path):
    """move_task: dst 已存在时不应双份存在（合法路径：planned → in_progress）"""
    store = FileBoardStore(tmp_workspace)
    _write_task(tmp_board, "planned", "t1")
    _write_task(tmp_board, "in_progress", "t1")  # 模拟僵尸 dst

    assert (tmp_board / "planned" / "t1.jsonl").exists()
    assert (tmp_board / "in_progress" / "t1.jsonl").exists()

    ok = store.move_task("t1", "planned", "in_progress")
    assert ok is True

    # src 必须消失
    assert not (tmp_board / "planned" / "t1.jsonl").exists(), "src 列残留"
    # dst 必须只剩一份
    assert (tmp_board / "in_progress" / "t1.jsonl").exists()
    # 检查没有第二份
    copies = list((tmp_board / "in_progress").glob("t1.jsonl"))
    assert len(copies) == 1


def test_move_task_updates_status_field(tmp_board: Path, tmp_workspace: Path):
    """move_task: status 字段必须同步更新到 to_col"""
    store = FileBoardStore(tmp_workspace)
    _write_task(tmp_board, "planned", "t2", status="planned")
    store.move_task("t2", "planned", "in_progress")

    obj = json.loads((tmp_board / "in_progress" / "t2.jsonl").read_text().strip())
    assert obj["status"] == "in_progress"


# --- reconcile ---

def test_reconcile_clean_state(tmp_board: Path):
    """干净状态：0 zombie / 0 mismatch → 零改动"""
    _write_task(tmp_board, "backlog", "t3")
    _write_task(tmp_board, "released", "t4")

    moved = reconcile(tmp_board, dry_run=True)
    # dry_run 返回 zombie+mismatch 数量；干净状态下应为 0
    # 注意 reconcile 返回值在干净时是 0
    assert moved == 0


def test_reconcile_deletes_zombie_keeps_canonical(tmp_board: Path):
    """多副本 task：保留 status 匹配目录的那一份，删其它"""
    # t5 在 backlog 和 released 都存在；backlog 副本 status=backlog（合法），released 副本 status=backlog（zombie）
    _write_task(tmp_board, "backlog", "t5", status="backlog")
    _write_task(tmp_board, "released", "t5", status="backlog")  # zombie

    moved = reconcile(tmp_board, dry_run=False)

    assert (tmp_board / "backlog" / "t5.jsonl").exists()
    assert not (tmp_board / "released" / "t5.jsonl").exists(), "zombie 没删"


def test_reconcile_canonical_when_no_status_match(tmp_board: Path):
    """多副本且 status 都不匹配时：取最大 rank 列（released > ... > backlog）"""
    # 两个 status 都错
    _write_task(tmp_board, "backlog", "t6", status="testing")
    _write_task(tmp_board, "released", "t6", status="testing")
    # 没任何副本 status 自报 backlog/released

    moved = reconcile(tmp_board, dry_run=False)

    # released 优先保留
    assert (tmp_board / "released" / "t6.jsonl").exists()
    assert not (tmp_board / "backlog" / "t6.jsonl").exists()


def test_reconcile_fixes_status_mismatch(tmp_board: Path):
    """status 字段与目录不一致时：修正 status 为目录名"""
    # 物理在 backlog，但 status 字段是 released（历史 bug）
    _write_task(tmp_board, "backlog", "t7", status="released")

    moved = reconcile(tmp_board, dry_run=False)

    obj = json.loads((tmp_board / "backlog" / "t7.jsonl").read_text().strip())
    assert obj["status"] == "backlog"
    # 文件位置不变
    assert (tmp_board / "backlog" / "t7.jsonl").exists()


def test_reconcile_dry_run_no_changes(tmp_board: Path):
    """dry_run 模式不改文件"""
    _write_task(tmp_board, "backlog", "t8", status="released")
    _write_task(tmp_board, "released", "t8", status="backlog")

    before_backlog = (tmp_board / "backlog" / "t8.jsonl").read_text()
    before_released = (tmp_board / "released" / "t8.jsonl").read_text()

    moved = reconcile(tmp_board, dry_run=True)
    assert moved > 0  # 检测出问题

    # 文件未变
    assert (tmp_board / "backlog" / "t8.jsonl").read_text() == before_backlog
    assert (tmp_board / "released" / "t8.jsonl").read_text() == before_released


# --- H2: reconcile 使用原子写入 ---

def test_reconcile_uses_atomic_write(tmp_board: Path, monkeypatch):
    """H2: fix_status_field 必须走 _atomic_write，不直接 write_text"""
    _write_task(tmp_board, "backlog", "atomic-test", status="released")

    # monkeypatch board_reconcile._atomic_write，记录调用
    captured_calls = []
    original_atomic = board_reconcile._atomic_write

    def mock_atomic(path: Path, content: str):
        captured_calls.append((path, content))
        original_atomic(path, content)

    monkeypatch.setattr(board_reconcile, "_atomic_write", mock_atomic)

    reconcile(tmp_board, dry_run=False)

    assert len(captured_calls) >= 1, "fix_status_field 应调用 _atomic_write"
    assert captured_calls[0][0] == tmp_board / "backlog" / "atomic-test.jsonl"


# --- M10: schema_version 元数据行不被污染 ---

def test_reconcile_skips_schema_metadata_lines(tmp_board: Path, monkeypatch):
    """M10: schema_version 元数据行不应被加上 status 字段"""
    col_dir = tmp_board / "backlog"
    col_dir.mkdir(parents=True, exist_ok=True)
    target = col_dir / "meta-test.jsonl"

    # 元数据行 + 任务行（status 错误）
    target.write_text(
        '{"schema_version": "1.0"}\n'
        + json.dumps({
            "id": "meta-test",
            "title": "x",
            "description": "x",
            "status": "released",   # 故意错误
            "created_at": "2026-07-11T00:00:00Z",
            "updated_at": "2026-07-11T00:00:00Z",
        }, ensure_ascii=False)
        + "\n"
    )

    reconcile(tmp_board, dry_run=False)

    lines = target.read_text().strip().split("\n")
    meta = json.loads(lines[0])
    task = json.loads(lines[1])

    # 元数据行不应被添加 status 字段
    assert "status" not in meta
    assert meta.get("schema_version") == "1.0"

    # 任务行 status 应被修正
    assert task["status"] == "backlog"