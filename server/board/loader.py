"""从任务卡文档解析看板派生数据（任务卡 = 唯一事实源）。

- 元数据块（`>` 行，`key：value` 以 `·` 分隔）→ 状态 / 项目 / 执行体 / 分派时间 / 派发方式。
- 项目：卡头「项目」字段优先；缺省从「关联」首段（冒号/空格前）推导，推导不出归「未分类」。
- 派发方式：卡头「派发」字段（manual|engine，缺省 engine）。
- 回写区（`## 回写区` 后 `**日期**：`）→ 回写时间。
- 字段缺失容错：标「未知」不崩溃；无显式打回次数按 0。

用法：
    from server.board.loader import parse_card, load_dispatch_cards

    item = parse_card("docs/dispatch/T2-engine-core.md")
    items = load_dispatch_cards("docs/dispatch")
"""

from __future__ import annotations

import logging
import os
import json
import re
from pathlib import Path

from server.board.models import UNCLASSIFIED, UNKNOWN, BoardItem, base_state, board_column, machine_audit_passed_text
from server.board.roles import normalize_tool
from server.board.card_header import CardHeader, parse_metadata, is_task_card_text

logger = logging.getLogger("ccc.board.loader")

# 回写区日期：`**日期**：YYYY-MM-DD`
_WRITTEN_RE = re.compile(r"\*\*日期\*\*\s*[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")

# 推导出的项目名不得含这些字符（长句/引号/括号 → 非项目前缀，归「未分类」）
_GARBLED_RE = re.compile(r"[「」『』【】\"'<>（）()]")

_parse_metadata = parse_metadata


def _strip_parenthetical(value: str) -> str:
    """取括号前部分（如 `INT-120（CCC 重构）` → `INT-120`）。"""
    return re.split(r"[（(]", value, maxsplit=1)[0].strip()


def _derive_project_from_related(related: str) -> str:
    """旧卡兼容：无「项目」字段时从「关联」首段推导项目名。

    推导规则（T53）：
    1. 取关联值首段（按 `：`/`:`/空格 切分）；
    2. 去括号（如 `INT-120（CCC 重构）` → `INT-120`）；
    3. 结果含引号/括号等非项目前缀字符、或为空/未知 → 「未分类」。

    例：`INT-120（CCC 重构）` → `INT-120`；`阶段 3 P1` → `阶段`；
        `新阶段「双壳可用 + 心智升级」` → 「未分类」。
    """
    if not related or related == UNKNOWN:
        return UNCLASSIFIED
    seg = re.split(r"[：:\s]", related, maxsplit=1)[0].strip()
    seg = _strip_parenthetical(seg)
    if not seg or seg == UNKNOWN or _GARBLED_RE.search(seg):
        return UNCLASSIFIED
    return seg


def _resolve_project(header: CardHeader) -> str:
    """项目名：卡头「项目」字段优先；缺省从「关联」首段推导。"""
    explicit = (header.project or "").strip()
    if explicit:
        return _strip_parenthetical(explicit)
    return _derive_project_from_related(header.related or UNKNOWN)


def _parse_written_at(text: str) -> str:
    """从回写区取 `**日期**：YYYY-MM-DD`。"""
    match = _WRITTEN_RE.search(text)
    return match.group(1) if match else UNKNOWN


def parse_card(path: Path | str) -> BoardItem:
    """解析单张任务卡；字段缺失容错标「未知」。"""
    text = Path(path).read_text(encoding="utf-8")
    header = CardHeader.from_text(text, fallback_id=Path(path).stem)

    p = Path(path)
    is_archived = "docs/archive" in p.as_posix() or "docs/archive" in p.resolve().as_posix()

    return BoardItem(
        id=header.id,
        title=header.title,
        state=header.state,
        project=_resolve_project(header),
        executor=_strip_parenthetical(header.executor),
        dispatched_at=header.dispatched_at,
        written_at=_parse_written_at(text),
        reject_count=header.reject_count,
        dispatch=header.dispatch,
        type=header.card_type,
        parent=header.parent,
        thread_id=header.session,
        acceptance=normalize_tool(_strip_parenthetical(header.acceptance)) or UNKNOWN,
        archived=is_archived,
        machine_audit_passed=machine_audit_passed_text(text),
    )


def _is_task_card(path: Path) -> bool:
    """是否任务卡：行首含 `# 任务卡` 卡头标题；T-mapping.md 等说明文档跳过。"""
    try:
        return is_task_card_text(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, OSError) as exc:
        logger.warning("跳过无法读取的文件 %s: %s", path, exc)
        return False


