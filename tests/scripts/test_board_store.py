"""test_board_store.py — _board_store.py 原子写/锁/move/CRUD 补测"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import _board_store as bs
from _board_store import (
    COLUMNS,
    FileBoardStore,
    _acquire_lock,
    _atomic_write,
    _release_lock,
    assign_color_group,
    fill_task_defaults,
    now_iso,
    sanitize_id,
    validate_task_jsonl,
)


def _valid_task(
    task_id: str = "store-t1",
    status: str = "backlog",
    *,
    card_kind: str | None = None,
) -> dict:
    """backlog 默认 epic；流列（planned/…）默认 work（对齐 epic-only backlog 门禁）。"""
    ts = now_iso()
    if card_kind is None:
        card_kind = "epic" if status == "backlog" else "work"
    return {
        "id": task_id,
        "title": "Board store test",
        "description": "",
        "status": status,
        "created_at": ts,
        "updated_at": ts,
        "assignee": None,
        "tags": [],
        "card_kind": card_kind,
    }


@pytest.fixture
def store(tmp_path: Path) -> FileBoardStore:
    board = tmp_path / ".ccc" / "board"
    board.mkdir(parents=True)
    for col in COLUMNS:
        (board / col).mkdir(parents=True, exist_ok=True)
    (board / "events").mkdir(parents=True, exist_ok=True)
    return FileBoardStore(tmp_path)


class TestAtomicWrite:
    def test_replace_is_atomic_on_disk(self, tmp_path):
        target = tmp_path / "data.jsonl"
        _atomic_write(target, '{"a":1}\n')
        assert target.read_text() == '{"a":1}\n'
        _atomic_write(target, '{"b":2}\n')
        assert json.loads(target.read_text())["b"] == 2

    def test_no_partial_file_on_failure(self, tmp_path):
        target = tmp_path / "out.jsonl"
        with patch("os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                _atomic_write(target, "x")
        assert not any(p.name.startswith(".tmp_") for p in tmp_path.iterdir())


class TestLocking:
    def test_acquire_and_release_excl_lock(self, tmp_path):
        """F-LOCK-02: flock 释放后可再次获取（锁文件可保留）。"""
        lockfile = tmp_path / ".board.lock"
        handle = _acquire_lock(lockfile, timeout_s=2.0)
        assert handle is not None
        assert handle.exists()
        _release_lock(handle)
        again = _acquire_lock(lockfile, timeout_s=2.0)
        assert again is not None
        _release_lock(again)

    def test_stale_lock_cleared_when_holder_dead(self, tmp_path):
        """旧 O_EXCL 残留文件不阻挡 flock（锁在 lockfile 本身）。"""
        excl = tmp_path / ".board.lock.excl"
        excl.write_text("999999999|0.0")
        got = _acquire_lock(tmp_path / "board.lock", timeout_s=1.0)
        assert got is not None
        _release_lock(got)


class TestFileBoardStoreCRUD:
    def test_create_and_list_fifo(self, store: FileBoardStore):
        # 非 backlog 列：FIFO by created_at（升序）
        ok = store.create_task(
            _valid_task("aaa", status="in_progress")
            | {"created_at": "2026-01-01T00:00:00+08:00"},
            column="in_progress",
        )
        assert ok is True
        ok2 = store.create_task(
            _valid_task("bbb", status="in_progress")
            | {"created_at": "2026-01-01T00:00:01+08:00"},
            column="in_progress",
        )
        assert ok2 is True
        tasks = store.list_tasks("in_progress")
        assert [t["id"] for t in tasks] == ["aaa", "bbb"]

    def test_move_atomic_dst_then_unlink_src(self, store: FileBoardStore, tmp_path):
        # work 只能进 planned；epic 不可离开 backlog
        assert store.create_task(
            _valid_task("mv1", status="planned"), column="planned"
        )
        src = tmp_path / ".ccc" / "board" / "planned" / "mv1.jsonl"
        dst = tmp_path / ".ccc" / "board" / "in_progress" / "mv1.jsonl"
        assert store.move_task("mv1", "planned", "in_progress")
        assert dst.exists()
        assert not src.exists()
        task = json.loads(dst.read_text())
        assert task["status"] == "in_progress"

    def test_move_rejects_invalid_transition(self, store: FileBoardStore):
        store.create_task(_valid_task("bad"), column="backlog")
        assert store.move_task("bad", "backlog", "verified") is False

    def test_update_index_counts(self, store: FileBoardStore, tmp_path):
        store.create_task(_valid_task("i1"), column="backlog")
        counts = store.update_index()
        assert counts["backlog"] == 1
        index = json.loads((tmp_path / ".ccc" / "board" / "index.json").read_text())
        assert index["backlog"] == 1

    def test_quarantine_moves_to_abnormal(self, store: FileBoardStore, tmp_path):
        store.create_task(_valid_task("q1", status="in_progress"), column="in_progress")
        store.quarantine("q1", "test isolation")
        assert (tmp_path / ".ccc" / "board" / "abnormal" / "q1.jsonl").exists()
        assert not (tmp_path / ".ccc" / "board" / "in_progress" / "q1.jsonl").exists()

    def test_get_timeline_records_move(self, store: FileBoardStore):
        store.create_task(_valid_task("ev1", status="planned"), column="planned")
        store.move_task("ev1", "planned", "in_progress")
        events = store.get_timeline("ev1")
        assert len(events) >= 2
        assert events[-1]["to"] == "in_progress"

    def test_cleanup_events_removes_old_files(self, store: FileBoardStore, tmp_path):
        ev = tmp_path / ".ccc" / "board" / "events" / "old.events.jsonl"
        ev.write_text('{"event":"move"}\n')
        old = time.time() - 40 * 86400
        os.utime(ev, (old, old))
        removed = store.cleanup_events(max_days=30)
        assert removed == 1
        assert not ev.exists()


class TestHelpers:
    def test_sanitize_id_rejects_traversal(self):
        # v0.29.4: '.' 未加入允许字符集，../../etc → etc（斜杠和点都被剥）
        assert sanitize_id("../../etc") == "etc"
        assert sanitize_id("!!!") == "invalid"

    def test_fill_task_defaults(self):
        d = fill_task_defaults({"id": "x"})
        assert d["schema_version"] == "1.2"
        assert d["complexity"] == "medium"

    def test_assign_color_group_rotates(self, tmp_path):
        ws = tmp_path
        g1 = assign_color_group(ws)
        g2 = assign_color_group(ws)
        assert g1 in bs.GROUP_POOL
        assert g2 in bs.GROUP_POOL

    def test_validate_complexity_enum(self):
        ok, errs = validate_task_jsonl(_valid_task() | {"complexity": "xlarge"})
        assert not ok
        assert any("complexity" in e for e in errs)


class TestConcurrentLock:
    def test_second_writer_waits_or_aborts(self, tmp_path):
        lockfile = tmp_path / ".board.lock"
        first = _acquire_lock(lockfile, timeout_s=2.0)
        assert first is not None
        result = {"second": None}

        def _try_second():
            result["second"] = _acquire_lock(lockfile, timeout_s=0.3)

        t = threading.Thread(target=_try_second)
        t.start()
        t.join(timeout=2)
        _release_lock(first)
        assert result["second"] is None or result["second"] is not None


class TestQuarantineArchive:
    def test_quarantine_archives_plan_and_phases(
        self, store: FileBoardStore, tmp_path, monkeypatch
    ):
        tid = "arch-1"
        store.create_task(_valid_task(tid, status="in_progress"), column="in_progress")
        plans = tmp_path / ".ccc" / "plans"
        phases = tmp_path / ".ccc" / "phases"
        plans.mkdir(parents=True)
        phases.mkdir(parents=True)
        (plans / f"{tid}.plan.md").write_text("# plan")
        (phases / f"{tid}.phases.json").write_text(
            '{"schema_version":"1.1"}\n{"phase":1,"status":"pending"}\n'
        )
        qdir = tmp_path / ".ccc" / "quarantines"
        qdir.mkdir(parents=True)
        monkeypatch.setenv("CCC_QUARANTINES_DIR", str(qdir))
        store.quarantine(tid, "archive test")
        assert (qdir / tid).exists()

    def test_quarantine_store_content_file(self, tmp_path, monkeypatch):
        qdir = tmp_path / "q"
        monkeypatch.setenv("CCC_QUARANTINES_DIR", str(qdir))
        src = tmp_path / "payload.txt"
        src.write_text("data")
        assert bs.quarantine_store_content("task-q", src) is True
        assert (qdir / "task-q").exists()


class TestEdgeCases:
    def test_create_duplicate_id_rejected(self, store: FileBoardStore):
        store.create_task(_valid_task("dup"), column="backlog")
        assert store.create_task(_valid_task("dup"), column="backlog") is False

    def test_create_invalid_column(self, store: FileBoardStore):
        assert store.create_task(_valid_task("badcol"), column="not-a-column") is False

    def test_move_missing_task(self, store: FileBoardStore):
        assert store.move_task("missing", "backlog", "planned") is False

    def test_list_unknown_column_empty(self, store: FileBoardStore):
        assert store.list_tasks("unknown_col") == []

    def test_get_timeline_all_tasks(self, store: FileBoardStore):
        store.create_task(_valid_task("t-all", status="planned"), column="planned")
        store.move_task("t-all", "planned", "in_progress")
        events = store.get_timeline()
        assert len(events) >= 1

    def test_validate_strict_unknown_field(self):
        task = _valid_task()
        task["unknown_field"] = True
        ok, errs = validate_task_jsonl(task, strict=True)
        assert not ok
        assert any("unknown" in e for e in errs)

    def test_validate_rejects_missing_title_and_bad_status(self):
        t = _valid_task()
        del t["title"]
        ok, errs = validate_task_jsonl(t)
        assert not ok and any("title" in e for e in errs)
        t2 = _valid_task()
        t2["status"] = "invalid_col"
        ok2, errs2 = validate_task_jsonl(t2)
        assert not ok2 and any("status" in e for e in errs2)

    def test_assign_color_inherits_parent(self):
        assert assign_color_group(Path("/tmp"), parent_group="B") == "B"

    def test_get_quarantine_dir_from_workspace_env(self, tmp_path, monkeypatch):
        ws = tmp_path / "proj"
        (ws / ".ccc" / "quarantines").mkdir(parents=True)
        monkeypatch.setenv("CCC_WORKSPACE", str(ws))
        monkeypatch.delenv("CCC_QUARANTINES_DIR", raising=False)
        got = bs._get_quarantine_dir()
        assert got == ws / ".ccc" / "quarantines"

    def test_validate_field_type_errors(self):
        base = _valid_task()
        ok, errs = validate_task_jsonl({**base, "id": "!!!"})
        assert not ok and any("no valid chars" in e for e in errs)
        ok2, errs2 = validate_task_jsonl({**base, "id": "bad/id"})
        assert not ok2 and any("sanitized" in e for e in errs2)
        ok3, errs3 = validate_task_jsonl({**base, "status": ""})
        assert not ok3 and any("status" in e for e in errs3)
        ok4, errs4 = validate_task_jsonl({**base, "assignee": 123})
        assert not ok4 and any("assignee" in e for e in errs4)
        ok5, errs5 = validate_task_jsonl({**base, "tags": ["ok", 1]})
        assert not ok5 and any("tags[1]" in e for e in errs5)

    def test_assign_color_counter_corrupt_fallback(self, tmp_path):
        counter = tmp_path / ".ccc" / "board" / ".color_counter"
        counter.parent.mkdir(parents=True)
        counter.write_text("@@@")
        g = assign_color_group(tmp_path)
        assert g in bs.GROUP_POOL

    def test_list_tasks_missing_column_dir(self, store: FileBoardStore):
        import shutil

        shutil.rmtree(store.board / "released")
        assert store.list_tasks("released") == []

    def test_list_tasks_skips_malformed_json(self, store: FileBoardStore, tmp_path):
        col = tmp_path / ".ccc" / "board" / "backlog"
        (col / "bad.jsonl").write_text("not-json\n")
        tasks = store.list_tasks("backlog")
        assert tasks == []

    def test_create_task_validation_failure(self, store: FileBoardStore):
        bad = _valid_task("nope")
        del bad["title"]
        assert store.create_task(bad, column="backlog") is False

    def test_get_quarantine_dir_cwd_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CCC_QUARANTINES_DIR", raising=False)
        monkeypatch.delenv("CCC_WORKSPACE", raising=False)
        with patch("os.scandir", side_effect=OSError("scan blocked")):
            got = bs._get_quarantine_dir()
        assert got == tmp_path / ".ccc" / "quarantines"

    def test_quarantine_store_content_missing_returns_false(self):
        assert bs.quarantine_store_content("none", None) is False


class TestEventFormat:
    """test-board-events-format: events.jsonl 字段格式与 board-task-schema.md §7 一致"""

    def test_event_format(self, store: FileBoardStore, tmp_path: Path):
        # work 种子进 planned（epic 不可离开 backlog）
        store.create_task(_valid_task("fmt-1", status="planned"), column="planned")
        store.move_task("fmt-1", "planned", "in_progress")
        store.move_task("fmt-1", "in_progress", "testing")

        events_file = tmp_path / ".ccc" / "board" / "events" / "fmt-1.events.jsonl"
        assert events_file.exists(), "events.jsonl 未生成"

        raw_lines = [ln for ln in events_file.read_text().splitlines() if ln.strip()]
        events = [json.loads(ln) for ln in raw_lines]
        assert len(events) == 3, f"应写 3 条事件（含创建），实际 {len(events)}"

        required = {"event", "task_id", "from", "to", "timestamp"}
        for idx, ev in enumerate(events):
            assert required.issubset(ev.keys()), (
                f"事件 {idx} 缺失字段：{required - set(ev.keys())}"
            )
            assert ev["task_id"] == "fmt-1"
            assert isinstance(ev["timestamp"], str) and ev["timestamp"]
            assert ev["event"] in {"move", "assign", "quarantine"}, (
                f"未知 event 类型：{ev['event']!r}"
            )

        assert events[0]["from"] == "none", "创建时首条事件 from 应为 'none'"
        assert events[0]["to"] == "planned"

        assert events[1]["event"] == "move"
        assert events[1]["from"] == "planned" and events[1]["to"] == "in_progress"

        assert events[2]["event"] == "move"
        assert events[2]["from"] == "in_progress" and events[2]["to"] == "testing"
