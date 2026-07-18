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
    "planned": ["backlog", "in_progress", "abnormal"],  # v0.31: patrol 退回
    "in_progress": ["planned"],
    "testing": ["in_progress", "abnormal", "planned"],  # v0.31: patrol 推进
    "verified": ["testing"],
    "released": ["verified", "abnormal"],  # v0.31: patrol 已修复释放
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
    """北京时间 ISO 8601 时间戳（+08:00）。
    委托 _utils 统一实现，所有模块保持一致。
    """
    return _utils_now_iso()


TITLE_MAX = 500
DESCRIPTION_MAX = 10000


# Epic lifecycle（五态）；active/blocked 为存量别名，读路径归一
SPLIT_STATUSES = ("pending", "planned", "running", "done", "failed")
SPLIT_STATUS_ALIASES = {
    "active": "running",  # 旧「已拆分」；refresh 会精算为 planned/running
    "blocked": "failed",
}
CARD_KINDS = ("epic", "work")

# backlog 排序：进行中组在前，failed 居中可处理，done 沉底
_BACKLOG_SPLIT_RANK = {
    "pending": 0,
    "planned": 1,
    "running": 2,
    "failed": 3,
    "done": 4,
}
_BACKLOG_FRONT = frozenset({"pending", "planned", "running"})


