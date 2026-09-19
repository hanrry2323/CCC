r"""D2/D2b 回归：markdown 兜底节标题行首锚定（2026-09-19 指令单 D2）。

D2 根因：main.py 旧逻辑用子串 split("## 3. 维护区四问")，执行体实际写「## 维护区」
（无序号），子串命中散文提及 → 提取出无关段 → parse_maintenance_section 解析 0/4 问。
D2b 连带：契约检查 missing = [h for h in required if h not in result] 同样子串匹配，
散文提及骗过检查 → 判「完整」但提取段是垃圾。

修复：行首正则锚定 `^## (?:\d+\. )?(?:维护区四问|维护区)\s*$`（re.M），
取该匹配之后到下一个行首 `^## ` 之前；契约检查同样行首锚定。
"""
from __future__ import annotations

from server.engine.result_contract import (
    _extract_maintenance_section,
    _missing_required_headings,
)

_FOUR_LINES = (
    "1. **方案同步**：[是] xy079 已含在 xy-plan-011 卡头关联\n"
    "2. **教训沉淀**：[有] 教训沉淀于 CCC 仓 docs/notes/2026-09-18-xy079-lessons.md\n"
    "3. **档案/README**：[否] 无变更\n"
    "4. **线路图**：[否] 无新增线路图"
)

_FULL_ENVELOPE = (
    "# 执行结果 · xy079 · smoke\n"
    "## 0. 卡标题复述\n\nxy079 · smoke\n"
    "## 1. 探针输出\n\n- probe ok\n"
    "## 2. 自测输出\n\n- 8 passed\n"
    "## 维护区\n\n" + _FOUR_LINES + "\n\n"
    "## 4. 变更证据\n\ncommit=abc branch=codex/xy079 push=success\n"
)


def test_envelope_with_unumbered_heading_extracts_four_lines() -> None:
    """本缺陷回归：信封节标题写「## 维护区」（无序号）→ 提取段四行齐全。"""
    text = _FULL_ENVELOPE  # 节标题无序号
    section = _extract_maintenance_section(text)
    assert section is not None
    assert _FOUR_LINES.strip() == section.strip()


def test_envelope_with_numbered_heading_extracts_four_lines() -> None:
    """信封写「## 3. 维护区四问」带序号 → 同样四行齐全。"""
    text = _FULL_ENVELOPE.replace("## 维护区\n", "## 3. 维护区四问\n")
    section = _extract_maintenance_section(text)
    assert section is not None
    assert _FOUR_LINES.strip() == section.strip()


def test_prose_mention_does_not_pass_contract_check() -> None:
    """D2b 回归：散文里提「维护区四问」但节标题缺失 → 契约判 incomplete。"""
    # 信封无节标题，只在散文里提到「## 3. 维护区四问 + ### Q1/Q2/... 三级标题格式」
    prose = (
        "# 执行结果 · xy079 · smoke\n"
        "## 0. 卡标题复述\n\nxy079 · smoke\n"
        "## 1. 探针输出\n\n替换上一版的 ## 3. 维护区四问 + ### Q1/Q2/... 三级标题格式\n"
        "## 2. 自测输出\n\n- 8 passed\n"
        "## 4. 变更证据\n\ncommit=abc\n"
    )
    missing = _missing_required_headings(prose)
    assert "## 3. 维护区四问" in missing, missing


def test_missing_maintenance_heading_reported() -> None:
    """维护区节标题完全缺失 → 契约判 incomplete。"""
    text = (
        "## 0. 卡标题复述\n\nxy079\n"
        "## 1. 探针输出\n\nprobe\n"
        "## 2. 自测输出\n\ntest\n"
        "## 4. 变更证据\n\ncommit=abc\n"
    )
    missing = _missing_required_headings(text)
    assert "## 3. 维护区四问" in missing


def test_prose_mention_does_not_extract_garbage() -> None:
    """D2 核心：散文提及不得被当作节标题提取出无关段。"""
    text = (
        "## 0. 卡标题复述\n\nxy079\n"
        "## 1. 探针输出\n\n替换上一版的 ## 3. 维护区四问 + ### Q1/Q2 三级标题格式\n"
        "## 2. 自测输出\n\ntest ok\n"
        "## 4. 变更证据\n\ncommit=abc\n"
    )
    assert _extract_maintenance_section(text) is None


def test_full_envelope_passes_contract() -> None:
    """完整信封（无序号维护区）契约判定齐全。"""
    assert _missing_required_headings(_FULL_ENVELOPE) == ()


def test_envelope_without_all_headings_incomplete() -> None:
    """缺卡标题复述/探针/自测任一段 → 契约判 incomplete（行首锚定不因散文放水）。"""
    text = (
        "## 1. 探针输出\n\nprobe\n"
        "## 2. 自测输出\n\ntest\n"
        "## 维护区\n\n" + _FOUR_LINES + "\n"
    )
    missing = _missing_required_headings(text)
    assert "## 0. 卡标题复述" in missing
