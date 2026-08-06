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
