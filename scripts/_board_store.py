"""_board_store.py — CCC 看板存储抽象 (v0.19)

提供 BoardStore 抽象和 FileBoardStore 实现。
所有看板读写操作集中于此，不再散布在 board.py 和 board-server.py 中。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# fcntl 在 macOS 行为不稳定（open("w") 截断 + 杀进程锁不释放 → 死锁）。
# 强制使用 atomic rename 锁（O_CREAT|O_EXCL）作为唯一锁机制。
_HAS_FLOCK = False


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
    "testing": ["in_progress", "abnormal"],  # v0.23.16: abnormal 重投允许
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


# v0.26 Protocol v1: 11 条校验规则常量
VALID_ID_CHARS = re.compile(r"^[a-zA-Z0-9_-]+$")
TITLE_MAX = 500
DESCRIPTION_MAX = 10000


def validate_task_jsonl(data: dict, *, strict: bool = False) -> tuple[bool, list[str]]:
    """v0.26 CCC Board Protocol v1 校验入口（事实依据：references/board-task-schema.md §4）

    Returns:
        (is_valid, errors) — errors 为空列表时 valid
        第一条 error 必为人类可读摘要（IDE 端 fix_hint）

    11 条规则（与协议文档同步）：
      1. id 必填，sanitize 后非 "invalid"，仅 [a-zA-Z0-9_-]
      2. title 必填且非空字符串（≤ TITLE_MAX）
      3. status 必填 ∈ COLUMNS
      4. created_at / updated_at 必填，ISO 8601 UTC
      5. description 类型=str（可空）
      6. assignee 类型=str|None
      7. tags 类型=list[str]
      8. note 类型=str|None
      9. schema_version 缺省补 "1.0"
     10. color_group 缺省 None；若存在 ∈ [A-Z] 单字符
     11. color_depth 缺省 0；若存在 ≥ 0 整数

    strict=True 时：
      - 不接受未知字段（id/title/status/timestamps/assignee/tags/note/
        schema_version/color_group/color_depth/description 之外的 key 拒绝）
      - 类型不符直接拒绝（不允许缺失补默认）

    strict=False（默认）：
      - 未知字段忽略
      - 缺失字段补默认
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["data must be dict"]

    # 规则 1: id
    raw_id = data.get("id")
    if raw_id is None or not str(raw_id).strip():
        errors.append("id: required and non-empty")
    else:
        sanitized = sanitize_id(str(raw_id))
        if sanitized == "invalid":
            errors.append("id: contains no valid chars (only [a-zA-Z0-9_-] allowed)")
        elif sanitized != str(raw_id):
            errors.append(f"id: would be sanitized from '{raw_id}' to '{sanitized}'")

    # 规则 2: title
    title = data.get("title")
    if title is None or not str(title).strip():
        errors.append("title: required and non-empty")
    elif len(str(title)) > TITLE_MAX:
        errors.append(f"title: length {len(str(title))} > {TITLE_MAX}")

    # 规则 3: status
    status = data.get("status")
    if status is None or str(status).strip() == "":
        errors.append("status: required")
    elif status not in COLUMNS:
        errors.append(f"status: '{status}' not in COLUMNS")

    # 规则 4: created_at / updated_at (ISO 8601)
    for field in ("created_at", "updated_at"):
        val = data.get(field)
        if val is None or str(val).strip() == "":
            errors.append(f"{field}: required")
        else:
            try:
                datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                errors.append(f"{field}: '{val}' not ISO 8601")

    # 规则 5: description
    desc = data.get("description", "")
    if desc is not None and not isinstance(desc, str):
        errors.append("description: must be string")

    # 规则 6: assignee
    assignee = data.get("assignee")
    if assignee is not None and not isinstance(assignee, str):
        errors.append("assignee: must be string or null")

    # 规则 7: tags
    tags = data.get("tags", [])
    if tags is not None:
        if not isinstance(tags, list):
            errors.append("tags: must be list")
        else:
            for i, t in enumerate(tags):
                if not isinstance(t, str):
                    errors.append(f"tags[{i}]: must be string")

    # 规则 8: note
    note = data.get("note")
    if note is not None and not isinstance(note, str):
        errors.append("note: must be string or null")

    # 规则 9: schema_version
    schema_version = data.get("schema_version")
    if schema_version is not None and not isinstance(schema_version, str):
        errors.append("schema_version: must be string")

    # 规则 10: color_group
    color_group = data.get("color_group")
    if color_group is not None:
        if not isinstance(color_group, str):
            errors.append("color_group: must be string")
        elif len(color_group) != 1 or not ("A" <= color_group <= "Z"):
            errors.append(f"color_group: '{color_group}' must be single A-Z char")

    # 规则 11: color_depth
    color_depth = data.get("color_depth")
    if color_depth is not None:
        if not isinstance(color_depth, int) or isinstance(color_depth, bool):
            errors.append("color_depth: must be int")
        elif color_depth < 0:
            errors.append(f"color_depth: must be >= 0, got {color_depth}")

    # strict 模式：拒绝未知字段
    if strict:
        allowed = {
            "id", "title", "description", "status", "created_at", "updated_at",
            "assignee", "tags", "note", "schema_version", "color_group", "color_depth",
        }
        unknown = set(data.keys()) - allowed
        if unknown:
            errors.append(f"strict mode: unknown fields: {sorted(unknown)}")

    return (len(errors) == 0), errors


