"""看板对接接口 + 内存/文件实现。

engine 只依赖 `BoardStore` 接口做状态更新；不直接触碰 board/ 内部实现。

- `InMemoryBoardStore`：进程内字典（测试/演示用）。
- `FileBoardStore`：文件/卡驱动（P1-1）——读 `docs/dispatch/*.md` 卡头元数据 →
  构造 `Work`；状态流转后回写卡头「状态」行。生产路径用此实现。

用法（文件驱动）：
    from server.engine.store import FileBoardStore

    store = FileBoardStore("docs/dispatch", registry)
    pending = store.list_work(state=State.TODO)
    for work in pending:
        work.transition(State.RUNNING)
        store.save_work(work)  # 回写卡头「状态：执行中」
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Protocol

from server.board.loader import _strip_parenthetical  # noqa: PLC0415 — 复用同一解析逻辑
from server.board.models import UNKNOWN, base_state
from server.engine.dispatch import ExecutorRegistry
from server.engine.task import State, Work

logger = logging.getLogger("ccc.engine.store")

# 卡头「状态：X」段匹配（用于回写时定位替换）
# lookahead 保留 `·` 前的空格，不消费
_STATE_PAIR_RE = re.compile(r"(状态\s*[:：]\s*)([^\n·]+?)(?=\s*·|\s*$)")

# 待分派（重试2/3：原因）或 待分派（重试2：原因）→ 持久化 retry_count
_RETRY_IN_STATE_RE = re.compile(r"待分派（重试(\d+)")

# 卡头状态字符串 → State 枚举
_STR_TO_STATE: dict[str, State] = {
    "待分派": State.TODO,
    "执行中": State.RUNNING,
    "已回写": State.DONE,
    "已关闭": State.CLOSED,
    "打回": State.REJECTED,
}


def _retry_count_from_state_str(raw_state: str) -> int:
    """从卡头状态串解析重试次数。"""
    if not raw_state:
        return 0
    m = _RETRY_IN_STATE_RE.search(raw_state)
    if m:
        try:
            return max(0, int(m.group(1)))
        except ValueError:
            return 0
    # 兼容旧式「待分派（原因）」：至少记 1 次已回炉
    if "待分派（" in raw_state:
        return 1
    return 0


def _state_from_str(s: str) -> State:
    """卡头状态字符串 → State 枚举；未知/空 → None（调用方跳过）。"""
    base = base_state(s)
    return _STR_TO_STATE.get(base)  # type: ignore[return-value]


class BoardStore(Protocol):
    """看板存储接口。"""

    def list_work(self, state: State | None = None) -> list[Work]:
        """按状态过滤列出 work；state=None 列出全部。"""
        ...

    def save_work(self, work: Work) -> None:
        """持久化 work 状态更新。"""
        ...


class InMemoryBoardStore:
    """内存实现（进程内字典），测试/演示用。"""

    def __init__(self) -> None:
        self._items: dict[str, Work] = {}

    def seed(self, *works: Work) -> None:
        """注入初始 work（测试/演示用）。"""
        for work in works:
            self._items[work.id] = work

    def list_work(self, state: State | None = None) -> list[Work]:
        """按状态过滤；state=None 返回全部。"""
        if state is None:
            return list(self._items.values())
        return [w for w in self._items.values() if w.state is state]

    def save_work(self, work: Work) -> None:
        """按 work.id 写入。"""
        self._items[work.id] = work


class FileBoardStore:
    """文件/卡驱动看板存储（P1-1）。

    读 `docs/dispatch/*.md` 卡头元数据 → 构造 `Work`；
    `save_work` 回写卡头「状态：X」行（原子替换）。

    Args:
        dispatch_dir: 任务卡目录（如 `docs/dispatch`）。
        registry: 执行体注册表（用于工具名 → 角色反查）。
    """

    def __init__(self, dispatch_dir: str | Path, registry: ExecutorRegistry) -> None:
        self._dir = Path(dispatch_dir)
        self._registry = registry

    def list_work(self, state: State | None = None) -> list[Work]:
        """走索引列出 work (扫描仅用于重建/校验)。"""
        from server.board.loader import load_dispatch_cards, load_index_file
        load_dispatch_cards(self._dir)

        index_entries = load_index_file(self._dir)
        works: list[Work] = []
        project_root = Path(__file__).resolve().parents[2]

        for entry in index_entries.values():
            # 归档卡不进 Engine 派发队列（看板 loader 已过滤；store 须对齐）
            if entry.get("archived"):
                continue
            st = _state_from_str(entry["state"])
            if st is None:
                logger.warning(
                    "跳过未知状态卡: id=%s state=%r",
                    entry.get("id"),
                    entry.get("state"),
                )
                continue

            if state is not None and st is not state:
                continue

            executor_name = _strip_parenthetical(entry["executor"])
            role = self._registry.role_for_binding(executor_name) or ""
            executor_binding = "" if executor_name == UNKNOWN else executor_name

            rel_path = entry.get("path", "")
            abs_path = project_root / rel_path

            raw_state = entry.get("state", "")
            retry_count = _retry_count_from_state_str(str(raw_state or ""))

            work = Work(
                id=entry["id"],
                role=role,
                title=entry["title"],
                state=st,
                card_path=str(abs_path.resolve()),
                executor=executor_binding,
                dispatch=entry.get("dispatch", "engine"),
                type=entry.get("card_type", "task"),
                project=entry.get("project", ""),
                parent=entry.get("parent_card", "") or "",
                acceptance=entry.get("acceptance", "") or "",
                thread_id=entry.get("thread_id", ""),
                retry_count=retry_count,
            )
            works.append(work)
        return works

    def save_work(self, work: Work) -> None:
        """回写卡头「状态」行（原子替换）。

        只改 `>` 元数据行中的 `状态：X` 段；不动回写区 `**日期**：`。
        """
        if not work.card_path:
            logger.warning("save_work: work=%s 无 card_path，跳过回写", work.id)
            return
        path = Path(work.card_path)
        if not path.is_file():
            logger.warning("save_work: 卡文件不存在 %s", path)
            return
        text = path.read_text(encoding="utf-8")
        new_state_str = work.state.value
        # 打回 / 待分派重试：附首个问题（截断）；重试带 n/max 便于跨心跳恢复
        if work.state is State.REJECTED and work.problems:
            reason = work.problems[0][:40]
            new_state_str = f"打回（{reason}）"
        elif work.state is State.TODO and (work.problems or work.retry_count > 0):
            reason = (work.problems[0] if work.problems else "重试")[:32]
            if work.retry_count > 0:
                new_state_str = f"待分派（重试{work.retry_count}：{reason}）"
            else:
                new_state_str = f"待分派（{reason}）"

        try:
            new_text = _replace_state_in_metadata(text, new_state_str)
        except ValueError as exc:
            logger.warning("save_work: 未在卡头找到「状态」段 %s (%s)", path, exc)
            return
        # 原子写：tmp → rename
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        os.replace(tmp, path)
        logger.info("save_work: %s → 状态：%s", path.name, new_state_str)
        # 写卡后失效：重新加载索引以同步最新状态
        try:
            from server.board.loader import load_dispatch_cards
            load_dispatch_cards(self._dir)
        except Exception:
            logger.exception("save_work: 索引失效重扫失败（不影响回写成功）")

    def _parse_card_to_work(self, path: Path) -> Work | None:
        """解析单张任务卡 → Work 对象。"""
        from server.board.loader import parse_card  # noqa: PLC0415 — 避免循环导入

        item = parse_card(path)
        # 状态映射
        st = _state_from_str(item.state)
        if st is None:
            # 未知状态 → 跳过，禁止落入待分派被误派发
            logger.warning("跳过未知状态卡: path=%s state=%r", path, item.state)
            return None
        # 执行体 → 角色反查（卡头「执行体：X」）
        executor_name = _strip_parenthetical(item.executor)
        role = self._registry.role_for_binding(executor_name) or ""
        # T39：保留卡头执行体绑定名（未知/缺省 → 空串，回退角色决策）
        executor_binding = "" if executor_name == UNKNOWN else executor_name
        return Work(
            id=item.id,
            role=role,
            title=item.title,
            state=st,
            card_path=str(path.resolve()),
            executor=executor_binding,
            # T53：派发方式随卡头透传（manual 卡保持待分派，Engine 不自动拉）
            dispatch=item.dispatch or "engine",
            type=item.type,
            project=item.project,
            parent=item.parent or "",
            thread_id=item.thread_id,
            acceptance=(item.acceptance or "") if item.acceptance != "未知" else "",
            retry_count=_retry_count_from_state_str(item.state or ""),
        )


def _replace_state_in_metadata(text: str, new_state: str) -> str:
    """在 `>` 元数据行中替换「状态：X」段的值。

    只替换第一个匹配（卡头只有一行含「状态」）。
    如果找不到「状态：X」段，则抛出 ValueError 异常由调用方拦截。
    """
    lines = text.splitlines(keepends=True)
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(">"):
            if _STATE_PAIR_RE.search(line):
                lines[i] = _STATE_PAIR_RE.sub(
                    lambda m: m.group(1) + new_state,
                    line,
                    count=1,
                )
                replaced = True
                break
    if not replaced:
        raise ValueError("未在卡头元数据行中找到「状态」段")
    return "".join(lines)
