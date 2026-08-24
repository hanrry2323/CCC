"""任务卡卡头校验器（2026-08-04 新增，填补「文件即事实源但无机器校验」缺口）。

扫描 ``docs/dispatch``（根平铺旧卡 + 一层子目录新卡），逐卡校验：

- 卡头 ``>`` 元数据行必含：关联 / 执行体 / 状态 / 日期；
- 状态值必须是五态之一（待分派 / 执行中 / 已回写 / 已关闭 / 打回）；
- 非「待分派」状态必须存在回写区（``## 回写区`` 且含执行体行）；
- 卡文件必须存在 ``## 目标`` 与 ``## 验收标准`` 节（格式最低要求）。

T54 命名规则（新卡强制，旧卡仅提示）：
- 新卡文件名 ``<前缀><三位序号>-<slug>.md`` 且必须位于 ``docs/dispatch/<前缀>/`` 子目录；
- 前缀必须在项目前缀表（``PREFIXES``，源自 ``docs/projects/registry.yaml``）内；子目录名必须等于前缀；
- ``<前缀><NNN>`` 全目录唯一（编号跨项目唯一）；
- 旧卡（根目录 ``T*.md``）零拦截：仅提示迁移建议，不阻断；
- 非任务卡文档（无 ``# 任务卡`` 卡头，如 ``T-mapping.md``）不参与校验。

用法::

    $PYTHON_BIN -m server.board.validate [dispatch_dir]

返回码：0 = 无 error 问题（warn 提示不影响退出码）；1 = 存在 error 问题。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from server.board.models import PREFIXES, FORBIDDEN_CARD_PREFIXES, base_state, BoardItem
from server.board.roles import acceptance_issue
from server.board.card_header import is_task_card_text, parse_metadata, card_id

VALID_STATES = frozenset({"待分派", "执行中", "已回写", "已关闭", "打回", "作废"})
# 新卡强制含「验收」；交叉对由 roles.acceptance_issue 校验
REQUIRED_HEADER_KEYS = ("关联", "执行体", "状态", "日期")
REQUIRED_HEADER_KEYS_NEW = ("关联", "执行体", "验收", "状态", "日期")

# T54 新卡文件名：`<前缀><三位序号>-<slug>.md`（前缀 2-4 位小写字母；slug 小写字母数字 + 单连字符）
NEW_CARD_RE = re.compile(r"^(?P<prefix>[a-z]{2,4})(?P<num>\d{3})-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$")
# 旧卡：`T<N>-...`（根目录平铺）
OLD_CARD_RE = re.compile(r"^T\d")


@dataclass
class CardIssue:
    """单张卡的一个问题。"""

    card_id: str
    path: str
    reason: str
    severity: str = "error"  # error=阻断（退出码 1）；warn=提示（退出码 0）


def _has_card_title(path: Path) -> bool:
    """是否任务卡（行首含 ``# 任务卡`` 卡头标题）；排除 T-mapping.md 等说明文档。"""
    return is_task_card_text(path.read_text(encoding="utf-8"))


def _header_metadata(card: Path) -> dict[str, str]:
    """用 loader 同款解析合并全部 ``>`` 行 → ``key: value`` 字典。

    历史卡把 关联/执行体/状态/日期 分布在多个 ``>`` 行，只查首行会误报；
    与 `server/board/loader._parse_metadata` 一致语义合并解析。
    """
    return parse_metadata(card.read_text(encoding="utf-8"))


def _body_has(card: Path, marker: str) -> bool:
    text = card.read_text(encoding="utf-8")
    return marker in text


def _has_real_annotation(card: Path) -> bool:
    """卡含 `## 人工批注` 且内容非模板占位（老板写了真实修订指示）。"""
    try:
        text = card.read_text(encoding="utf-8")
    except OSError:
        return False
    m = re.search(r"^##\s*人工批注\s*$", text, flags=re.MULTILINE)
    if not m:
        return False
    tail = text[m.end() :]
    nxt = re.search(r"^##\s", tail, flags=re.MULTILINE)
    content = (tail[: nxt.start()] if nxt else tail).strip()
    if not content:
        return False
    return "老板对打回卡/审核的批注意见写这里" not in content


