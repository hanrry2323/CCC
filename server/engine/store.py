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
import subprocess
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
    "作废": State.VOIDED,
}


def _branch_envelope_state(project_root: Path, entry: dict) -> str:
    """远端 ``codex/<slug>`` 分支卡文件状态（分支信封 = 终态权威之一）。

    磁盘 main 镜像在合入前永远旧值（待分派）；收单后 sidecar 按契约清除；
    AUTO 业务仓卡的真值在执行体 push 的 codex 分支卡文件里。
    分支不存在/读取失败返回空串（不覆盖现有判定，不阻断）。
    """
    raw_path = entry.get("path") or ""
    if not raw_path:
        return ""
    try:
        path = str(Path(raw_path).expanduser().resolve().relative_to(Path(project_root).expanduser().resolve()))
    except ValueError:
        path = str(raw_path).replace("\\", "/")
    stem = Path(path).stem.lower()
    branch = f"codex/{stem}"
    try:
        res = subprocess.run(
            ["git", "-C", str(project_root), "show", f"origin/{branch}:{path}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception:
        return ""
    if res.returncode != 0:
        return ""
    from server.board.card_header import parse_metadata

    try:
        meta = parse_metadata(res.stdout)
    except Exception:
        return ""
    state = (meta.get("状态") or "").strip()
    if base_state(state) in ("已回写", "已关闭", "打回", "作废"):
        return state
    return ""


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
    """卡驱动看板存储（P1-1）+ 运行时状态（主树干净化）。

    读 `docs/dispatch/*.md` 卡头元数据 → 构造 `Work`；
    `save_work` 在给定 ``log_dir`` 时写入运行时状态 sidecar（不写卡文件）；
    未给 ``log_dir``（测试）回退回写卡头「状态：X」行（原子替换）。

    Args:
        dispatch_dir: 任务卡目录（如 `docs/dispatch`）。
        registry: 执行体注册表（用于工具名 → 角色反查）。
        log_dir: 执行体日志目录（运行时状态落这里；None=legacy 卡文件写）。
    """

    def __init__(
        self,
        dispatch_dir: str | Path,
        registry: ExecutorRegistry,
        log_dir: str | Path | None = None,
    ) -> None:
        self._dir = Path(dispatch_dir)
        self._registry = registry
        self._log_dir = Path(log_dir) if log_dir else None

    def list_work(self, state: State | None = None) -> list[Work]:
        """走索引列出 work (扫描仅用于重建/校验)。"""
        from server.board.loader import load_dispatch_cards, load_index_file

        load_dispatch_cards(self._dir)

        index_entries = load_index_file(self._dir)
        from server.engine.runtime_state import read_card_state

        runtime = read_card_state(self._log_dir) if self._log_dir else {}
        works: list[Work] = []
        try:
            from server.git_sync import resolve_repo_root

            project_root = resolve_repo_root(self._dir)
        except Exception:
            project_root = Path(__file__).resolve().parents[2]

        for entry in index_entries.values():
            # 归档卡不进 Engine 派发队列（看板 loader 已过滤；store 须对齐）
            if entry.get("archived"):
                continue
            raw_state = entry.get("state", "")
            rt = runtime.get(entry["id"]) or {}
            # sidecar 状态在磁盘状态为「待分派」/「已回写」/「执行中」时参与判定。
            # 若磁盘状态是「已关闭」「打回」，忽略 sidecar 状态。
            if base_state(raw_state) in ("待分派", "已回写", "执行中") and rt.get("state"):
                raw_state = str(rt["state"])
            # 分支信封（2026-08-12 · 终态权威补齐）：磁盘 main 镜像未合入前永远旧值，
            # sidecar 收单后按契约清除 → 磁盘待分派会误重派、机审扫不到。
            # 远端 codex/<slug> 分支卡是执行体回写后的真值，合并进状态判定。
            if base_state(raw_state) in ("待分派", "执行中") and not rt.get("state"):
                branch_state = _branch_envelope_state(project_root, entry)
                if branch_state:
                    raw_state = branch_state
            st = _state_from_str(raw_state)
            if st is None:
                logger.warning(
                    "跳过未知状态卡: id=%s state=%r",
                    entry.get("id"),
                    raw_state,
                )
                continue

            if state is not None and st is not state:
                continue

            executor_name = _strip_parenthetical(entry["executor"])
            role = self._registry.role_for_binding(executor_name) or ""
            executor_binding = "" if executor_name == UNKNOWN else executor_name

            card_id = entry["id"]
            # work.id -> card_path 解析改为每次从磁盘索引重新匹配，避免改名后残留旧 card_path
            matched_path = None
            try:
                candidates = list(Path(self._dir).glob(f"**/*{card_id}*.md"))
                candidates = [c for c in candidates if not c.name.endswith(".tmp") and not c.name.endswith(".bak")]
                if candidates:
                    for c in candidates:
                        stem = c.stem.lower()
                        if (
                            stem == card_id.lower()
                            or stem.startswith(card_id.lower() + "-")
                            or stem.startswith(card_id.lower() + "_")
                        ):
                            matched_path = c
                            break
                    if not matched_path:
                        matched_path = candidates[0]
            except Exception:
                pass

            if matched_path:
                abs_path = matched_path.resolve()
            else:
                rel_path = entry.get("path", "")
                abs_path = project_root / rel_path

            retry_count = (
                int(rt.get("retry_count") or 0)
                if rt.get("retry_count") is not None
                else _retry_count_from_state_str(str(raw_state or ""))
            )
            reason = str(rt.get("reason") or "")[:200]

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
                depends_on=list(entry.get("depends_on") or []),
                acceptance=entry.get("acceptance", "") or "",
                thread_id=entry.get("thread_id", ""),
                retry_count=retry_count,
                problems=[reason] if reason else [],
            )
            works.append(work)
        return works

    def save_work(self, work: Work) -> None:
        """持久化 work 状态：有 log_dir → 运行时 sidecar（不写卡文件）；否则回写卡头。

        运行时模式只写 ``EXECUTOR_LOG_DIR/state/cards.jsonl``，主树卡文件保持 main 镜像。
        """
        if self._log_dir is not None:
            from server.engine.runtime_state import write_card_state

            write_card_state(
                self._log_dir,
                work.id,
                state=work.state.value,
                retry_count=work.retry_count,
                reason=work.problems[0] if work.problems else "",
            )
            logger.info("save_work(runtime): %s → %s", work.id, work.state.value)
            return
        if not work.card_path:
            logger.warning("save_work: work=%s 无 card_path，跳过回写", work.id)
            return
        path = Path(work.card_path)
        if not path.is_file():
            logger.warning("save_work: 卡文件不存在 %s", path)
            return
        text = path.read_text(encoding="utf-8")
        new_state_str = work.state.value
        # 打回 / 作废 / 待分派重试：附首个问题（截断）；重试带 n/max 便于跨心跳恢复
        if work.state is State.REJECTED and work.problems:
            reason = work.problems[0][:40]
            new_state_str = f"打回（{reason}）"
        elif work.state is State.VOIDED and work.problems:
            reason = work.problems[0][:40]
            new_state_str = f"作废（{reason}）"
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
        # 打回次数修复（统一化）：进入「打回」时递增卡头 打回次数：N（此前只读不写）
        if work.state is State.REJECTED:
            from server.board.card_header import bump_reject_count

            new_text = bump_reject_count(new_text)
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
            depends_on=list(item.depends_on),
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