def scan_dispatch_files(directory: Path | str) -> list[Path]:
    """扫描任务卡文件：根目录平铺（旧卡）+ 一层子目录（`<prefix>/` 下新卡）。

    T54 规则：旧卡（根 `T*.md`）与 `<prefix>/` 子目录新卡共存；只认含 `# 任务卡`
    卡头标题的 .md，T-mapping.md 等说明文档不参与。目录不存在返回空。
    """
    d = Path(directory)
    if not d.is_dir():
        return []
    files: list[Path] = []
    for p in sorted(d.glob("*.md")):
        if _is_task_card(p):
            files.append(p)
    for p in sorted(d.glob("[!.]*/[!.]*.md")):
        if _is_task_card(p):
            files.append(p)
    return files


def get_archive_dir(dispatch_dir: Path | str) -> Path:
    """由任务卡目录推导归档目录（docs/archive/ccc-tasks）。"""
    d = Path(dispatch_dir)
    return d.parent / "archive" / "ccc-tasks"


def scan_archive_files(archive_dir: Path) -> list[Path]:
    """扫描归档目录下的任务卡（docs/archive/ccc-tasks/<project>/<filename>.md）。"""
    if not archive_dir.is_dir():
        return []
    files: list[Path] = []
    for p in sorted(archive_dir.glob("[!.]*/[!.]*.md")):
        if _is_task_card(p):
            files.append(p)
    for p in sorted(archive_dir.glob("*.md")):
        if _is_task_card(p):
            files.append(p)
    return files


def load_dispatch_cards(directory: Path | str, include_archived: bool = False) -> list[BoardItem]:
    """扫描目录下全部任务卡（使用增量索引机制，只重扫变化卡）。"""
    return load_dispatch_cards_incremental(directory, include_archived=include_archived)


def get_index_path(dispatch_dir: Path | str | None = None) -> Path:
    if "PYTEST_CURRENT_TEST" in os.environ and dispatch_dir is not None:
        return Path(dispatch_dir) / "cards.index.jsonl"

    raw = os.environ.get("CCC_DATA_DIR") or os.environ.get("DATA_DIR")
    if raw:
        base = Path(raw).expanduser().resolve()
        return base / "cards" / "cards.index.jsonl"

    base = Path(__file__).resolve().parents[2] / "data"
    return base / "cards" / "cards.index.jsonl"


def _derive_card_type(path: Path) -> str:
    from server.board.validate import NEW_CARD_RE, OLD_CARD_RE
    stem = path.stem
    if NEW_CARD_RE.match(stem):
        return "new"
    if OLD_CARD_RE.match(stem):
        return "old"
    return "other"


def build_index_entry(path: Path, item: BoardItem, mtime: float) -> dict:
    ctype = _derive_card_type(path)
    parent_dir = path.parent
    if parent_dir.name == "dispatch" or parent_dir.name == "":
        parent = ""
    else:
        parent = parent_dir.name

    closed_at = UNKNOWN
    if base_state(item.state) == "已关闭":
        closed_at = item.written_at

    project_root = Path(__file__).resolve().parents[2]
    try:
        repo_path = str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        repo_path = str(path)

    return {
        "id": item.id,
        "project": item.project,
        "type": ctype,
        "parent": parent,
        "state": item.state,
        "executor": item.executor,
        "dispatched_at": item.dispatched_at,
        "written_at": item.written_at,
        "closed_at": closed_at,
        "reject_count": item.reject_count,
        "title": item.title,
        "path": repo_path,
        "mtime": mtime,
        "dispatch": item.dispatch,
        "card_type": item.type,
        "parent_card": item.parent,
        "thread_id": item.thread_id,
        "acceptance": item.acceptance,
        "archived": item.archived,
        "machine_audit_passed": item.machine_audit_passed,
        "board_column": board_column(item.state, item.machine_audit_passed),
    }