def _is_accepted(path: Path) -> bool | None:
    """读卡正文 `## 验收区` 后 20 行内含 `✅` 或 `判定：通过`。

    无 `## 验收区` 节 → 返回 None（历史旧流程卡，不适用验收标记校验）；
    有节但无通过标记 → False；有通过标记 → True。
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return False

    idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("## 验收区"):
            idx = i
            break

    if idx == -1:
        return None

    # 检查后 20 行
    for j in range(idx + 1, min(idx + 21, len(lines))):
        line = lines[j]
        if "✅" in line or "判定：通过" in line:
            return True
    return False


def _classify_card(path: Path) -> tuple[str, str, str]:
    """按文件名分类：``(类型, 前缀, 编号)``。类型: new|old|other。"""
    stem = path.stem
    m = NEW_CARD_RE.match(stem)
    if m:
        return "new", m.group("prefix"), m.group("num")
    if OLD_CARD_RE.match(stem):
        return "old", "", ""
    return "other", "", ""


def _header_card_id(card: Path) -> str:
    """取卡头 ``# 任务卡 <ID>`` 的 ID（停在 ``·`` 或空白处）；未匹配返回空。

    旧卡两种写法并存：``# 任务卡 T1-server-skeleton``（含 slug）与
    ``# 任务卡 T52 · 自动化基建``（仅编号），统一取 ``T<N>`` 前缀即可；
    新卡取 ``<prefix><NNN>``（可带 ``-<slug>``，数字部分一致）。
    """
    return card_id(card.read_text(encoding="utf-8"))


def _header_number(card: Path) -> str:
    """取卡头 ID 的数字部分（``T52`` → ``52``；``ccc064`` / ``ccc064-foo`` → ``064``）。"""
    m = re.search(r"(\d+)", _header_card_id(card))
    return m.group(1) if m else ""


def _scan_cards(dispatch_dir: Path) -> list[tuple[Path, str]]:
    """扫描任务卡：根目录平铺（旧卡）+ 一层子目录（``<prefix>/`` 下新卡）。

    只认带 ``# 任务卡`` 卡头标题的 .md；``T-mapping.md`` 等说明文档被跳过。
    返回 ``(path, location)``，location ∈ root | subdir。
    """
    cards: list[tuple[Path, str]] = []
    if not dispatch_dir.is_dir():
        return cards
    for p in sorted(dispatch_dir.glob("*.md")):
        if _has_card_title(p):
            cards.append((p, "root"))
    for p in sorted(dispatch_dir.glob("[!.]*/[!.]*.md")):
        if _has_card_title(p):
            cards.append((p, "subdir"))
    return cards


def _validate_new_naming(
    path: Path,
    loc: str,
    prefix: str,
    num: str,
) -> list[CardIssue]:
    """新规则卡命名校验（错误命名即拦截）。"""
    issues: list[CardIssue] = []
    card_id = path.stem
    name = path.name
    m = NEW_CARD_RE.match(path.stem)
    if not m:
        issues.append(
            CardIssue(card_id, str(path), f"子目录卡文件名不符合新命名规则 <前缀><三位序号>-<slug>.md: {name}")
        )
        return issues
    prefix, num, slug = m.group("prefix"), m.group("num"), m.group("slug")
    if prefix in FORBIDDEN_CARD_PREFIXES:
        issues.append(
            CardIssue(
                card_id,
                str(path),
                f"前缀 {prefix!r} 禁止走 CCC（QuantHive 独立轨道，不得 Engine 出卡/派发）",
            )
        )
    elif prefix not in PREFIXES:
        issues.append(CardIssue(card_id, str(path), f"未知前缀 {prefix!r}（合法前缀: {sorted(PREFIXES)}）"))
    if loc != "subdir":
        issues.append(CardIssue(card_id, str(path), f"新规则卡 {card_id} 必须位于子目录 {prefix}/ 下"))
    elif path.parent.name != prefix:
        issues.append(
            CardIssue(card_id, str(path), f"新规则卡 {card_id} 所在子目录 {path.parent.name!r} 与前缀 {prefix!r} 不符")
        )
    # 卡头编号与文件名一致（防复制卡只改文件名不改卡头）
    hdr_id = _header_card_id(path)
    hdr_num = _header_number(path)
    if hdr_num and hdr_num != num:
        issues.append(CardIssue(card_id, str(path), f"卡头编号 {hdr_id} 与文件名 {card_id} 不一致"))
    return issues


def validate_cards(dispatch_dir: str | Path) -> list[CardIssue]:
    """校验目录下全部任务卡，返回问题清单（error 空 = 门禁通过，warn 仅提示）。

    T52 增强（出卡门禁）：
    - 编号一致性：卡头 ``# 任务卡 T<N>`` 的数字前缀与文件名 ``T<N>-...`` 必须一致
      （防止文件改名/复制后卡头编号错乱）；
    - 编号唯一：卡头 ID 重复（同编号两张卡，如复制卡只改文件名不改卡头）报重。
    T54 增强（命名规则）：
    - 新卡必须 ``<前缀><NNN>-<slug>.md`` 且位于对应子目录；编号跨项目唯一；
    - 旧卡（根目录 ``T*.md``）仅提示不拦截；非任务卡文档（如 T-mapping.md）跳过。
    注：R/X 变体卡（``T1`` 与 ``T1-R-...``）数字前缀允许共存，按卡头 ID 判重。
    """
    issues: list[CardIssue] = []
    d = Path(dispatch_dir)
    if not d.is_dir():
        return [CardIssue("?", str(d), "目录不存在")]
    cards = _scan_cards(d)

    # 方案链编号保护：统一走共享保留表（出卡/校验单一事实源，2026-08-12）
    from server.board.plan_reservations import plan_reserved_card_titles, plan_reserved_ids

    plan_reservations = plan_reserved_card_titles()
    reserved_ids = plan_reserved_ids()

    def _free_number_hint(prefix: str) -> str:
        try:
            taken = set()
            for _path, _loc in cards:
                _cid = _path.name.split(".")[0]
                _m = re.fullmatch(r"([a-z]{2,4})(\d{3})", _cid.lower())
                if _m and _m.group(1) == prefix:
                    taken.add(int(_m.group(2)))
            for _n in range(1, 1000):
                if _n not in taken and _n not in reserved_ids.get(prefix, set()):
                    return f"{prefix}{_n:03d}"
        except Exception:
            pass
        return ""

    from server.board.loader import parse_card

    all_items: dict[Path, BoardItem] = {}
    id_to_item: dict[str, BoardItem] = {}
    for path, _ in cards:
        try:
            item = parse_card(path)
            all_items[path.resolve()] = item
            id_to_item[item.id] = item
        except Exception:
            pass

    # 编号唯一：新卡按 <前缀><NNN> 判重；旧卡按卡头 ID 判重（R/X 变体卡卡头 ID 不同，不误伤）
    new_by_id: dict[str, list[Path]] = {}
    old_by_hdr: dict[str, list[Path]] = {}
    for path, _loc in cards:
        ctype, prefix, num = _classify_card(path)
        if ctype == "new":
            new_by_id.setdefault(prefix + num, []).append(path)
        else:
            hdr_id = _header_card_id(path)
            if hdr_id:
                old_by_hdr.setdefault(hdr_id, []).append(path)
    dup_paths = set()
    for cid, dupes in new_by_id.items():
        if len(dupes) > 1:
            dup_paths.update(p.resolve() for p in dupes)
            for card in dupes[1:]:
                issues.append(
                    CardIssue(card.stem, str(card), f"新卡编号 {cid} 重复（与 {dupes[0].name} 冲突，编号跨项目唯一）")
                )
    for hdr_id, dupes in old_by_hdr.items():
        if len(dupes) > 1:
            for card in dupes[1:]:
                issues.append(
                    CardIssue(card.stem, str(card), f"编号 {hdr_id} 重复（与 {dupes[0].name} 冲突，编号必须唯一）")
                )

    for path, loc in cards:
        card_id = path.name.split(".")[0]
        ctype, prefix, num = _classify_card(path)
        if ctype == "new":
            naming_issues = _validate_new_naming(path, loc, prefix, num)
            issues.extend(naming_issues)
            # 方案链编号保护 (Step 5)：仅对命名合规、非重复、未关闭的新卡生效；
            # 关联含任何合法 <prefix>-plan-<NNN> 即视为已关联（旧卡标题格式不要求）
            if not naming_issues and path.resolve() not in dup_paths:
                card_state = _header_metadata(path).get("状态", "")
                if "已关闭" in card_state or "作废" in card_state:
                    pass
                else:
                    card_id_full = (prefix + num).lower()
                    if card_id_full in plan_reservations:
                        plan_title = plan_reservations[card_id_full]
                        meta = _header_metadata(path)
                        related = meta.get("关联", "")
                        if not re.search(r"[a-z]{2,4}-plan-\d{3}", related):
                            free_hint = _free_number_hint(prefix)
                            hint = f"可用编号示例：{free_hint}；" if free_hint else ""
                            issues.append(
                                CardIssue(
                                    card_id,
                                    str(path),
                                    f"方案编号保护冲突：卡片 {card_id} 未在卡头「关联」中声明任何合法方案编号（<prefix>-plan-<NNN>），但该编号已被方案 {plan_title!r} 占用。{hint}请显式指定其他编号（附加卡用 `--id`），禁止吃掉方案链编号空间。",
                                )
                            )
        elif ctype == "old":
            # 旧卡零拦截：仅提示迁移建议（T54 红线 2：旧卡不批量重命名，保持 git 历史）
            issues.append(
                CardIssue(
                    card_id,
                    str(path),
                    "旧卡（T 前缀）保持原名不迁移；新卡请用 <前缀><NNN>-<slug>.md 放 <前缀>/ 子目录（见 T-mapping.md）",
                    severity="warn",
                )
            )
            if loc == "subdir":
                issues.append(
                    CardIssue(
                        card_id,
                        str(path),
                        "旧卡样式文件位于子目录（旧卡应留在根目录；子目录只放新规则卡）",
                        severity="warn",
                    )
                )
        else:
            if loc == "subdir":
                issues.append(
                    CardIssue(
                        card_id, str(path), f"子目录卡文件名不符合新命名规则 <前缀><三位序号>-<slug>.md: {path.name}"
                    )
                )

        meta = _header_metadata(path)
        if not meta:
            issues.append(CardIssue(card_id, str(path), "缺少卡头元数据行（> 且含 key：value）"))
            continue

        # 禁止自造卡头字段（如 "批准"）——卡头字段定死，见 DOC-PROTOCOL §2.3。
        # 豁免（ccc072）：approve-merge 人审节点③（scripts/approve-merge.sh close_card）
        # 在每张卡关闭时会于卡头有意盖「> 批准：老板合入批准」章，属平台设计而非自造
        # 字段；故 base_state=「已关闭」的卡豁免「批准」键检查，否则每张新合并卡瞬间
        # 毒化所属项目出卡校验通道（tst004/ccc068/xy059 实证）。未关闭卡的「批准」键
        # 仍严格报错；「审批/review/approval」无 close_card 盖章设计，仍全态报错。
        approval_exempt = base_state(meta.get("状态", "")) == "已关闭"
        FORBIDDEN_HEADER_KEYS = {"批准", "审批", "review", "approval"}
        for forbidden in FORBIDDEN_HEADER_KEYS:
            if forbidden in meta and not (forbidden == "批准" and approval_exempt):
                issues.append(
                    CardIssue(card_id, str(path), f"卡头禁止自造字段「{forbidden}」——卡头字段定死（DOC-PROTOCOL §2.3），「合入批准」是人审动作不是卡头字段")
                )

        # Check epic/task specific rules
        type_raw = meta.get("类型")
        if type_raw:
            type_val = type_raw.strip().lower()
            if type_val not in ("epic", "task"):
                issues.append(CardIssue(card_id, str(path), f"类型值非法: {type_raw!r}（合法=epic|task）"))

        item = all_items.get(path.resolve())
        if item:
            if item.type == "epic":
                if item.parent:
                    issues.append(CardIssue(item.id, str(path), f"Epic 卡片不能指定父卡: {item.parent}"))
            elif item.type == "task":
                if item.parent:
                    parent_item = id_to_item.get(item.parent)
                    if not parent_item:
                        issues.append(CardIssue(item.id, str(path), f"父卡 {item.parent} 不存在"))
                    elif parent_item.project != item.project:
                        issues.append(
                            CardIssue(
                                item.id,
                                str(path),
                                f"父卡 {item.parent} 的项目 ({parent_item.project}) 与当前卡片项目 ({item.project}) 不一致",
                            )
                        )

        missing = [k for k in REQUIRED_HEADER_KEYS if not meta.get(k, "").strip()]
        if missing:
            issues.append(CardIssue(card_id, str(path), f"卡头缺字段: {missing}"))
        state_raw = meta.get("状态", "")
        base = base_state(state_raw)
        # 自验收：新卡 error；旧卡未关闭 warn（历史 Codex 验收不阻断）
        exe_raw = meta.get("执行体", "")
        acc_raw = meta.get("验收", "")
        if ctype == "new":
            miss_new = [k for k in REQUIRED_HEADER_KEYS_NEW if not meta.get(k, "").strip()]
            if miss_new:
                issues.append(CardIssue(card_id, str(path), f"新卡卡头缺字段: {miss_new}"))
            issue = acceptance_issue(exe_raw, acc_raw)
            if issue:
                from server.board.roles import FORBIDDEN_ACCEPTORS, normalize_tool

                acc = normalize_tool(acc_raw)
                if acc in FORBIDDEN_ACCEPTORS:
                    # 禁止席（Codex/Cursor）任何时候都 error
                    issues.append(CardIssue(card_id, str(path), issue))
                else:
                    # 自验收（2026-08-07 起）：交叉不匹配 → 提示不阻断
                    # （存量卡与规则切换日卡仍交叉，历史验收席可继续工作）
                    issues.append(
                        CardIssue(
                            card_id,
                            str(path),
                            f"{issue}（2026-08-07 起自验收：谁开发谁验收；历史交叉验收不阻断）",
                            severity="warn",
                        )
                    )
        elif base not in ("已关闭",) and acc_raw.strip():
            issue = acceptance_issue(exe_raw, acc_raw)
            if issue:
                issues.append(
                    CardIssue(
                        card_id,
                        str(path),
                        f"{issue}（旧卡提示：新卡须自验收=执行体同工具；Codex/Cursor 已取消验收资格）",
                        severity="warn",
                    )
                )
        if base not in VALID_STATES:
            issues.append(CardIssue(card_id, str(path), f"状态值非法: {state_raw!r}（合法={sorted(VALID_STATES)}）"))

        # 卡头「状态」字段与实际（打回/已关闭/待分派等）一致性强校验 (Task 4)
        # 三态：None=无验收区节（历史旧流程卡豁免）；True=已通过；False=有节无通过标记
        accepted = _is_accepted(path)
        if base == "已关闭" and accepted is False:
            issues.append(
                CardIssue(
                    card_id,
                    str(path),
                    "卡头声明状态为 '已关闭'，但验收区无 ✅/判定：通过 标记",
                )
            )
        if accepted is True and base != "已关闭":
            issues.append(
                CardIssue(
                    card_id,
                    str(path),
                    f"卡片实际已通过验收，但当前卡头状态为 {base!r}（期望：'已关闭'）",
                )
            )
        if base == "打回" and accepted is True:
            issues.append(
                CardIssue(
                    card_id,
                    str(path),
                    "卡片实际已通过验收，但当前卡头状态为 '打回'（冲突，已被验收的卡不能是打回状态）",
                )
            )
        if base in ("已回写", "已关闭", "打回") and not _body_has(path, "## 回写区"):
            issues.append(CardIssue(card_id, str(path), f"状态 {base} 但缺少 ## 回写区"))
        if base in ("已回写", "已关闭") and _has_real_annotation(path) and not _body_has(path, "## 批注落实"):
            issues.append(
                CardIssue(
                    card_id,
                    str(path),
                    "卡含 ## 人工批注（老板最高开发指令），但回写区缺 ## 批注落实"
                    "（执行体须说明批注如何落实；未落实=机审不通过）",
                )
            )
        if not _body_has(path, "## 目标"):
            issues.append(CardIssue(card_id, str(path), "缺少 ## 目标"))
        if not _body_has(path, "## 验收标准"):
            issues.append(CardIssue(card_id, str(path), "缺少 ## 验收标准"))

    # 如果存在阻断性错误，跳过索引对账以防连带报错
    if any(i.severity == "error" for i in issues):
        return issues

    # 对账索引 vs 磁盘文件
    try:
        from server.board.loader import load_index_file, parse_card, get_index_path, load_dispatch_cards

        index_path = get_index_path(d)
        if not index_path.is_file():
            load_dispatch_cards(d)

        index_entries = load_index_file(d)

        # 1. Check disk vs index
        disk_ids = set()
        project_root = Path(__file__).resolve().parents[2]

        for path, _loc in cards:
            try:
                item = parse_card(path)
            except Exception:
                continue

            disk_ids.add(item.id)

            try:
                repo_path = str(path.resolve().relative_to(project_root.resolve()))
            except ValueError:
                repo_path = str(path)

            if item.id not in index_entries:
                issues.append(
                    CardIssue(
                        card_id=item.id,
                        path=str(path),
                        reason=f"索引缺失：卡片 {item.id} 在磁盘上存在，但未在索引中找到",
                        severity="error",
                    )
                )
                continue

            entry = index_entries[item.id]
            if entry.get("path") != repo_path:
                issues.append(
                    CardIssue(
                        card_id=item.id,
                        path=str(path),
                        reason=f"路径不一致：索引路径为 {entry.get('path')}，实际路径为 {repo_path}",
                        severity="error",
                    )
                )

            # Check fields
            mismatches = []
            if entry.get("title") != item.title:
                mismatches.append(f"标题不一致: 索引='{entry.get('title')}', 实际='{item.title}'")
            if entry.get("state") != item.state:
                mismatches.append(f"状态不一致: 索引='{entry.get('state')}', 实际='{item.state}'")
            if entry.get("project") != item.project:
                mismatches.append(f"项目不一致: 索引='{entry.get('project')}', 实际='{item.project}'")
            if entry.get("executor") != item.executor:
                mismatches.append(f"执行体不一致: 索引='{entry.get('executor')}', 实际='{item.executor}'")
            if entry.get("dispatched_at") != item.dispatched_at:
                mismatches.append(f"分派时间不一致: 索引='{entry.get('dispatched_at')}', 实际='{item.dispatched_at}'")
            if entry.get("written_at") != item.written_at:
                mismatches.append(f"回写时间不一致: 索引='{entry.get('written_at')}', 实际='{item.written_at}'")
            if entry.get("reject_count") != item.reject_count:
                mismatches.append(f"打回次数不一致: 索引={entry.get('reject_count')}, 实际={item.reject_count}")
            if entry.get("card_type", "task") != item.type:
                mismatches.append(f"卡片类型不一致: 索引='{entry.get('card_type')}', 实际='{item.type}'")
            if entry.get("parent_card", "") != item.parent:
                mismatches.append(f"父卡不一致: 索引='{entry.get('parent_card')}', 实际='{item.parent}'")
            if entry.get("dispatch", "engine") != item.dispatch:
                mismatches.append(f"派发方式不一致: 索引='{entry.get('dispatch')}', 实际='{item.dispatch}'")

            if mismatches:
                issues.append(
                    CardIssue(
                        card_id=item.id,
                        path=str(path),
                        reason=f"索引对账失败: {'; '.join(mismatches)}",
                        severity="error",
                    )
                )

        # 2. Check index vs disk
        for card_id, entry in index_entries.items():
            if card_id not in disk_ids:
                issues.append(
                    CardIssue(
                        card_id=card_id,
                        path=entry.get("path", ""),
                        reason=f"孤立索引：索引中存在卡片 {card_id}，但磁盘上未找到对应文件",
                        severity="error",
                    )
                )
    except Exception as e:
        issues.append(CardIssue(card_id="?", path="index", reason=f"对账过程异常: {e}", severity="error"))

    return issues


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    target = argv[0] if argv else "docs/dispatch"
    issues = validate_cards(target)
    errors = [i for i in issues if i.severity == "error"]
    warns = [i for i in issues if i.severity == "warn"]
    count = len(_scan_cards(Path(target))) if Path(target).is_dir() else 0
    if not errors:
        print(f"卡头校验通过：{target}（{count} 张卡，{len(warns)} 条提示）")
        for w in warns:
            print(f"  [提示] [{w.card_id}] {w.path}: {w.reason}")
        return 0
    print(f"卡头校验发现 {len(errors)} 个问题（另 {len(warns)} 条提示）：")
    for it in errors:
        print(f"  [{it.card_id}] {it.path}: {it.reason}")
    for w in warns:
        print(f"  [提示] [{w.card_id}] {w.path}: {w.reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
