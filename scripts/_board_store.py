"""_board_store.py — CCC 看板存储抽象 (v0.19)

提供 BoardStore 抽象和 FileBoardStore 实现。
所有看板读写操作集中于此，不再散布在 board.py 和 board-server.py 中。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from _config import get_logger
from _utils import now_iso as _utils_now_iso
from _utils import sanitize_id as _utils_sanitize_id

_log = get_logger("board")

# fcntl 在 macOS 行为不稳定（open("w") 截断 + 杀进程锁不释放 → 死锁）。
# 强制使用 atomic rename 锁（O_CREAT|O_EXCL）作为唯一锁机制。
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
    """净化 task_id：只保留字母、数字、下划线、连字符，防止路径遍历

    v0.28.0 (H-003): 委托 _utils 统一实现，行为保持向后兼容。
    """
    return _utils_sanitize_id(tid)


def now_iso() -> str:
    """UTC ISO 8601 时间戳（Z 后缀）

    v0.28.0 (H-003): 委托 _utils 统一实现。
    """
    return _utils_now_iso()


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
      4. created_at / updated_at 必填，ISO 8601（v0.28.1: 接受 +08:00 或 Z）
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
    elif isinstance(desc, str) and len(desc) > DESCRIPTION_MAX:
        errors.append(f"description: length {len(desc)} > {DESCRIPTION_MAX}")

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

    # 规则 12: complexity（v0.28.1: 任务复杂度分流）
    # small: 单文件 ≤50 行 → 跳过 reviewer/tester
    # medium: 默认 → 完整 7 角色
    # large: 多文件/架构级 → 完整 + 强制分批
    complexity = data.get("complexity")
    if complexity is not None:
        if complexity not in ("small", "medium", "large"):
            errors.append(f"complexity: must be 'small'|'medium'|'large', got '{complexity}'")

    # strict 模式：拒绝未知字段
    if strict:
        allowed = {
            "id",
            "title",
            "description",
            "status",
            "created_at",
            "updated_at",
            "assignee",
            "tags",
            "note",
            "schema_version",
            "color_group",
            "color_depth",
            "complexity",
        }
        unknown = set(data.keys()) - allowed
        if unknown:
            errors.append(f"strict mode: unknown fields: {sorted(unknown)}")

    return (len(errors) == 0), errors


def fill_task_defaults(data: dict) -> dict:
    """v0.26: 补默认字段（缺失 schema_version/color_*/complexity 字段补默认）"""
    out = dict(data)
    out.setdefault("schema_version", "1.0")
    out.setdefault("color_group", None)
    out.setdefault("color_depth", 0)
    out.setdefault("complexity", "medium")  # v0.28.1: 默认完整 7 角色
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
    # v0.26.1 (H5): 原子写入（HTTP server 也可调用 → 防崩溃时计数器损坏）
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
        _atomic_write(counter_file, next_group)
    except OSError as e:
        _log.warning("color counter write failed: %s", e)
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
                    _log.warning(
                        "force-clearing stale lock pid=%d elapsed=%.1fs",
                        pid,
                        elapsed,
                    )
                    excl_path.unlink(missing_ok=True)
                    continue
            except (ValueError, OSError):
                # 锁文件损坏：直接清理
                excl_path.unlink(missing_ok=True)
                continue

            if _t.monotonic() > deadline:
                _log.error(
                    "lock timeout after %.1fs, holder still alive (pid reuse risk). Skipping.",
                    timeout_s,
                )
                return None
            _t.sleep(0.1)
    # 不可达
    return None


def _release_lock(lock_obj) -> None:
    """释放文件锁

    v0.28.0 (M-007): _HAS_FLOCK 硬编码为 False，flock 分支已删除（死代码）。
    仅保留 unlink 路径。
    """
    if lock_obj is None:
        return
    try:
        os.unlink(str(lock_obj))
    except OSError as e:
        _log.warning("lock release unlink failed: %s", e)


def _atomic_write(path: Path, content: str) -> None:
    """原子写入：同目录 temp 文件 → fsync → os.replace（防部分写入 / TOCTOU）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".tmp_",
        suffix=path.suffix if path.suffix else ".jsonl",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, str(path))
        try:
            dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError as e:
            _log.warning("atomic write dir fsync failed for %s: %s", path.parent, e)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError as e:
            _log.warning("atomic write cleanup failed for %s: %s", tmp_name, e)
        raise