def fill_task_defaults(data: dict) -> dict:
    """v0.26: 补默认字段（缺失 schema_version/color_* 字段补默认）"""
    out = dict(data)
    out.setdefault("schema_version", "1.0")
    out.setdefault("color_group", None)
    out.setdefault("color_depth", 0)
    return out


# v0.26 Protocol v1 §5: 颜色分组 pool（A-Z 单字符轮转）
GROUP_POOL = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def assign_color_group(workspace: Path, parent_group: str | None = None) -> str:
    """v0.26 Protocol v1 §5: 分配 color_group
    - 父任务有 group → 子继承
    - 无 → 从 pool 取下一个（按字母序轮转，持久化在 .ccc/board/.color_counter）
    """
    if parent_group and parent_group in GROUP_POOL:
        return parent_group
    counter_file = workspace / ".ccc" / "board" / ".color_counter"
    counter_file.parent.mkdir(parents=True, exist_ok=True)
    # 简化版：顺序轮转，无并发锁（CCC 是单 Engine 串行，无需锁）
    if counter_file.exists():
        try:
            current = counter_file.read_text().strip() or "A"
            idx = GROUP_POOL.index(current) if current in GROUP_POOL else -1
            next_idx = (idx + 1) % len(GROUP_POOL)
        except (ValueError, OSError):
            next_idx = 0
    else:
        next_idx = 0
    next_group = GROUP_POOL[next_idx]
    try:
        counter_file.write_text(next_group)
    except OSError:
        pass
    return next_group