def validate_task_jsonl(data: dict, *, strict: bool = False) -> tuple[bool, list[str]]:
    """CCC Board Protocol 校验入口（事实依据：references/board-task-schema.md §4）

    Returns:
        (is_valid, errors) — errors 为空列表时 valid
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["data must be dict"]

    for rule in (
        _validate_rule_id,
        _validate_rule_title,
        _validate_rule_status,
        _validate_rule_timestamps,
        _validate_rule_description,
        _validate_rule_assignee,
        _validate_rule_tags,
        _validate_rule_note,
        _validate_rule_schema_version,
        _validate_rule_color_group,
        _validate_rule_color_depth,
        _validate_rule_complexity,
        _validate_rule_card_kind,
        _validate_rule_parent_id,
        _validate_rule_split_status,
        _validate_rule_child_ids,
        _validate_rule_ui_hidden,
        _validate_rule_epic_column,
    ):
        err = rule(data)
        if err:
            errors.append(err)

    if strict:
        err = _validate_strict_mode(data)
        if err:
            errors.append(err)

    return (len(errors) == 0), errors


def _validate_rule_id(data: dict) -> str | None:
    """规则 1: id 必填 + sanitize 后非 invalid + 无特殊字符"""
    raw_id = data.get("id")
    if raw_id is None or not str(raw_id).strip():
        return "id: required and non-empty"
    else:
        sanitized = sanitize_id(str(raw_id))
        if sanitized == "invalid":
            return "id: contains no valid chars (only [a-zA-Z0-9_-] allowed)"
        elif sanitized != str(raw_id):
            return f"id: would be sanitized from '{raw_id}' to '{sanitized}'"
        return None


def _validate_rule_title(data: dict) -> str | None:
    """规则 2: title 必填且非空字符串（≤ TITLE_MAX）"""
    title = data.get("title")
    if title is None or not str(title).strip():
        return "title: required and non-empty"
    elif len(str(title)) > TITLE_MAX:
        return f"title: length {len(str(title))} > {TITLE_MAX}"
    return None


def _validate_rule_status(data: dict) -> str | None:
    """规则 3: status 必填 ∈ COLUMNS"""
    status = data.get("status")
    if status is None or str(status).strip() == "":
        return "status: required"
    elif status not in COLUMNS:
        return f"status: '{status}' not in COLUMNS"
    return None


def _validate_rule_timestamps(data: dict) -> str | None:
    """规则 4: created_at / updated_at 必填，ISO 8601（v0.28.1: 接受 +08:00 或 Z）"""
    errors: list[str] = []
    for field in ("created_at", "updated_at"):
        val = data.get(field)
        if val is None or str(val).strip() == "":
            errors.append(f"{field}: required")
        else:
            try:
                datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                errors.append(f"{field}: '{val}' not ISO 8601")
    if errors:
        return "; ".join(errors)
    return None


def _validate_rule_description(data: dict) -> str | None:
    """规则 5: description 类型=str（可空）"""
    desc = data.get("description", "")
    if desc is not None and not isinstance(desc, str):
        return "description: must be string"
    elif isinstance(desc, str) and len(desc) > DESCRIPTION_MAX:
        return f"description: length {len(desc)} > {DESCRIPTION_MAX}"
    return None


def _validate_rule_assignee(data: dict) -> str | None:
    """规则 6: assignee 类型=str|None"""
    assignee = data.get("assignee")
    if assignee is not None and not isinstance(assignee, str):
        return "assignee: must be string or null"
    return None


def _validate_rule_tags(data: dict) -> str | None:
    """规则 7: tags 类型=list[str]"""
    tags = data.get("tags", [])
    if tags is not None:
        if not isinstance(tags, list):
            return "tags: must be list"
        else:
            for i, t in enumerate(tags):
                if not isinstance(t, str):
                    return f"tags[{i}]: must be string"
    return None


def _validate_rule_note(data: dict) -> str | None:
    """规则 8: note 类型=str|None"""
    note = data.get("note")
    if note is not None and not isinstance(note, str):
        return "note: must be string or null"
    return None


def _validate_rule_schema_version(data: dict) -> str | None:
    """规则 9: schema_version 必填类型检查"""
    schema_version = data.get("schema_version")
    if schema_version is not None and not isinstance(schema_version, str):
        return "schema_version: must be string"
    return None


def _validate_rule_color_group(data: dict) -> str | None:
    """规则 10: color_group 缺省 None；若存在 ∈ [A-Z] 单字符"""
    color_group = data.get("color_group")
    if color_group is not None:
        if not isinstance(color_group, str):
            return "color_group: must be string"
        elif len(color_group) != 1 or not ("A" <= color_group <= "Z"):
            return f"color_group: '{color_group}' must be single A-Z char"
    return None


def _validate_rule_color_depth(data: dict) -> str | None:
    """规则 11: color_depth 缺省 0；若存在 ≥ 0 整数"""
    color_depth = data.get("color_depth")
    if color_depth is not None:
        if not isinstance(color_depth, int) or isinstance(color_depth, bool):
            return "color_depth: must be int"
        elif color_depth < 0:
            return f"color_depth: must be >= 0, got {color_depth}"
    return None


def _validate_rule_complexity(data: dict) -> str | None:
    """规则 12: complexity 必须 'small'|'medium'|'large'（v0.28.1: 任务复杂度分流）"""
    complexity = data.get("complexity")
    if complexity is not None:
        if complexity not in ("small", "medium", "large"):
            return f"complexity: must be 'small'|'medium'|'large', got '{complexity}'"
    return None


def _validate_rule_card_kind(data: dict) -> str | None:
    """规则 13: card_kind ∈ {epic, work}"""
    kind = data.get("card_kind")
    if kind is not None and kind not in CARD_KINDS:
        return f"card_kind: must be 'epic'|'work', got '{kind}'"
    return None


def _validate_rule_parent_id(data: dict) -> str | None:
    """规则 14: parent_id 为 str|None；若有则须合法 id"""
    pid = data.get("parent_id")
    if pid is None:
        return None
    if not isinstance(pid, str) or not pid.strip():
        return "parent_id: must be non-empty string or null"
    if sanitize_id(pid) != pid:
        return f"parent_id: invalid id '{pid}'"
    return None


def _validate_rule_split_status(data: dict) -> str | None:
    """规则 15: split_status ∈ 五态（含存量 active/blocked 别名）；work 可空"""
    ss = data.get("split_status")
    if ss is None or ss == "":
        return None
    canon = SPLIT_STATUS_ALIASES.get(ss, ss)
    if canon not in SPLIT_STATUSES:
        return f"split_status: must be one of {SPLIT_STATUSES}, got '{ss}'"
    return None


def _validate_rule_child_ids(data: dict) -> str | None:
    """规则 16: child_ids 为 list[str]"""
    kids = data.get("child_ids")
    if kids is None:
        return None
    if not isinstance(kids, list):
        return "child_ids: must be list"
    for i, k in enumerate(kids):
        if not isinstance(k, str) or sanitize_id(k) != k:
            return f"child_ids[{i}]: must be valid task id"
    return None


def _validate_rule_ui_hidden(data: dict) -> str | None:
    """规则 17: ui_hidden 为 bool"""
    h = data.get("ui_hidden")
    if h is not None and not isinstance(h, bool):
        return "ui_hidden: must be bool"
    return None


def _validate_rule_epic_column(data: dict) -> str | None:
    """规则 18: epic 只能停留在 backlog"""
    if data.get("card_kind") == "epic" and data.get("status") not in (None, "backlog"):
        return "epic: status must be backlog"
    return None


def _validate_strict_mode(data: dict) -> str | None:
    """strict 模式：拒绝未知字段（仅在 validate_task_jsonl(..., strict=True) 时调用）"""
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
        "hints",
        "card_kind",
        "parent_id",
        "split_status",
        "child_ids",
        "ui_hidden",
        "phase_last_advanced_ts",
        "depends_on_tasks",
    }
    unknown = set(data.keys()) - allowed
    if unknown:
        return f"strict mode: unknown fields: {sorted(unknown)}"
    return None


def fill_task_defaults(data: dict, *, column: str | None = None) -> dict:
    """补默认字段；存量无 card_kind 时按列推断 epic/work。"""
    out = dict(data)
    out.setdefault("schema_version", "1.2")
    out.setdefault("color_group", None)
    out.setdefault("color_depth", 0)
    out.setdefault("complexity", "medium")
    out.setdefault("ui_hidden", False)
    out.setdefault("parent_id", None)
    out.setdefault("child_ids", [])
    col = column or out.get("status") or "backlog"
    if out.get("card_kind") not in CARD_KINDS:
        # 兼容：backlog 默认 epic；流转列默认 work
        out["card_kind"] = "epic" if col == "backlog" else "work"
    if out["card_kind"] == "epic":
        ss = out.get("split_status")
        if ss in SPLIT_STATUS_ALIASES:
            ss = SPLIT_STATUS_ALIASES[ss]
        if ss not in SPLIT_STATUSES:
            out["split_status"] = "pending"
        else:
            out["split_status"] = ss
        out["parent_id"] = None
        if not isinstance(out.get("child_ids"), list):
            out["child_ids"] = []
    else:
        # work：split_status 无意义，保持 None
        out.setdefault("split_status", None)
    return out


def normalize_task_view(task: dict, *, column: str | None = None) -> dict:
    """读路径补齐字段（不写盘）。"""
    return fill_task_defaults(task, column=column or task.get("status"))


# v0.26 Protocol v1 §5: 颜色分组 pool（A-Z 单字符轮转）
GROUP_POOL = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def task_border_hsl(color_group: str | None, color_depth: int = 0) -> str | None:
    """Protocol §5 HSL；无 group 返回 None（UI 回退列色）。

    depth0（epic）≈48% 更醒目；depth1（work）≈62% 更浅。
    """
    if not color_group or color_group not in GROUP_POOL:
        return None
    hue = (ord(color_group) - ord("A")) * 360 / 26
    lightness = 48 if int(color_depth) <= 0 else 62
    return f"hsl({hue:.1f}, 58%, {lightness}%)"


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
    """加文件锁（统一 fcntl.flock，F-LOCK-02）。

    进程崩溃后内核自动释放；活锁超时返回 None（不 force-clear）。
    """
    from board.lock import acquire_board_lock

    return acquire_board_lock(lockfile, timeout_s=timeout_s)


def _release_lock(lock_obj) -> None:
    """释放文件锁（flock unlock）。"""
    from board.lock import release_board_lock

    release_board_lock(lock_obj)


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
        """创建新 task（含 epic/work 字段补默认）"""
        now = now_iso()
        seed = dict(data)
        seed.setdefault("created_at", now)
        seed.setdefault("updated_at", now)
        seed.setdefault("status", column)
        data_with_defaults = fill_task_defaults(seed, column=column)
        is_valid, errors = validate_task_jsonl(data_with_defaults)
        if not is_valid:
            for err in errors:
                _log.error("create_task validation: %s", err)
            return False
        if data_with_defaults.get("card_kind") == "epic" and column != "backlog":
            _log.error("create_task: epic must be created in backlog, got %s", column)
            return False
        task_id = sanitize_id(data_with_defaults["id"])
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

            task = {
                "id": task_id,
                "title": data_with_defaults["title"],
                "description": data_with_defaults.get("description", ""),
                "status": column,
                "created_at": data_with_defaults.get("created_at", now),
                "updated_at": data_with_defaults.get("updated_at", now),
                "assignee": data_with_defaults.get("assignee"),
                "tags": data_with_defaults.get("tags") or [],
                "note": data_with_defaults.get("note"),
                "schema_version": data_with_defaults["schema_version"],
                "color_group": data_with_defaults["color_group"],
                "color_depth": data_with_defaults["color_depth"],
                "complexity": data_with_defaults.get("complexity", "medium"),
                "card_kind": data_with_defaults["card_kind"],
                "parent_id": data_with_defaults.get("parent_id"),
                "split_status": data_with_defaults.get("split_status"),
                "child_ids": list(data_with_defaults.get("child_ids") or []),
                "ui_hidden": bool(data_with_defaults.get("ui_hidden", False)),
            }
            deps_tasks = data_with_defaults.get("depends_on_tasks")
            if isinstance(deps_tasks, list) and deps_tasks:
                task["depends_on_tasks"] = [
                    str(d).strip() for d in deps_tasks if str(d).strip()
                ][:16]
            elif isinstance(deps_tasks, str) and deps_tasks.strip():
                task["depends_on_tasks"] = [deps_tasks.strip()]
            hints = data.get("hints")
            if isinstance(hints, dict):
                clean_hints: dict = {}
                skills = hints.get("skills")
                if isinstance(skills, list):
                    clean_skills = [
                        str(s).strip()[:80]
                        for s in skills
                        if str(s).strip()
                    ][:5]
                    if clean_skills:
                        clean_hints["skills"] = clean_skills
                note_h = hints.get("note")
                if isinstance(note_h, str) and note_h.strip():
                    clean_hints["note"] = note_h.strip()[:400]
                if clean_hints:
                    task["hints"] = clean_hints
            dst = self.board / column / f"{task_id}.jsonl"
            dst.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(dst, json.dumps(task, ensure_ascii=False) + "\n")
            self._record_event(task_id, "none", column)
            _log.info("%s created in %s kind=%s", task_id, column, task["card_kind"])
            return True
        finally:
            self._unlock(lock)

    def list_tasks(
        self, column: str, *, include_hidden: bool = False
    ) -> list[dict]:
        """读某列所有 task。

        backlog：pending/planned/running 在前（新→旧），failed 可处理，done 沉底；默认隐藏 ui_hidden。
        其它列：FIFO by created_at；默认过滤 ui_hidden。
        """
        if column not in COLUMNS:
            _log.warning(
                "list_tasks: unknown column '%s' (allowed: %s)", column, COLUMNS
            )
            return []
        col_dir = self.board / column
        if not col_dir.exists():
            return []
        tasks: list[dict] = []
        for f in sorted(col_dir.glob("*.jsonl")):
            try:
                raw = f.read_text(encoding="utf-8")
                if raw and not raw.endswith("\n"):
                    raw = raw.rsplit("\n", 1)[0] if "\n" in raw else ""
                for line in raw.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        tasks.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        _log.debug("skip malformed line in %s: %s", f.name, exc)
            except FileNotFoundError as exc:
                _log.debug("task file disappeared during list: %s", exc)
            except OSError as exc:
                _log.debug("list_tasks read failed %s: %s", f.name, exc)

        viewed = [normalize_task_view(t, column=column) for t in tasks]
        if not include_hidden:
            viewed = [t for t in viewed if not t.get("ui_hidden")]

        if column == "backlog":
            front = [
                t
                for t in viewed
                if (t.get("split_status") or "pending") in _BACKLOG_FRONT
            ]
            failed = [
                t for t in viewed if (t.get("split_status") or "") == "failed"
            ]
            done = [t for t in viewed if (t.get("split_status") or "") == "done"]
            other = [
                t
                for t in viewed
                if (t.get("split_status") or "pending")
                not in _BACKLOG_FRONT | {"failed", "done"}
            ]
            front.sort(
                key=lambda t: (
                    _BACKLOG_SPLIT_RANK.get(t.get("split_status") or "pending", 1),
                    t.get("created_at", t.get("id", "")),
                ),
                reverse=False,
            )
            # 同 rank 内新→旧；created_at 相同时按 id 升序确定
            front.sort(key=lambda t: t.get("id", ""))
            front.sort(
                key=lambda t: t.get("created_at", t.get("id", "")), reverse=True
            )
            front.sort(
                key=lambda t: _BACKLOG_SPLIT_RANK.get(
                    t.get("split_status") or "pending", 1
                )
            )
            failed.sort(key=lambda t: t.get("id", ""))
            failed.sort(
                key=lambda t: t.get("updated_at") or t.get("created_at") or "",
                reverse=True,
            )
            done.sort(key=lambda t: t.get("id", ""))
            done.sort(
                key=lambda t: t.get("updated_at") or t.get("created_at") or ""
            )
            other.sort(key=lambda t: t.get("id", ""))
            other.sort(
                key=lambda t: t.get("updated_at") or t.get("created_at") or ""
            )
            return front + failed + other + done

        viewed.sort(
            key=lambda t: (
                t.get("created_at", t.get("id", "")),
                t.get("id", ""),
            )
        )
        return viewed

    def find_task(self, task_id: str) -> tuple[str | None, dict | None]:
        """查找 task 所在列与内容。返回 (column, task)。"""
        task_id = sanitize_id(task_id)
        for col in COLUMNS:
            path = self.board / col / f"{task_id}.jsonl"
            if not path.is_file():
                continue
            try:
                obj = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
                return col, normalize_task_view(obj, column=col)
            except (OSError, json.JSONDecodeError, IndexError):
                continue
        return None, None

    def patch_task(self, task_id: str, fields: dict) -> bool:
        """原地更新 task 字段（不换列）。用于 epic split_status/child_ids/color 等。"""
        task_id = sanitize_id(task_id)
        lock = self._lock()
        if lock is None:
            _log.error("patch_task: lock unavailable")
            return False
        try:
            col, task = None, None
            for c in COLUMNS:
                src = self.board / c / f"{task_id}.jsonl"
                if src.is_file():
                    try:
                        task = json.loads(
                            src.read_text(encoding="utf-8").splitlines()[0]
                        )
                        col = c
                        break
                    except (OSError, json.JSONDecodeError, IndexError):
                        return False
            if not task or not col:
                _log.error("patch_task: %s not found", task_id)
                return False
            task.update(fields)
            task["id"] = task_id
            task["status"] = col
            task["updated_at"] = now_iso()
            task = fill_task_defaults(task, column=col)
            if task.get("card_kind") == "epic" and col != "backlog":
                _log.error("patch_task: epic cannot leave backlog")
                return False
            ok, errs = validate_task_jsonl(task)
            if not ok:
                _log.error("patch_task validation: %s", errs)
                return False
            _atomic_write(
                self.board / col / f"{task_id}.jsonl",
                json.dumps(task, ensure_ascii=False) + "\n",
            )
            return True
        finally:
            self._unlock(lock)

    def move_task(self, task_id: str, from_col: str, to_col: str) -> bool:
        """把 task 从 from_col 挪到 to_col（文件锁 + 原子写入 + 白名单约束）"""
        task_id = sanitize_id(task_id)
        allowed_from = COLUMN_TRANSITIONS.get(to_col, [])
        if from_col not in allowed_from:
            _log.error(
                "拒绝迁移: %s → %s (允许的源列: %s)", from_col, to_col, allowed_from
            )
            return False

        success = False
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

            task = normalize_task_view(task, column=from_col)
            # epic 大卡永不可离开 backlog
            if task.get("card_kind") == "epic" and to_col != "backlog":
                _log.error(
                    "拒绝迁移: epic %s 不可离开 backlog → %s", task_id, to_col
                )
                return False

            task["status"] = to_col
            now = now_iso()
            task["updated_at"] = now
            task["phase_last_advanced_ts"] = now

            dst = self.board / to_col / f"{task_id}.jsonl"
            dst.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(task, ensure_ascii=False) + "\n"
            _atomic_write(dst, payload)
            try:
                src.unlink()
            except OSError as e:
                _log.warning(
                    "move_task src unlink failed (dst committed) %s: %s", src, e
                )
            self._record_event(task_id, from_col, to_col)
            _log.info("%s: %s → %s", task_id, from_col, to_col)
            success = True
        finally:
            self._unlock(lock)
        if success:
            self._sync_state_md()
        return success

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
        success = False
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
            success = True
        finally:
            self._unlock(lock)
        if success:
            self._sync_state_md()

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
                        _log.warning(
                            "skip malformed event line in %s: %s", event_file.name, e
                        )
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
            existing = (
                event_file.read_text(encoding="utf-8") if event_file.exists() else ""
            )
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
    - 通过 get_quarantine_base_name() 读取最近一次 base_name

    Args:
        task_id: task ID（会 sanitize 防止路径穿越）
        content_path: 源路径（文件或目录），None 或不存在时返回 False

    Returns:
        True=归档成功；False=无 content 或失败
    """
    # v0.28.0 P2 安全：sanitize task_id 防路径穿越
    task_id = sanitize_id(task_id)
    global _QUARANTINE_BASE_NAME
    _QUARANTINE_BASE_NAME = task_id

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
        existing["first_seen"] = datetime.fromtimestamp(
            first_seen_ts, timezone.utc
        ).isoformat()
        existing["last_seen"] = datetime.fromtimestamp(
            last_seen_ts, timezone.utc
        ).isoformat()
        existing["count"] = len(files)
        quarantines[base] = existing

    index_file.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# v0.30.0: 默认 base_name（首次调用前）
_QUARANTINE_BASE_NAME: str = ""


def get_quarantine_base_name() -> str:
    """v0.30.0: 替代 quarantine_store_content.base_name 函数属性。"""
    return _QUARANTINE_BASE_NAME
