"""看板机审列 + 机审标记解析。"""
from server.board.models import board_column, machine_audit_passed_text


def test_board_column_ji_shen_when_written_without_audit():
    assert board_column("已回写", False) == "机审"
    assert board_column("已回写", True) == "已回写"
    assert board_column("执行中", False) == "执行中"


def test_machine_audit_passed_text():
    ok = "## 机审区\n\n**机审：通过**\n"
    assert machine_audit_passed_text(ok) is True
    bad = "## 目标\n禁止写 ## 机审区\n"
    assert machine_audit_passed_text(bad) is False


def test_machine_audit_multi_round_passed():
    """多轮机审追加多节：首锚点为历史不通过，后节有通过 → 判通过。"""
    card = (
        "# 任务卡 xy012 · 测试\n"
        "\n## 机审区\n\n**结论：机审：不通过**\n原因：轮次 2\n"
        "\n## 机审区\n\n**结论：机审：通过**\n轮次 3 通过\n"
        "\n## 机审区\n\n**结论：机审：通过**\n轮次 8 通过\n"
    )
    assert machine_audit_passed_text(card) is True

    only_fail = (
        "# 任务卡 x · 测试\n"
        "\n## 机审区\n\n**结论：机审：不通过**\n原因：缺测试\n"
        "\n## 机审区\n\n**结论：机审：不通过**\n原因：仍缺\n"
    )
    assert machine_audit_passed_text(only_fail) is False


def test_machine_audit_p6_cases():
    """测试 P6 升级后更精细的判定规则：噪声排除、多轮追加、单轮及无机审区。"""
    # 1. 噪声排除：表格中含有 ✅，但最后的结论是「不通过」 -> False (如 hp009 场景)
    hp009_mock = (
        "# 任务卡 hp009\n"
        "## 机审区\n"
        "**机审**：2017 机审席（Claude Code） · 日期：2026-08-08 · 轮次：**第 3 轮复查** · 结论：**机审：不通过**\n"
        "| 编号 | 严重级 | 发现 | 闭环? |\n"
        "|---|---|---|---|\n"
        "| P1-1 | P1 | 测试 | ✅ |\n"
    )
    assert machine_audit_passed_text(hp009_mock) is False

    # xy024 场景：结论为「不通过」，哪怕有 ✅ 噪声
    xy024_mock = (
        "# 任务卡 xy024\n"
        "## 机审区\n"
        "**机审：不通过**（测试门禁验收标准未被真实运行满足；文档归位已修复）\n"
        "| 验收标准 | 结果 | 依据 |\n"
        "|---|---|---|\n"
        "| 1. pytest | ✅ 满足 | 很好 |\n"
    )
    assert machine_audit_passed_text(xy024_mock) is False

    # 2. 同一节多轮追加：先「不通过」轮，后「通过」轮 -> True (xy012 单节多轮场景)
    same_section_multi_round = (
        "# 任务卡 xy012\n"
        "## 机审区\n"
        "### 第 1 轮\n"
        "机审：不通过\n"
        "### 第 2 轮\n"
        "结论：通过\n"
    )
    assert machine_audit_passed_text(same_section_multi_round) is True

    # 先「通过」轮，后「不通过」轮 -> False
    same_section_multi_round_fail = (
        "# 任务卡 xy012_fail\n"
        "## 机审区\n"
        "### 第 1 轮\n"
        "结论：通过\n"
        "### 第 2 轮\n"
        "机审：不通过\n"
    )
    assert machine_audit_passed_text(same_section_multi_round_fail) is False

    # 3. 单轮「机审：通过」 -> True
    simple_pass = (
        "# 任务卡 ok\n"
        "## 机审区\n"
        "结论：通过\n"
    )
    assert machine_audit_passed_text(simple_pass) is True

    # 4. 无机审区 -> False
    no_audit_section = (
        "# 任务卡 no\n"
        "## 回写区\n"
        "这里不含有机审区\n"
    )
    assert machine_audit_passed_text(no_audit_section) is False

    # 5. 结论在小节标题上（### 机审：通过） -> True
    section_title_pass = (
        "# 任务卡 section_pass\n"
        "## 机审区\n"
        "### 机审：通过\n"
    )
    assert machine_audit_passed_text(section_title_pass) is True

    # 结论在小节标题上且最后是不通过 -> False
    section_title_fail = (
        "# 任务卡 section_fail\n"
        "## 机审区\n"
        "### 机审：通过\n"
        "### 结论：不通过\n"
    )
    assert machine_audit_passed_text(section_title_fail) is False