def _acquire_lock(lockfile: Path, timeout_s: float = 30.0) -> object:
    """加文件锁（atomic rename 模式），返回锁对象路径

    只用 atomic 创建（O_CREAT|O_EXCL）：无 fcntl 死锁、无截断写。
    持锁进程被杀死后锁文件残留，下次获取时检测 pid 失效自动清理。

    v0.24.6 (A24-02): 阈值 5s → 30s；锁内容改为 "{pid}|{mtime}"；
    强清条件：elapsed > 30s 且 pid 已死；活 pid 永不强制清理（防 PID reuse 误杀无辜进程）。
    """
    import time as _t
    excl_path = lockfile.with_name(f".{lockfile.name}.excl")
    deadline = _t.monotonic() + timeout_s
    while True:
        try:
            fd = os.open(str(excl_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = f"{os.getpid()}|{_t.time():.3f}".encode()
            os.write(fd, payload)
            os.close(fd)
            return excl_path
        except FileExistsError:
            # 残留锁检测：持有进程死了 + 锁已超 30s 才清（防 PID reuse 误杀）
            try:
                content = excl_path.read_text().strip()
                if "|" in content:
                    pid_str, mtime_str = content.split("|", 1)
                    pid = int(pid_str)
                    mtime = float(mtime_str)
                else:
                    # 兼容旧格式（无 mtime）：立即清理升级到新格式
                    pid = int(content)
                    mtime = 0.0
                elapsed = _t.time() - mtime if mtime > 0 else 999999
                try:
                    os.kill(pid, 0)
                    pid_alive = True
                except (OSError, ProcessLookupError):
                    pid_alive = False
                # 清理条件：pid 已死 OR (pid 活但锁已超 30s 且 deadline 已过)
                if not pid_alive:
                    excl_path.unlink(missing_ok=True)
                    continue
                if elapsed > timeout_s and _t.monotonic() > deadline:
                    print(
                        f"[board] WARN: force-clearing stale lock pid={pid} elapsed={elapsed:.1f}s",
                        file=sys.stderr,
                    )
                    excl_path.unlink(missing_ok=True)
                    continue
            except (ValueError, OSError):
                # 锁文件损坏：直接清理
                excl_path.unlink(missing_ok=True)
                continue

            if _t.monotonic() > deadline:
                print(
                    f"[board] ERROR: lock timeout after {timeout_s}s, holder still alive (pid reuse risk). Skipping.",
                    file=sys.stderr,
                )
                return None
            _t.sleep(0.1)
    # 不可达
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
        """写锁（5s 超时，强清残留）"""
        return _acquire_lock(self.lockfile, timeout_s=5.0)

    def _acquire_ro(self, timeout_s: float = 0.5) -> Optional[object]:
        """读锁占位（atomic O_EXCL 永远独占，只能互斥；读时退化到 0.5s 短锁）"""
        return _acquire_lock(self.lockfile, timeout_s=timeout_s)

    def _unlock(self, lock_obj) -> None:
        _release_lock(lock_obj)

    # ── 核心 CRUD ──

    def create_task(self, data: dict, column: str = "backlog") -> bool:
        """创建新 task（v0.26+ 含 validate_task_jsonl 校验 + 11 字段补默认）"""
        # v0.26 Protocol v1: validate_task_jsonl 校验（11 条规则）
        is_valid, errors = validate_task_jsonl(data)
        if not is_valid:
            for err in errors:
                print(f"[board] create_task validation: {err}", file=sys.stderr)
            return False
        task_id = sanitize_id(data["id"])
        if column not in COLUMNS:
            print(f"[board] create_task: invalid column '{column}'", file=sys.stderr)
            return False

        lock = self._lock()
        try:
            if self._task_id_exists(task_id):
                print(f"[board] create_task: duplicate id '{task_id}'", file=sys.stderr)
                return False

            now = now_iso()
            # v0.26: 补默认 schema_version / color_group / color_depth
            data_with_defaults = fill_task_defaults(data)
            task = {
                "id": task_id,
                "title": data["title"],
                "description": data.get("description", ""),
                "status": column,
                "created_at": data.get("created_at", now),
                "updated_at": data.get("updated_at", now),
                "assignee": data.get("assignee"),
                "tags": data.get("tags", []),
                "note": data.get("note"),
                "schema_version": data_with_defaults["schema_version"],
                "color_group": data_with_defaults["color_group"],
                "color_depth": data_with_defaults["color_depth"],
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
        # atomic 锁，3s 超时，读锁
        excl_path = self._acquire_ro(timeout_s=3.0)
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
            if excl_path is not None:
                try:
                    excl_path.unlink(missing_ok=True)
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
            # 原子迁移：先把更新后的 task 写回 src（status 已更新），再 shutil.move 一次性挪过去。
            # 这样 dst 的 status 字段和物理位置天然一致。
            try:
                dst.unlink()
            except FileNotFoundError:
                pass
            src.write_text(json.dumps(task, ensure_ascii=False) + "\n")
            shutil.move(str(src), str(dst))
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