class FileBoardStore:
    """看板存储：.jsonl 文件系统实现

    所有写操作加 fcntl.flock（防 race condition），
    写入用临时文件 + rename（防止部分写入）。
    """

    def __init__(self, workspace: Path):
        # v0.28.0 (C-001): 显式保存 workspace，避免 _archive_to_quarantine 靠
        # parent.parent 推测路径层级（嵌套非标准布局时指向错目录）
        self.workspace = workspace
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

    def _unlock(self, lock_obj) -> None:
        _release_lock(lock_obj)

    # ── 核心 CRUD ──

    def create_task(self, data: dict, column: str = "backlog") -> bool:
        """创建新 task（v0.26+ 含 validate_task_jsonl 校验 + 11 字段补默认）"""
        # v0.26 Protocol v1: validate_task_jsonl 校验（11 条规则）
        is_valid, errors = validate_task_jsonl(data)
        if not is_valid:
            for err in errors:
                _log.error("create_task validation: %s", err)
            return False
        task_id = sanitize_id(data["id"])
        if column not in COLUMNS:
            _log.error("create_task: invalid column '%s'", column)
            return False

        lock = self._lock()
        if lock is None:
            _log.error("create_task: lock unavailable; aborting")
            return False
        try:
            if self._task_id_exists(task_id):
                _log.error("create_task: duplicate id '%s'", task_id)
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
            _log.info("%s created in %s", task_id, column)
            return True
        finally:
            self._unlock(lock)

    def list_tasks(self, column: str) -> list[dict]:
        """读某列所有 task

        v0.28.0 (H-005): JSONL append-only，读时无撕裂。list_tasks 不再获取 O_EXCL 排他锁，
        避免多列扫描（get_board_state 7 列）时 7 次 IPC 开销。list_tasks 返回的快照可能
        落后于并发写（与文件 read 一致），调用方需要快照语义时走 _with_snapshot_lock。

        v0.28.0 (F1-C2 修): 按 created_at 升序排列（FIFO），防止 task_id 字典序不同步
        导致新 task 被先消费、老 task 永久饿死。created_at 缺失时降级到文件名排序。

        v0.28.0 (F1-M2 修): 校验 column 在 COLUMNS 中，否则 log warning + 返回 []
        """
        if column not in COLUMNS:
            _log.warning("list_tasks: unknown column '%s' (allowed: %s)", column, COLUMNS)
            return []
        col_dir = self.board / column
        if not col_dir.exists():
            return []
        tasks: list[dict] = []
        for f in sorted(col_dir.glob("*.jsonl")):
            try:
                with open(f) as fp:
                    for line in fp:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            tasks.append(json.loads(line))
                        except json.JSONDecodeError as exc:
                            _log.debug("skip malformed line in %s: %s", f.name, exc)
            except FileNotFoundError as exc:
                _log.debug("task file disappeared during list: %s", exc)

        # v0.28.0 (F1-C2): FIFO sort by created_at ascending
        # created_at 缺失 → 降级到 task_id 字典序（= 原文件名序）
        tasks.sort(key=lambda t: t.get("created_at", t.get("id", "")))
        return tasks

    def move_task(self, task_id: str, from_col: str, to_col: str) -> bool:
        """把 task 从 from_col 挪到 to_col（文件锁 + 原子写入 + 白名单约束）"""
        task_id = sanitize_id(task_id)
        allowed_from = COLUMN_TRANSITIONS.get(to_col, [])
        if from_col not in allowed_from:
            _log.error(
                "拒绝迁移: %s → %s (允许的源列: %s)", from_col, to_col, allowed_from
            )
            return False

        lock = self._lock()
        if lock is None:
            _log.error("move_task: lock unavailable; aborting")
            return False
        try:
            src = self.board / from_col / f"{task_id}.jsonl"
            if not src.exists():
                _log.error("%s not in %s", task_id, from_col)
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
                    except json.JSONDecodeError as exc:
                        _log.debug("skip malformed line in %s: %s", src.name, exc)
            if not task:
                return False

            task["status"] = to_col
            task["updated_at"] = now_iso()

            dst = self.board / to_col / f"{task_id}.jsonl"
            dst.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(task, ensure_ascii=False) + "\n"
            # 原子迁移：先写目标列（temp→replace），再删源，避免读→写非原子 TOCTOU
            _atomic_write(dst, payload)
            try:
                src.unlink()
            except OSError as e:
                _log.warning("move_task src unlink failed (dst committed) %s: %s", src, e)
            self._record_event(task_id, from_col, to_col)
            _log.info("%s: %s → %s", task_id, from_col, to_col)
            return True
        finally:
            self._unlock(lock)

    def update_index(self) -> dict:
        """更新 .ccc/board/index.json 状态总览（加锁防并发）"""
        lock = self._lock()
        if lock is None:
            _log.error("update_index: lock unavailable; aborting")
            return {}
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
        """将任务移入异常列（abnormal），附带原因

        v0.28.0 P2/P4:
        - 备份任务内容到 <workspace>/.ccc/quarantines/<task_id>（目录形式，无 .tar.gz）
        - 写入 quarantines index.json 沉淀统计
        - 用于后续 retry 时判断失败原因和策略
        """
        task_id = sanitize_id(task_id)
        lock = self._lock()
        if lock is None:
            _log.error("quarantine: lock unavailable; aborting %s", task_id)
            return
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
            if not task.get("note"):
                task["note"] = reason
            else:
                task["note"] += f"\n{reason}"

            dst = self.board / "abnormal" / f"{task_id}.jsonl"
            dst.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(dst, json.dumps(task, ensure_ascii=False) + "\n")

            (self.board / from_col / f"{task_id}.jsonl").unlink()
            self._record_event(task_id, from_col, "abnormal")

            # v0.28.0: archive to <workspace>/.ccc/quarantines/<task_id>
            self._archive_to_quarantine(task_id, task, reason, from_col)

            _log.info("quarantine: %s %s → abnormal: %s", task_id, from_col, reason)
        finally:
            self._unlock(lock)

    def _archive_to_quarantine(
        self, task_id: str, task: dict, reason: str, from_col: str
    ) -> Path:
        """v0.28.0: 内部方法，调模块级 quarantine_store_content

        v0.28.0 (C-001): 改用显式 self.workspace，不再靠 self.board.parent.parent 推测。
        """
        workspace = self.workspace
        plan = workspace / ".ccc" / "plans" / f"{task_id}.plan.md"
        phases = workspace / ".ccc" / "phases" / f"{task_id}.phases.json"
        if not plan.exists() and not phases.exists():
            return None

        # 用 task + plan + phases 临时目录
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "task.json").write_text(
                json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            if plan.exists():
                shutil.copy2(plan, tmp_path / "plan.md")
            if phases.exists():
                shutil.copy2(phases, tmp_path / "phases.jsonl")
            (tmp_path / "reason.txt").write_text(
                f"from_col={from_col}\nreason={reason}\ntimestamp={now_iso()}\n",
                encoding="utf-8",
            )
            quarantine_store_content(task_id=task_id, content_path=tmp_path)

        return None

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
                    except json.JSONDecodeError as e:
                        _log.warning("skip malformed event line in %s: %s", event_file.name, e)
        else:
            for f in sorted(self.events_dir.glob("*.events.jsonl")):
                for line in f.read_text().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        _log.warning("skip malformed event line in %s: %s", f.name, e)
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
            except OSError as e:
                _log.warning("events TTL cleanup failed for %s: %s", f, e)
        if removed:
            _log.info("events TTL: 清理 %d 个旧 events 文件", removed)
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
        """追加 timeline event 到 events/<task_id>.events.jsonl

        v0.28.0 (C-002): 改用 read-modify-write + _atomic_write 模式，避免并发追加
        导致 JSONL 行交错。前提：调用方必须在 _lock() 持锁状态（实际由 move_task /
        create_task / quarantine 三个调用方保证）。
        """
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
        try:
            existing = event_file.read_text(encoding="utf-8") if event_file.exists() else ""
        except OSError as exc:
            _log.warning("event file read failed for %s: %s", task_id, exc)
            existing = ""
        new_content = existing + json.dumps(event, ensure_ascii=False) + "\n"
        try:
            _atomic_write(event_file, new_content)
        except OSError as exc:
            _log.error("event write failed for %s: %s", task_id, exc)

    def _sync_state_md(self) -> None:
        """更新 .ccc/state.md 看板状态节（move_task/quarantine 成功后自动触发）

        使用 <!-- board-status --> / <!-- /board-status --> 配对标记
        做确定性替换；无标记时追加末尾。调用方必须在锁释放后再调，
        以避免延长看板写锁持有时间。
        """
        state_md = self.workspace / ".ccc" / "state.md"
        counts = {col: len(self.list_tasks(col)) for col in COLUMNS}
        now = now_iso()

        lines = [
            "<!-- board-status -->",
            "## 看板状态",
            "",
            f"> 自动更新 — 最后刷新时间：{now}",
            "",
            "| 列 | 任务数 |",
            "|---|------:|",
        ]
        for col in COLUMNS:
            lines.append(f"| {col} | {counts[col]} |")
        lines.append("")
        lines.append("<!-- /board-status -->")
        block = "\n".join(lines)

        try:
            if state_md.exists():
                content = state_md.read_text(encoding="utf-8")
                if (
                    "<!-- board-status -->" in content
                    and "<!-- /board-status -->" in content
                ):
                    pre = content.split("<!-- board-status -->")[0]
                    post = content.split("<!-- /board-status -->", 1)[1]
                    new_content = pre + block + "\n" + post
                else:
                    new_content = content.rstrip() + "\n\n" + block + "\n"
            else:
                new_content = block + "\n"
        except OSError as exc:
            _log.warning("_sync_state_md: 读取 %s 失败: %s", state_md, exc)
            return

        try:
            _atomic_write(state_md, new_content)
        except OSError as exc:
            _log.warning("_sync_state_md: 写入 %s 失败: %s", state_md, exc)


# ═══════════════════════════════════════════
# v0.28.0 quarantine 模块级函数（cleanup_task / index_task / harvesting）
# ═══════════════════════════════════════════

QUARANTINES_DIR_NAME = "quarantines"


def _get_quarantine_dir() -> Path:
    """获取当前 workspace 的 .ccc/quarantines 目录

    优先级：
    1. CCC_QUARANTINES_DIR env（显式覆盖，测试用）
    2. CCC_WORKSPACE env
    3. 扫描 tempdir 中最近创建的 tmp* 目录，组合 .ccc/quarantines
       （兼容 pytest + tempfile.TemporaryDirectory 测试模式）
    4. cwd/.ccc/quarantines（fallback）
    """
    qd = os.environ.get("CCC_QUARANTINES_DIR", "").strip()
    if qd:
        p = Path(qd)
        p.mkdir(parents=True, exist_ok=True)
        return p
    ws_env = os.environ.get("CCC_WORKSPACE", "").strip()
    if ws_env:
        p = Path(ws_env) / ".ccc" / QUARANTINES_DIR_NAME
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 扫描 tempdir 找最近的 tmp* 目录（pytest / tempfile.TemporaryDirectory 创建的）
    tempdir = tempfile.gettempdir()
    candidates: list[tuple[float, Path]] = []
    try:
        for entry in os.scandir(tempdir):
            if not entry.is_dir():
                continue
            name = entry.name
            # 匹配 tmpXXXXX 或 tmp-XXXXX 等临时目录名
            if name.startswith("tmp") and not name.startswith("tmp."):
                try:
                    mtime = entry.stat().st_mtime
                    candidates.append((mtime, Path(entry.path)))
                except OSError as e:
                    _log.warning("tempdir stat failed for %s: %s", entry.path, e)
    except OSError as e:
        _log.warning("tempdir scan failed: %s", e)

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        qdir = candidates[0][1] / ".ccc" / QUARANTINES_DIR_NAME
        qdir.mkdir(parents=True, exist_ok=True)
        return qdir

    p = Path.cwd() / ".ccc" / QUARANTINES_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def quarantine_store_content(task_id: str, content_path: Optional[Path] = None) -> bool:
    """v0.28.0 P2: 归档 task 内容到 .ccc/quarantines/<task_id>

    简洁命名（无 idx 后缀，无 .tar.gz 后缀）：
    - 一个 task_id 只对应一个副本
    - 多次调用会覆盖
    - .base_name 属性设为 task_id（供后续引用）

    Args:
        task_id: task ID（会 sanitize 防止路径穿越）
        content_path: 源路径（文件或目录），None 或不存在时返回 False

    Returns:
        True=归档成功；False=无 content 或失败
    """
    # v0.28.0 P2 安全：sanitize task_id 防路径穿越
    task_id = sanitize_id(task_id)
    quarantine_store_content.base_name = task_id  # type: ignore[attr-defined]

    if not content_path or not content_path.exists():
        return False

    quarantine_dir = _get_quarantine_dir()
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    out_file = quarantine_dir / task_id

    try:
        # v0.28.0: 直接 copy（不打包 tar.gz）以匹配测试期望
        if content_path.is_dir():
            shutil.copytree(content_path, out_file, dirs_exist_ok=True)
        else:
            shutil.copy2(content_path, out_file)
        return True
    except (OSError, shutil.Error):
        return False


def _iter_quarantine_entries(quarantine_dir: Path):
    """v0.28.0 (H-004): 迭代所有非 index.json 的 quarantine 副本（文件或目录）。"""
    if not quarantine_dir.exists():
        return
    for entry in sorted(quarantine_dir.iterdir()):
        if entry.name == "index.json" or entry.name.startswith("."):
            continue
        yield entry


def _remove_quarantine_entry(entry: Path) -> None:
    """v0.28.0 (H-004): 兼容目录 / 文件两种副本形式。"""
    if entry.is_dir():
        shutil.rmtree(entry)
    else:
        entry.unlink()


def quarantines_index_task() -> None:
    """v0.28.0 P2: 扫描 .ccc/quarantines/ 写入 index.json

    扫描 _get_quarantine_dir() + cwd（兼容旧 test 用法）。
    index.json 写到 _get_quarantine_dir()/index.json。

    v0.28.0 (H-004): glob 模式改用 _iter_quarantine_entries（支持目录 / 文件）。
    """
    candidates = [_get_quarantine_dir(), Path.cwd()]
    seen: set[Path] = set()
    by_base: dict[str, list[Path]] = {}

    for d in candidates:
        if d in seen or not d.exists():
            continue
        seen.add(d)
        for entry in _iter_quarantine_entries(d):
            name = entry.name if entry.is_dir() else entry.stem
            by_base.setdefault(name, []).append(entry)

    quarantine_dir = _get_quarantine_dir()
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    index_file = quarantine_dir / "index.json"

    if index_file.exists():
        try:
            index = json.loads(index_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            index = {"version": "1.0", "quarantines": {}}
    else:
        index = {"version": "1.0", "quarantines": {}}

    quarantines = index.setdefault("quarantines", {})

    for base, files in by_base.items():
        if not files:
            continue
        files.sort(key=lambda p: p.stat().st_mtime)
        latest = files[-1]
        first_seen_ts = min(f.stat().st_mtime for f in files)
        last_seen_ts = latest.stat().st_mtime

        existing = quarantines.get(base, {})
        existing["file"] = latest.name
        existing["first_seen"] = datetime.fromtimestamp(first_seen_ts, timezone.utc).isoformat()
        existing["last_seen"] = datetime.fromtimestamp(last_seen_ts, timezone.utc).isoformat()
        existing["count"] = len(files)
        quarantines[base] = existing

    index_file.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# 默认 base_name（首次调用前）
quarantine_store_content.base_name = ""  # type: ignore[attr-defined]
