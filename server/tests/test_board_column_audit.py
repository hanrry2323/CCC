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