def load_index_file(dispatch_dir: Path | str | None = None) -> dict[str, dict]:
    index_path = get_index_path(dispatch_dir)
    if not index_path.is_file():
        return {}

    entries: dict[str, dict] = {}
    try:
        with open(index_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "id" in data:
                        entries[data["id"]] = data
                except Exception:
                    continue
    except Exception:
        pass
    return entries


def save_index_file(entries: dict[str, dict], dispatch_dir: Path | str | None = None) -> None:
    index_path = get_index_path(dispatch_dir)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_entries = sorted(entries.values(), key=lambda x: x["id"])
    tmp_path = index_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            for entry in sorted_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        tmp_path.replace(index_path)
    except Exception:
        if tmp_path.is_file():
            tmp_path.unlink()


def load_dispatch_cards_incremental(directory: Path | str, include_archived: bool = False) -> list[BoardItem]:
    """增量扫描任务卡：按 mtime 检测变化卡只重扫，写回索引并返回全部卡。"""
    dispatch_dir = Path(directory)
    index_entries = load_index_file(dispatch_dir)

    index_by_path: dict[str, dict] = {}
    for entry in index_entries.values():
        if "path" in entry:
            index_by_path[entry["path"]] = entry

    disk_files = scan_dispatch_files(dispatch_dir)
    archive_dir = get_archive_dir(dispatch_dir)
    archive_files = scan_archive_files(archive_dir)

    all_files = disk_files + archive_files
    project_root = Path(__file__).resolve().parents[2]

    updated_entries: dict[str, dict] = {}
    items: list[BoardItem] = []
    updated = False

    for path in all_files:
        try:
            repo_path = str(path.resolve().relative_to(project_root.resolve()))
        except ValueError:
            repo_path = str(path)

        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue

        entry = index_by_path.get(repo_path)
        # 缺 machine_audit_passed 的旧索引视为失效（M3：否则机审通过卡一直停在「机审」列）
        cache_ok = (
            entry is not None
            and entry.get("mtime") == mtime
            and "machine_audit_passed" in entry
        )
        if cache_ok:
            item = BoardItem(
                id=entry["id"],
                title=entry["title"],
                state=entry["state"],
                project=entry["project"],
                executor=entry["executor"],
                dispatched_at=entry["dispatched_at"],
                written_at=entry["written_at"],
                reject_count=entry["reject_count"],
                dispatch=entry.get("dispatch", "engine"),
                type=entry.get("card_type", "task"),
                parent=entry.get("parent_card", ""),
                thread_id=entry.get("thread_id", ""),
                acceptance=entry.get("acceptance", UNKNOWN),
                archived=entry.get("archived", False),
                machine_audit_passed=bool(entry.get("machine_audit_passed", False)),
            )
            items.append(item)
            updated_entries[entry["id"]] = entry
        else:
            try:
                item = parse_card(path)
                new_entry = build_index_entry(path, item, mtime)
                items.append(item)
                updated_entries[item.id] = new_entry
                updated = True
            except Exception:
                logger.exception("解析任务卡失败，保留旧索引项: %s", path)
                if entry is not None:
                    # 保留旧索引，避免静默丢卡并覆写索引
                    item = BoardItem(
                        id=entry["id"],
                        title=entry["title"],
                        state=entry["state"],
                        project=entry["project"],
                        executor=entry["executor"],
                        dispatched_at=entry["dispatched_at"],
                        written_at=entry["written_at"],
                        reject_count=entry["reject_count"],
                        dispatch=entry.get("dispatch", "engine"),
                        type=entry.get("card_type", "task"),
                        parent=entry.get("parent_card", ""),
                        thread_id=entry.get("thread_id", ""),
                        acceptance=entry.get("acceptance", UNKNOWN),
                        archived=entry.get("archived", False),
                        machine_audit_passed=bool(entry.get("machine_audit_passed", False)),
                    )
                    items.append(item)
                    updated_entries[entry["id"]] = entry
                continue

    if len(updated_entries) != len(index_entries) or updated:
        save_index_file(updated_entries, dispatch_dir)

    if not include_archived:
        items = [i for i in items if not i.archived]

    return derive_epic_states_and_progress(items)


def derive_epic_states_and_progress(items: list[BoardItem]) -> list[BoardItem]:
    """线路图/看板按 epic 聚合子卡进度（已完成/总子卡）；epic 状态由子卡派生（全部关闭+目标达成→待验收）。"""
    epic_items = [item for item in items if item.type == "epic"]
    if not epic_items:
        return items

    epic_to_children: dict[str, list[BoardItem]] = {epic.id: [] for epic in epic_items}
    for item in items:
        if item.type == "task" and item.parent in epic_to_children:
            epic_to_children[item.parent].append(item)

    derived_items = []
    for item in items:
        if item.type == "epic":
            children = epic_to_children.get(item.id, [])
            if children:
                total = len(children)
                closed = sum(1 for child in children if base_state(child.state) == "已关闭")
                progress_str = f"{closed}/{total}"

                if closed == total:
                    derived_state = "已回写"
                else:
                    has_active = any(base_state(child.state) in ("执行中", "已回写", "打回") for child in children)
                    if has_active:
                        derived_state = "执行中"
                    else:
                        derived_state = "待分派"

                new_item = BoardItem(
                    id=item.id,
                    title=f"{item.title} ({progress_str})",
                    state=derived_state,
                    project=item.project,
                    executor=item.executor,
                    dispatched_at=item.dispatched_at,
                    written_at=item.written_at,
                    reject_count=item.reject_count,
                    dispatch=item.dispatch,
                    type=item.type,
                    parent=item.parent,
                    progress=progress_str,
                    thread_id=item.thread_id,
                    acceptance=item.acceptance,
                )
                derived_items.append(new_item)
            else:
                derived_items.append(item)
        else:
            derived_items.append(item)

    return derived_items
