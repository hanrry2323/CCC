"""_board_store.py — CCC 看板存储抽象 (v0.19)

提供 BoardStore 抽象和 FileBoardStore 实现。
所有看板读写操作集中于此，不再散布在 board.py 和 board-server.py 中。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 尝试导入文件锁（非 macOS 系统不强制）
_HAS_FLOCK = False
try:
    import fcntl

    _HAS_FLOCK = True
except ImportError:
    pass


COLUMNS = [
    "backlog",
    "planned",
    "in_progress",
    "testing",
    "verified",
    "released",
    "abnormal",
]

# 列迁移白名单：{目标列: [允许的源列列表]}
# 不在白名单中的迁移会被拒绝
COLUMN_TRANSITIONS: dict[str, list[str]] = {
    "planned": ["backlog"],
    "in_progress": ["planned"],
    "testing": ["in_progress"],
    "verified": ["testing"],
    "released": ["verified"],
    "backlog": [
        "released",
        "in_progress",
        "abnormal",
        "planned",
    ],
    "abnormal": [
        "in_progress",
        "testing",
        "verified",
        "released",
    ],
}


def sanitize_id(tid: str) -> str:
    """净化 task_id：只保留字母、数字、下划线、连字符，防止路径遍历"""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", str(tid))
    return safe if safe else "invalid"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _acquire_lock(lockfile: Path) -> object:
    """加文件锁（如果平台支持），返回锁对象"""
    if _HAS_FLOCK:
        f = open(lockfile, "w")
        fcntl.flock(f, fcntl.LOCK_EX)
        return f
    # Fallback: 独占文件创建锁（跨平台原子操作，_HAS_FLOCK=False 时使用）
    import time as _time

    excl_path = lockfile.with_name(f".{lockfile.name}.excl")
    for _ in range(60):
        try:
            fd = os.open(str(excl_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return excl_path
        except FileExistsError:
            # 检测残留锁：检查持有进程是否存活
            try:
                pid_str = excl_path.read_text().strip()
                if pid_str:
                    pid = int(pid_str)
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        excl_path.unlink(missing_ok=True)
                        continue
            except (ValueError, OSError):
                pass
            _time.sleep(0.5)
    print(
        f"[board] WARNING: timeout acquiring fallback lock: {excl_path}",
        file=sys.stderr,
    )
    return None


def _release_lock(lock_obj) -> None:
    """释放文件锁"""
    if lock_obj is None:
        return
    if _HAS_FLOCK:
        try:
            fcntl.flock(lock_obj, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            lock_obj.close()
        except Exception:
            pass
    else:
        # Fallback: 删除独占锁文件
        try:
            os.unlink(str(lock_obj))
        except OSError:
            pass


def _atomic_write(path: Path, content: str) -> None:
    """原子写入：临时文件 → rename，防止部分写入"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(path.parent),
        prefix=".tmp_",
        suffix=".jsonl",
        delete=False,
        encoding="utf-8",
    )
    try:
        tmp.write(content)
        tmp.close()
        os.replace(tmp.name, str(path))
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


