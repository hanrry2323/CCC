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
from server.board.models import base_state
from server.engine.dispatch import ExecutorRegistry
from server.engine.task import State, Work

logger = logging.getLogger("ccc.engine.store")

# 卡头「状态：X」段匹配（用于回写时定位替换）
# lookahead 保留 `·` 前的空格，不消费
_STATE_PAIR_RE = re.compile(r"(状态\s*[:：]\s*)([^\n·]+?)(?=\s*·|\s*$)")

# 卡头状态字符串 → State 枚举
_STR_TO_STATE: dict[str, State] = {
    "待分派": State.TODO,
    "执行中": State.RUNNING,
    "已回写": State.DONE,
    "已关闭": State.CLOSED,
    "打回": State.REJECTED,
}


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
        """扫描任务卡目录 → 解析卡头 → 构造 Work 列表。

        state=None 返回全部；指定状态则过滤。
        无法解析状态或执行体不匹配注册表的卡仍返回（role 可能为空，decide() 会跳过）。
        """
        works: list[Work] = []
        if not self._dir.is_dir():
            return works
        for path in sorted(self._dir.glob("*.md")):
            try:
                work = self._parse_card_to_work(path)
            except OSError:
                continue
            except Exception:
                logger.exception("解析任务卡失败: %s", path)
                continue
            if work is None:
                continue
            if state is None or work.state is state:
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
        # 打回时附首个问题（截断）作为状态行注释
        if work.state is State.REJECTED and work.problems:
            reason = work.problems[0][:40]
            new_state_str = f"打回（{reason}）"

        new_text = _replace_state_in_metadata(text, new_state_str)
        if new_text == text:
            logger.warning("save_work: 未在卡头找到「状态」段 %s", path)
            return
        # 原子写：tmp → rename
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        os.replace(tmp, path)
        logger.info("save_work: %s → 状态：%s", path.name, new_state_str)

    def _parse_card_to_work(self, path: Path) -> Work | None:
        """解析单张任务卡 → Work 对象。"""
        from server.board.loader import parse_card  # noqa: PLC0415 — 避免循环导入

        item = parse_card(path)
        # 状态映射
        st = _state_from_str(item.state)
        if st is None:
            # 未知状态（如「未知」）→ 默认待分派，让 Engine 能看到
            st = State.TODO
        # 执行体 → 角色反查
        executor_name = _strip_parenthetical(item.executor)
        role = self._registry.role_for_binding(executor_name) or ""
        return Work(
            id=item.id,
            role=role,
            title=item.title,
            state=st,
            card_path=str(path.resolve()),
        )


def _replace_state_in_metadata(text: str, new_state: str) -> str:
    """在 `>` 元数据行中替换「状态：X」段的值。

    只替换第一个匹配（卡头只有一行含「状态」）。
    """
    return _STATE_PAIR_RE.sub(
        lambda m: m.group(1) + new_state,
        text,
        count=1,
    )
