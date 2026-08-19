"""机审区格式契约测试（ccc-plan-035 · F1/F2/F3）。

覆盖三道防线：
- F1: validate_audit_section 校验器（合法/非法判定）
- F2: parse_metadata 卡头隔离（机审区 > 状态： 不污染卡头）
- F3: engine 输出格式对齐契约
"""

from __future__ import annotations

from server.board.card_header import parse_metadata, validate_audit_section


# ── F2: parse_metadata 卡头隔离 ──


def test_f2_audit_section_state_not_polluting_header():
    """机审区内 `> 状态：机审通过` 不应覆盖卡头真状态。"""
    card = (
        "# 任务卡 T99 · 示例\n"
        "> 状态：执行中 · 执行体：OpenCode\n"
        "\n"
        "## 目标\n"
        "测试\n"
        "\n"
        "## 机审区\n"
        "> 状态：机审通过\n"
        "> 结论：通过\n"
    )
    meta = parse_metadata(card)
    assert meta.get("状态") == "执行中", f"卡头状态被机审区污染: {meta.get('状态')}"


def test_f2_header_before_section_still_parsed():
    """##  之前的 > 行正常解析（向后兼容）。"""
    card = (
        "# 任务卡 T99 · 示例\n"
        "> 状态：待分派 · 执行体：OpenCode · 验收：Codex\n"
        "\n"
        "## 机审区\n"
        "> 结论：机审通过\n"
    )
    meta = parse_metadata(card)
    assert meta["状态"] == "待分派"
    assert meta["执行体"] == "OpenCode"
    assert meta["验收"] == "Codex"


def test_f2_no_section_full_text_scanned():
    """无机审区时全文扫（向后兼容短卡）。"""
    card = (
        "# 任务卡 T99 · 示例\n"
        "> 状态：待分派 · 执行体：OpenCode\n"
    )
    meta = parse_metadata(card)
    assert meta["状态"] == "待分派"
    assert meta["执行体"] == "OpenCode"


def test_f2_reject_count_before_section_preserved():
    """打回次数在 ## 前插入，不受影响。"""
    card = (
        "# 任务卡 T99 · 示例\n"
        "> 状态：打回 · 打回次数：2\n"
        "\n"
        "## 机审区\n"
        "> 结论：机审不通过\n"
    )
    meta = parse_metadata(card)
    assert meta["状态"] == "打回"
    assert meta["打回次数"] == "2"


# ── F1: validate_audit_section 校验器 ──


def test_f1_valid_conclusion_pass():
    """合法：> 结论：通过（权威写法）。"""
    card = "## 机审区\n\n> 结论：通过\n"
    ok, reason = validate_audit_section(card)
    assert ok, reason


def test_f1_valid_conclusion_fail():
    """合法：> 结论：不通过（权威写法）。"""
    card = "## 机审区\n\n> 结论：不通过\n原因：缺测试\n"
    ok, reason = validate_audit_section(card)
    assert ok, reason


def test_f1_valid_section_title_verdict():
    """合法：### 机审：通过（兼容写法）。"""
    card = "## 机审区\n\n### 机审：通过\n"
    ok, reason = validate_audit_section(card)
    assert ok, reason


def test_f1_valid_bold_verdict():
    """合法：**机审：通过**（去加粗后匹配）。"""
    card = "## 机审区\n\n**机审：通过**\n"
    ok, reason = validate_audit_section(card)
    assert ok, reason


def test_f1_valid_result_field():
    """合法：结果：通过（兼容 agent 格式）。"""
    card = "## 机审区\n\n**机审**：Codex · 结果：**通过**\n"
    ok, reason = validate_audit_section(card)
    assert ok, reason


def test_f1_invalid_machine_verdict_in_conclusion():
    """非法：> 结论：机审通过（结论行带「机审」二字，判定器不认 → 死循环根因，校验器前置拦截）。

    判定器 models.py 正则 `结论：通过` 要求冒号后直接是「通过/不通过」，
    `结论：机审通过` 中间隔了「机审」→ 不匹配 → 判无结论。
    校验器同正则，落盘前拦截，防「机审通过但落盘判定失败 → 死循环」（hp032/hp038 根因）。
    """
    card = "## 机审区\n\n> 结论：机审通过\n"
    ok, reason = validate_audit_section(card)
    assert not ok
    assert "结论" in reason


def test_f1_invalid_state_prefix():
    """非法：> 状态： 前缀行。"""
    card = "## 机审区\n\n> 状态：机审通过\n> 结论：机审通过\n"
    ok, reason = validate_audit_section(card)
    assert not ok
    assert "状态" in reason


def test_f1_invalid_no_verdict():
    """非法：无机审结论行。"""
    card = "## 机审区\n\n这里只有描述文字\n没有结论\n"
    ok, reason = validate_audit_section(card)
    assert not ok
    assert "结论" in reason


def test_f1_valid_no_audit_section():
    """合法：无机审区节。"""
    card = "# 任务卡 T99 · 示例\n> 状态：待分派\n\n## 目标\n测试\n"
    ok, reason = validate_audit_section(card)
    assert ok, reason


def test_f1_valid_empty_text():
    """合法：空文本。"""
    ok, reason = validate_audit_section("")
    assert ok, reason


def test_f1_multiple_sections_all_valid():
    """合法：多节机审区，每节都有结论。"""
    card = (
        "## 机审区\n\n> 结论：不通过\n原因：缺测试\n"
        "\n## 机审区\n\n> 结论：通过\n"
    )
    ok, reason = validate_audit_section(card)
    assert ok, reason


def test_f1_multiple_sections_second_invalid():
    """非法：多节中第二节缺结论。"""
    card = (
        "## 机审区\n\n> 结论：通过\n"
        "\n## 机审区\n\n只有描述\n无结论\n"
    )
    ok, reason = validate_audit_section(card)
    assert not ok
    assert "2" in reason


# ── F3: engine 输出格式对齐 ──


def test_f3_engine_output_format():
    """engine 自动落盘的机审区文本符合契约（> 结论：通过）。"""
    # 模拟 _append_machine_audit_pass 的 section 格式
    section = (
        "\n\n## 机审区\n\n"
        "> 结论：通过\n"
        "> 来源：engine 自动落盘（test）· 2026-08-19 14:00\n"
        "> 证据：pytest all passed\n"
    )
    ok, reason = validate_audit_section(section)
    assert ok, f"engine 输出格式不符契约: {reason}"
