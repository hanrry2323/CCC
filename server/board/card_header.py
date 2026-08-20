"""任务卡头契约单一 schema（A1 · ccc059）。

loader / validate / docgate / prompt_inject 统一从这里 import 卡头解析与字段清单，
禁止各层自写 regex 解析卡头。

冻结期（红线）：不改现有字段名/语义；HEADER_FIELDS 为唯一字段登记表，
新增字段必须先在方案/规范中定稿，再在此登记。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Self

from server.board.models import UNKNOWN, base_state

# ── 冻结的卡头字段清单（契约 §1；唯一登记表，禁止各层自写解析） ──
HEADER_FIELDS: tuple[str, ...] = (
    "关联",
    "执行体",
    "验收",
    "状态",
    "日期",
    "项目",
    "派发",
    "类型",
    "父卡",
    "会话",
    "thread_id",
    "批准",
)

# 契约 §2 六态（卡头唯一合法状态）
# 人审调整动作统一化（2026-08-14）：新增「作废」终态。
VALID_STATES: frozenset[str] = frozenset({"待分派", "执行中", "已回写", "已关闭", "打回", "作废"})
# 「派发」合法值（缺省 engine）
DISPATCH_VALUES: frozenset[str] = frozenset({"manual", "engine", "scheduler", "remote"})
# 「类型」合法值（缺省 task）
TYPE_VALUES: frozenset[str] = frozenset({"epic", "task"})

_META_PAIR_RE = re.compile(r"^\s*([^：\s][^：]*?)\s*[:：]\s*(.+?)\s*$")
_TITLE_RE = re.compile(r"^#\s*任务卡\s+(\S+)\s*[·\-]\s*(.+?)\s*$", re.MULTILINE)
_CARD_TITLE_RE = re.compile(r"^#\s*任务卡\s", re.MULTILINE)
_ID_RE = re.compile(r"^#\s*任务卡\s+([^\s·]+)", re.MULTILINE)
_REJECT_RE = re.compile(r"打回次数\s*[:：]\s*(\d+)")


def parse_metadata(text: str) -> dict[str, str]:
    """解析 `>` 元数据行的 `key：value` 对（唯一实现；loader/validate/docgate/prompt_inject 共用）。

    F2（ccc-plan-035）：遇 ``## `` 标题行即停止——卡头元信息只在标题行后、
    第一个 ``## `` 节之前。机审区内 ``> 状态：`` 等行不再污染卡头。
    """
    meta: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            break  # 进入正文节，卡头元信息区结束
        if not line.startswith(">"):
            continue
        body = line.lstrip(">").strip()
        for part in re.split(r"·", body):
            match = _META_PAIR_RE.match(part)
            if match:
                meta[match.group(1).strip()] = match.group(2).strip()
    return meta


def card_id(text: str) -> str:
    """取卡头 `# 任务卡 <ID>` 的 ID（行首锚定）；未匹配返回空串。"""
    m = _ID_RE.search(text)
    return m.group(1).strip() if m else ""


def bump_reject_count(text: str) -> str:
    """卡进入「打回」时递增卡头 `打回次数：N` 字段（只读展示→真实计数修复）。

    统一化（2026-08-14）前该字段全仓只有读没有写；打回/机审打回路径调用本函数。
    无字段则新增一行（放在卡头 `# 任务卡` 标题行后）；已有则 N+1。
    """
    m = _REJECT_RE.search(text)
    if m:
        new_count = int(m.group(1)) + 1
        return re.sub(
            r"(打回次数\s*[:：]\s*)\d+",
            rf"\g<1>{new_count}",
            text,
            count=1,
        )
    # 无字段：在 `# 任务卡 ...` 标题行后插入 `> 打回次数：1`
    title_m = _CARD_TITLE_RE.search(text)
    if not title_m:
        return text
    # 插入点 = 标题行行尾（而非标题前缀之后）——否则会把卡号/标题挤到下一行
    # （xy054 事故：insert_at=title_m.end() 只到「# 任务卡 」前缀，导致标题被拆成
    #   「# 任务卡 \n> 打回次数：1xy054 · 标题」，CardHeader 解析 id 时 _TITLE_RE 失配，
    #   fallback 成文件 stem「xy054-preview-pages」，sync_plan_progress 按纯卡号查不到 → 方案进度漏算）
    line_end = text.find("\n", title_m.end())
    if line_end == -1:
        line_end = len(text)
    insert_at = line_end
    return text[:insert_at] + "\n> 打回次数：1" + text[insert_at:]


def is_task_card_text(text: str) -> bool:
    """是否任务卡卡头（行首含 `# 任务卡`）；T-mapping.md 等说明文档返回 False。"""
    return bool(_CARD_TITLE_RE.search(text))


def _normalize_dispatch(raw: str) -> str:
    value = (raw or "").strip().lower()
    return value if value in DISPATCH_VALUES else "engine"


def _normalize_type(raw: str) -> str:
    value = (raw or "").strip().lower()
    return value if value in TYPE_VALUES else "task"


@dataclass(frozen=True)
class CardHeader:
    """任务卡头契约单一 schema。"""

    id: str = UNKNOWN
    title: str = UNKNOWN
    related: str = ""
    executor: str = UNKNOWN
    acceptance: str = UNKNOWN
    state: str = UNKNOWN
    dispatched_at: str = UNKNOWN
    project: str = ""
    dispatch: str = "engine"
    card_type: str = "task"
    parent: str = ""
    session: str = ""
    reject_count: int = 0
    depends: str = ""
    approval: str = ""

    @classmethod
    def from_text(cls, text: str, fallback_id: str = "") -> Self:
        meta = parse_metadata(text)
        title_match = _TITLE_RE.search(text)
        if title_match:
            card_id_val, title = title_match.group(1), title_match.group(2).strip()
        else:
            card_id_val, title = fallback_id or UNKNOWN, UNKNOWN

        reject_match = _REJECT_RE.search(text)
        reject_count = int(reject_match.group(1)) if reject_match else 0
        state = meta.get("状态", UNKNOWN)
        if reject_count == 0 and base_state(state) == "打回":
            reject_count = 1

        return cls(
            id=card_id_val,
            title=title,
            related=meta.get("关联", ""),
            executor=meta.get("执行体", UNKNOWN),
            acceptance=meta.get("验收", UNKNOWN),
            state=state,
            dispatched_at=meta.get("日期", UNKNOWN),
            project=meta.get("项目", ""),
            dispatch=_normalize_dispatch(meta.get("派发", "")),
            card_type=_normalize_type(meta.get("类型", "")),
            parent=meta.get("父卡", ""),
            session=(meta.get("会话", "").strip() or meta.get("thread_id", "").strip()),
            reject_count=reject_count,
            depends=meta.get("依赖", ""),
            approval=meta.get("批准", ""),
        )


# ── F1（ccc-plan-035）：机审区格式校验器 ──

_AUDIT_VERDICT_RE = re.compile(r"(机审|结论)\s*[:：]\s*(不通过|通过)")
_AUDIT_RESULT_RE = re.compile(r"结果\s*[:：]\s*(不通过|通过)")
_AUDIT_STATE_PREFIX_RE = re.compile(r"^>\s*状态\s*[:：]", re.MULTILINE)


def validate_audit_section(text: str) -> tuple[bool, str]:
    """校验机审区格式契约（ccc-plan-035 · F1）。

    落盘前调用：非法格式当场报错打回，防静默降级。

    规则：
    1. 每个 ``## 机审区`` 节必须含至少一条结论行（``机审：通过/不通过`` 或 ``结论：通过/不通过``，
       含 ``### 机审：通过`` 兼容写法）。
    2. 机审区内禁止 ``> 状态：`` 前缀行——会被 ``parse_metadata`` 误当卡头状态覆盖真值
       （F2 已隔离，此处为前置拦截双保险）。
    3. 无 ``## 机审区`` 节 → 合法（尚未添加机审区）。

    Returns:
        (True, "") 合法；(False, reason) 非法并附原因。
    """
    if not text:
        return True, ""
    lines = text.splitlines()
    n = len(lines)
    section_idx = 0
    i = 0
    while i < n:
        line_stripped = lines[i].strip()
        if line_stripped.startswith("## 机审区"):
            section_idx += 1
            has_verdict = False
            has_state_prefix = False
            j = i + 1
            while j < n:
                cur = lines[j]
                cur_stripped = cur.strip()
                if cur_stripped.startswith("## "):
                    break
                # 检测 > 状态： 前缀
                if _AUDIT_STATE_PREFIX_RE.match(cur):
                    has_state_prefix = True
                # 去加粗后匹配结论行
                normalized = cur_stripped.replace("**", "").replace("*", "")
                if _AUDIT_VERDICT_RE.search(normalized) or _AUDIT_RESULT_RE.search(normalized):
                    has_verdict = True
                j += 1
            if has_state_prefix:
                return False, f"机审区{section_idx}含 `> 状态：` 前缀行——会被 parse_metadata 误当卡头状态覆盖，请改用 `> 结论：`"
            if not has_verdict:
                return False, f"机审区{section_idx}缺少结论行（需含 `机审：通过/不通过` 或 `结论：通过/不通过`）"
            i = j
        else:
            i += 1
    return True, ""