class FileBoardStore:
    """看板存储：.jsonl 文件系统实现

    所有写操作加 fcntl.flock（防 race condition），
    写入用临时文件 + rename（防止部分写入）。
    """

    def __init__(self, workspace: Path):
        self.board = workspace / ".ccc" / "board"
        self.events_dir = self.board / "events"
        self.lockfile = self.board / ".board.lock"
        # 兜底：裸 workspace 时建全 7 列 + events 目录（v0.22 N1 修）
        for col in COLUMNS:
            (self.board / col).mkdir(parents=True, exist_ok=True)

    # ── 内部方法 ──

    def _lock(self) -> object:
        return _acquire_lock(self.lockfile)

    def _unlock(self, lock_obj) -> None:
        _release_lock(lock_obj)

    # ── 核心 CRUD ──

    def create_task(self, data: dict, column: str = "backlog") -> bool:
        """创建新 task（含 id 唯一性校验 + 文件锁）"""
        task_id = sanitize_id(data.get("id", ""))
        if not task_id or task_id == "invalid":
            print("[board] create_task: missing 'id'", file=sys.stderr)
            return False
        if column not in COLUMNS:
            print(f"[board] create_task: invalid column '{column}'", file=sys.stderr)
            return False

        lock = self._lock()
        try:
            if self._task_id_exists(task_id):
                print(f"[board] create_task: duplicate id '{task_id}'", file=sys.stderr)
                return False

            now = now_iso()
            task = {
                "id": task_id,
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "status": column,
                "created_at": now,
                "updated_at": now,
                "assignee": data.get("assignee"),
                "tags": data.get("tags", []),
            }
            dst = self.board / column / f"{task_id}.jsonl"
            dst.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(dst, json.dumps(task, ensure_ascii=False) + "\n")
            self._record_event(task_id, "none", column)
            print(f"[board] {task_id} created in {column}")
            return True
        finally:
            self._unlock(lock)

    def list_tasks(self, column: str) -> list[dict]:
        """读某列所有 task（共享读锁，防幻读）"""
        col_dir = self.board / column
        if not col_dir.exists():
            return []
        tasks = []
        lock = None
        if _HAS_FLOCK:
            try:
                lock = open(self.lockfile, "w")
                fcntl.flock(lock, fcntl.LOCK_SH)
            except Exception:
                lock = None
        try:
            for f in sorted(col_dir.glob("*.jsonl")):
                try:
                    with open(f) as fp:
                        for line in fp:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                tasks.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
                except FileNotFoundError:
                    pass
            return tasks
        finally:
            if lock is not None:
                try:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    lock.close()
                except Exception:
                    pass

    def move_task(self, task_id: str, from_col: str, to_col: str) -> bool:
        """把 task 从 from_col 挪到 to_col（文件锁 + 原子写入 + 白名单约束）"""
        task_id = sanitize_id(task_id)
        allowed_from = COLUMN_TRANSITIONS.get(to_col, [])
        if from_col not in allowed_from:
            print(
                f"[board] 拒绝迁移: {from_col} → {to_col} (允许的源列: {allowed_from})",
                file=sys.stderr,
            )
            return False

        lock = self._lock()
        try:
            src = self.board / from_col / f"{task_id}.jsonl"
            if not src.exists():
                print(f"[board] {task_id} not in {from_col}", file=sys.stderr)
                return False

            task = None
            with open(src) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("id") == task_id:
                            task = obj
                            break
                    except json.JSONDecodeError:
                        pass
            if not task:
                return False

            task["status"] = to_col
            task["updated_at"] = now_iso()

            dst = self.board / to_col / f"{task_id}.jsonl"
            _atomic_write(dst, json.dumps(task, ensure_ascii=False) + "\n")
            try:
                src.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
            self._record_event(task_id, from_col, to_col)
            print(f"[board] {task_id}: {from_col} → {to_col}")
            return True
        finally:
            self._unlock(lock)

    def update_index(self) -> dict:
        """更新 .ccc/board/index.json 状态总览（加锁防并发）"""
        lock = self._lock()
        try:
            counts = {col: len(self.list_tasks(col)) for col in COLUMNS}
            index_file = self.board / "index.json"
            _atomic_write(
                index_file, json.dumps(counts, indent=2, ensure_ascii=False) + "\n"
            )
            return counts
        finally:
            self._unlock(lock)

    def quarantine(self, task_id: str, reason: str) -> None:
        """将任务移入异常列（abnormal），附带原因"""
        task_id = sanitize_id(task_id)
        lock = self._lock()
        try:
            from_col = ""
            for col in COLUMNS:
                if col == "abnormal":
                    continue
                src = self.board / col / f"{task_id}.jsonl"
                if src.exists():
                    from_col = col
                    break

            if not from_col:
                return

            task = json.loads((self.board / from_col / f"{task_id}.jsonl").read_text())
            task["status"] = "abnormal"
            task["updated_at"] = now_iso()
            tags = task.get("tags", [])
            if "abnormal" not in tags:
                tags.append("abnormal")
            if "automated" not in tags:
                tags.append("automated")
            task["tags"] = tags
            task["title"] = f"[ABNORMAL] {task.get('title', task_id)}"
            if "note" not in task:
                task["note"] = reason
            else:
                task["note"] += f"\n{reason}"

            dst = self.board / "abnormal" / f"{task_id}.jsonl"
            dst.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(dst, json.dumps(task, ensure_ascii=False) + "\n")

            (self.board / from_col / f"{task_id}.jsonl").unlink()
            self._record_event(task_id, from_col, "abnormal")
            print(f"[quarantine] {task_id} {from_col} → abnormal: {reason}")
        finally:
            self._unlock(lock)

    def get_timeline(self, task_id: Optional[str] = None) -> list[dict]:
        """从 events/*.events.jsonl 读取 timeline 事件"""
        if not self.events_dir.exists():
            return []
        events: list[dict] = []
        if task_id:
            task_id = sanitize_id(task_id)
            event_file = self.events_dir / f"{task_id}.events.jsonl"
            if event_file.exists():
                for line in event_file.read_text().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        else:
            for f in sorted(self.events_dir.glob("*.events.jsonl")):
                for line in f.read_text().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return events

    def cleanup_events(self, max_days: int = 30) -> int:
        """删除超过 max_days 天的 events 文件，返回删除数"""
        import time as _time

        if not self.events_dir.exists():
            return 0
        cutoff = _time.time() - max_days * 86400
        removed = 0
        for f in self.events_dir.glob("*.events.jsonl"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
        if removed:
            print(f"[board] events TTL: 清理 {removed} 个旧 events 文件")
        return removed

    # ── 内部辅助 ──

    def _task_id_exists(self, task_id: str) -> bool:
        """检查 task_id 是否在任意列中已存在"""
        task_id = sanitize_id(task_id)
        for col in COLUMNS:
            col_dir = self.board / col
            if (col_dir / f"{task_id}.jsonl").exists():
                return True
        return False

    def _record_event(self, task_id: str, from_col: str, to_col: str) -> None:
        """追加 timeline event 到 events/<task_id>.events.jsonl"""
        task_id = sanitize_id(task_id)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "event": "move",
            "task_id": task_id,
            "from": from_col,
            "to": to_col,
            "timestamp": now_iso(),
        }
        event_file = self.events_dir / f"{task_id}.events.jsonl"
        with open(event_file, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
