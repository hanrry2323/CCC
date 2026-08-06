"""session_store — 会话持久化（T47 项目+会话模型）。

把对话历史与会话元数据按「项目 + thread」落盘到
``<DATA_DIR>/conversations/<project>/<thread>.jsonl``（消息）与
``<DATA_DIR>/conversations/<project>/_index.json``（元数据，标题/时间/消息数）。

设计要点：
- thread/项目名进入文件路径前做安全清洗（防目录穿越）。
- 消息为 JSONL 追加写；元数据索引为整文件覆盖写（会话数量级小，可接受）。
- DATA_DIR 从环境变量 ``CCC_DATA_DIR``/``DATA_DIR`` 读取，缺默认用项目内 ``data/``
  （仅在部署未配置 DATA_DIR 时兜底，正常生产由 config.env 注入）。
- 本模块不持有任何 HTTP/SSE 状态，纯磁盘读写；切项目/会话不中断活跃流
  （流在 server.py 内存历史里，落盘只做旁路持久化）。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

_write_lock = threading.Lock()


def _data_root() -> Path:
    """会话持久化根目录：优先 DATA_DIR env（CCC_DATA_DIR 或 DATA_DIR），缺默认 data/。"""
    raw = os.environ.get("CCC_DATA_DIR", "") or os.environ.get("DATA_DIR", "")
    if raw:
        return Path(raw).expanduser().resolve()
    # 兜底：项目内 data/（仅未配置 DATA_DIR 时）
    return Path(__file__).resolve().parents[2] / "data"


def _conversations_root() -> Path:
    """DATA_DIR/conversations。"""
    return _data_root() / "conversations"


def _sanitize(part: str) -> str:
    """清洗路径片段：去分隔符/点号/空，仅保留安全字符，防目录穿越。"""
    cleaned = "".join(c for c in part if (c.isalnum() or c in "_.-"))
    cleaned = cleaned.strip(" ._")
    # 兜底：空/非法片段给个占位，禁止退化为 '.'/'..'
    return cleaned or "_"


def _thread_path(project: str, thread_id: str) -> Path:
    """项目+thread 的消息 JSONL 文件路径（清洗后可安全 join）。"""
    return _conversations_root() / _sanitize(project) / f"{_sanitize(thread_id)}.jsonl"


def _index_path(project: str) -> Path:
    """项目下会话索引文件路径。"""
    return _conversations_root() / _sanitize(project) / "_index.json"


# ── 消息读写（JSONL 追加） ──


def load_thread(project: str, thread_id: str) -> list[dict[str, Any]]:
    """读取项目+thread 的持久化消息列表；无文件返回空列表。"""
    p = _thread_path(project, thread_id)
    if not p.is_file():
        return []
    msgs: list[dict[str, Any]] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msgs.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # 丢弃损坏行（保留其余）
    except OSError:
        return []
    return msgs


def append_messages(project: str, thread_id: str, messages: list[dict[str, Any]]) -> None:
    """把消息 JSONL 追加写盘（每消息一行）。创建目录，忽略写失败（尽力而为）。"""
    if not messages:
        return
    p = _thread_path(project, thread_id)
    with _write_lock:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            lines = "".join(
                json.dumps(m, ensure_ascii=False, default=str) + "\n" for m in messages
            )
            with p.open("a", encoding="utf-8") as fh:
                fh.write(lines)
        except OSError:
            # 落盘失败不阻断对话主流程（内存历史仍可用）
            return


def delete_thread(project: str, thread_id: str) -> None:
    """删除项目+thread 的消息文件与索引项。"""
    p = _thread_path(project, thread_id)
    with _write_lock:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
    # 同步从索引移除（尽力而为）
    index = load_index(project)
    if thread_id in index:
        index.pop(thread_id, None)
        _write_index(project, index)


# ── 会话元数据索引（标题/创建时间/最后活动/消息数） ──


def load_jsonl(jl_path: Path) -> list[dict[str, Any]]:
    """读取给定 JSONL 文件为消息列表（供启动恢复扫描用，绕过项目路径清洗）。"""
    msgs: list[dict[str, Any]] = []
    try:
        for line in jl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msgs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return msgs


def load_index(project: str) -> dict[str, dict[str, Any]]:
    """读取项目下会话索引：{thread_id: {title, created_at, updated_at, message_count}}。"""
    p = _index_path(project)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_index(project: str, index: dict[str, dict[str, Any]]) -> None:
    p = _index_path(project)
    with _write_lock:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            return


def _derive_title(messages: list[dict[str, Any]]) -> str:
    """从首条 user 消息截断生成标题（默认「新对话」）。"""
    title = "新对话"
    for m in messages:
        if m.get("role") == "user" and m.get("message"):
            text = m["message"].strip().replace("\n", " ")
            title = text if len(text) <= 30 else text[:30] + "…"
            break
    return title


def touch_thread(project: str, thread_id: str, title: str = "") -> None:
    """更新会话索引：标题（首条）/创建时间/最后活动/消息数。供 /conversation 落盘后调用。"""
    index = load_index(project)
    entry = index.get(thread_id, {})
    existed = bool(entry)
    if not existed:
        entry["created_at"] = _now()
    messages = load_thread(project, thread_id)
    if title:
        entry["title"] = title
    else:
        entry["title"] = entry.get("title") or _derive_title(messages)
    entry["updated_at"] = _now()
    entry["message_count"] = len(messages)
    index[thread_id] = entry
    _write_index(project, index)


def rename_thread(project: str, thread_id: str, title: str) -> None:
    """重命名会话标题（持久化索引）。"""
    index = load_index(project)
    entry = index.get(thread_id, {})
    entry["title"] = title
    if "created_at" not in entry:
        entry["created_at"] = _now()
    entry["updated_at"] = _now()
    index[thread_id] = entry
    _write_index(project, index)


def list_threads(project: str) -> list[dict[str, Any]]:
    """列出项目下会话元数据（按最后活动倒序）。返回含 thread_id 的条目。"""
    index = load_index(project)
    threads = []
    for tid, meta in index.items():
        threads.append(
            {
                "thread_id": tid,
                "title": meta.get("title", "新对话"),
                "created_at": meta.get("created_at", ""),
                "updated_at": meta.get("updated_at", ""),
                "message_count": meta.get("message_count", 0),
            }
        )
    threads.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    return threads


def _now() -> str:
    """ISO8601 UTC 时间戳（datetime 替代，避免 Date.now 依赖注入问题）。"""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
