"""test_validate_task_jsonl.py — v0.26 Protocol v1 校验函数测试

覆盖：
  - 11 条校验规则（每条规则 1 个 pass + 1 个 fail case）
  - strict 模式拒绝未知字段
  - 缺失字段补默认（fill_task_defaults）
  - create_task 集成（实际写文件）
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"

os.chdir(str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("cb", str(SCRIPTS / "_board_store.py"))
bs = importlib.util.module_from_spec(_spec)
sys.modules["cb"] = bs
_spec.loader.exec_module(bs)

validate_task_jsonl = bs.validate_task_jsonl
fill_task_defaults = bs.fill_task_defaults
sanitize_id = bs.sanitize_id
FileBoardStore = bs.FileBoardStore
COLUMNS = bs.COLUMNS
now_iso = bs.now_iso


def _valid_task() -> dict:
    """完整合规 task"""
    return {
        "id": "fix-login-500",
        "title": "修复登录 500 错误",
        "description": "OAuth callback 返回 500",
        "status": "backlog",
        "created_at": "2026-07-11T14:00:00Z",
        "updated_at": "2026-07-11T14:00:00Z",
        "assignee": "alice",
        "tags": ["bug", "auth"],
        "note": "P1",
        "schema_version": "1.0",
        "color_group": "A",
        "color_depth": 0,
    }


class TestValidateTaskJsonl:
    """11 条规则 + 容错 + strict 模式"""

    # 规则 1: id
    def test_rule1_id_valid_passes(self):
        ok, errs = validate_task_jsonl(_valid_task())
        assert ok, errs

    def test_rule1_id_missing_fails(self):
        t = _valid_task()
        del t["id"]
        ok, errs = validate_task_jsonl(t)
        assert not ok
        assert any("id" in e for e in errs)

    def test_rule1_id_invalid_chars_fails(self):
        t = _valid_task()
        t["id"] = "task 001"  # 含空格
        ok, errs = validate_task_jsonl(t)
        assert not ok

    # 规则 2: title
    def test_rule2_title_empty_fails(self):
        t = _valid_task()
        t["title"] = ""
        ok, errs = validate_task_jsonl(t)
        assert not ok
        assert any("title" in e for e in errs)

    def test_rule2_title_too_long_fails(self):
        t = _valid_task()
        t["title"] = "x" * 501
        ok, errs = validate_task_jsonl(t)
        assert not ok

    # 规则 3: status
    def test_rule3_status_invalid_fails(self):
        t = _valid_task()
        t["status"] = "todo"
        ok, errs = validate_task_jsonl(t)
        assert not ok
        assert any("status" in e and "todo" in e for e in errs)

    def test_rule3_status_backlog_passes(self):
        t = _valid_task()
        t["status"] = "backlog"
        ok, _ = validate_task_jsonl(t)
        assert ok

    # 规则 4: timestamps
    def test_rule4_created_at_missing_fails(self):
        t = _valid_task()
        del t["created_at"]
        ok, errs = validate_task_jsonl(t)
        assert not ok
        assert any("created_at" in e for e in errs)

    def test_rule4_updated_at_invalid_format_fails(self):
        t = _valid_task()
        t["updated_at"] = "not-iso-8601"
        ok, errs = validate_task_jsonl(t)
        assert not ok

    # 规则 5: description
    def test_rule5_description_not_string_fails(self):
        t = _valid_task()
        t["description"] = 12345
        ok, errs = validate_task_jsonl(t)
        assert not ok

    # 规则 6: assignee
    def test_rule6_assignee_int_fails(self):
        t = _valid_task()
        t["assignee"] = 42
        ok, errs = validate_task_jsonl(t)
        assert not ok

    # 规则 7: tags
    def test_rule7_tags_not_list_fails(self):
        t = _valid_task()
        t["tags"] = "bug,auth"
        ok, errs = validate_task_jsonl(t)
        assert not ok

    # 规则 8: note
    def test_rule8_note_int_fails(self):
        t = _valid_task()
        t["note"] = 999
        ok, errs = validate_task_jsonl(t)
        assert not ok

    # 规则 9: schema_version
    def test_rule9_schema_version_int_fails(self):
        t = _valid_task()
        t["schema_version"] = 1.0
        ok, errs = validate_task_jsonl(t)
        assert not ok

    def test_rule9_schema_version_missing_passes(self):
        """缺失 schema_version 在 strict=False 时补默认"""
        t = _valid_task()
        del t["schema_version"]
        ok, _ = validate_task_jsonl(t)
        assert ok

    # 规则 10: color_group
    def test_rule10_color_group_lowercase_fails(self):
        t = _valid_task()
        t["color_group"] = "a"  # 必须大写
        ok, errs = validate_task_jsonl(t)
        assert not ok

    def test_rule10_color_group_missing_passes(self):
        t = _valid_task()
        del t["color_group"]
        ok, _ = validate_task_jsonl(t)
        assert ok

    # 规则 11: color_depth
    def test_rule11_color_depth_negative_fails(self):
        t = _valid_task()
        t["color_depth"] = -1
        ok, errs = validate_task_jsonl(t)
        assert not ok

    def test_rule11_color_depth_missing_passes(self):
        t = _valid_task()
        del t["color_depth"]
        ok, _ = validate_task_jsonl(t)
        assert ok

    # 容错 + strict 模式
    def test_unknown_field_ignored_in_non_strict(self):
        t = _valid_task()
        t["future_field_v027"] = "extra"
        ok, errs = validate_task_jsonl(t, strict=False)
        assert ok, errs

    def test_unknown_field_rejected_in_strict(self):
        t = _valid_task()
        t["future_field_v027"] = "extra"
        ok, errs = validate_task_jsonl(t, strict=True)
        assert not ok
        assert any("unknown fields" in e for e in errs)

    def test_data_not_dict_fails(self):
        ok, errs = validate_task_jsonl(["not", "a", "dict"])
        assert not ok


class TestFillTaskDefaults:
    """fill_task_defaults 补默认字段"""

    def test_fill_minimal_data(self):
        out = fill_task_defaults({"id": "x"})
        assert out["schema_version"] == "1.0"
        assert out["color_group"] is None
        assert out["color_depth"] == 0

    def test_fill_preserves_existing(self):
        out = fill_task_defaults({"schema_version": "1.0", "color_group": "B", "color_depth": 2})
        assert out["schema_version"] == "1.0"
        assert out["color_group"] == "B"
        assert out["color_depth"] == 2


class TestCreateTaskIntegration:
    """create_task 集成 validate + fill_defaults"""

    def test_create_valid_task(self, tmp_path):
        store = FileBoardStore(tmp_path)
        ok = store.create_task(_valid_task(), column="backlog")
        assert ok
        # 验证 task 文件存在且含全部字段
        task_file = tmp_path / ".ccc" / "board" / "backlog" / "fix-login-500.jsonl"
        assert task_file.exists()
        loaded = json.loads(task_file.read_text())
        assert loaded["id"] == "fix-login-500"
        assert loaded["color_group"] == "A"
        assert loaded["color_depth"] == 0
        assert loaded["schema_version"] == "1.0"

    def test_create_minimal_task_gets_defaults(self, tmp_path):
        """仅传 id+title+status+timestamps → 默认字段自动补"""
        store = FileBoardStore(tmp_path)
        ok = store.create_task(
            {
                "id": "minimal-task",
                "title": "Minimal",
                "status": "backlog",
                "created_at": "2026-07-11T14:00:00Z",
                "updated_at": "2026-07-11T14:00:00Z",
            },
            column="backlog",
        )
        assert ok
        loaded = json.loads(
            (tmp_path / ".ccc" / "board" / "backlog" / "minimal-task.jsonl").read_text()
        )
        assert loaded["schema_version"] == "1.0"
        assert loaded["color_group"] is None
        assert loaded["color_depth"] == 0
        assert loaded["description"] == ""

    def test_create_invalid_task_returns_false(self, tmp_path):
        store = FileBoardStore(tmp_path)
        bad = _valid_task()
        bad["id"] = "task 001"  # 含空格，validate 失败
        ok = store.create_task(bad, column="backlog")
        assert not ok
        # 文件不应写入
        assert not (tmp_path / ".ccc" / "board" / "backlog" / "task 001.jsonl").exists()

class TestServerStructuredError:
    """v0.26: POST /api/tasks 结构化 error feedback（精简版）"""

    @pytest.fixture
    def server_module(self):
        """ccc-board-server.py 含连字符，importlib 加载"""
        server_path = SCRIPTS / "ccc-board-server.py"
        spec = importlib.util.spec_from_file_location("ccc_board_server", str(server_path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ccc_board_server"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_field_of_extracts_id(self, server_module):
        assert server_module._field_of("id: required and non-empty") == "id"

    def test_field_of_extracts_status(self, server_module):
        assert server_module._field_of("status: 'todo' not in COLUMNS") == "status"

    def test_field_of_no_colon_returns_full(self, server_module):
        assert server_module._field_of("no colon here") == "no colon here"

    def test_rule_of_extracts_rule(self, server_module):
        assert server_module._rule_of("id: required") == "required"
        assert server_module._rule_of("status: 'todo' not in COLUMNS") == "'todo' not in COLUMNS"

    def test_got_of_extracts_quoted(self, server_module):
        assert server_module._got_of("status: 'todo' not in COLUMNS") == "todo"
        assert server_module._got_of("id: 'task 001' would be sanitized") == "task 001"
        assert server_module._got_of("plain text") == ""

    def test_fix_hint_for_id_and_status(self, server_module):
        hint = server_module._fix_hint_for([
            "id: required",
            "status: 'todo' not in COLUMNS",
        ])
        assert "id" in hint.lower()
        assert "status" in hint.lower()
        assert len(hint) <= 200

    def test_fix_hint_for_color_group(self, server_module):
        hint = server_module._fix_hint_for(["color_group: 'x' must be single A-Z char"])
        assert "A-Z" in hint or "color" in hint.lower()

    def test_fix_hint_for_empty_errors(self, server_module):
        assert server_module._fix_hint_for([]) == ""

    def test_fix_hint_truncates_to_200(self, server_module):
        errors = [f"field_{i}: error msg" for i in range(10)]
        hint = server_module._fix_hint_for(errors)
        assert len(hint) <= 200


class TestAssignColorGroup:
    """v0.26 Protocol v1 §5: assign_color_group 颜色分组"""

    def test_inherit_parent_group(self, tmp_path):
        from cb import assign_color_group
        g = assign_color_group(tmp_path, parent_group="B")
        assert g == "B"

    def test_assign_new_when_no_parent(self, tmp_path):
        from cb import assign_color_group
        g = assign_color_group(tmp_path)
        assert g in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def test_rotate_pool(self, tmp_path):
        """连续两次分配 → 第二次字母序 +1"""
        from cb import assign_color_group
        g1 = assign_color_group(tmp_path)
        g2 = assign_color_group(tmp_path)
        assert g1 != g2
        # 验证从 A 开始轮转
        assert ord(g2) == ord(g1) + 1 or (g1 == "Z" and g2 == "A")

    def test_persists_across_calls(self, tmp_path):
        """counter 持久化 → 第二次调用读到上次的值并 +1"""
        from cb import assign_color_group
        g1 = assign_color_group(tmp_path)
        g2 = assign_color_group(tmp_path)
        g3 = assign_color_group(tmp_path)
        # A → B → C
        assert g1 == "A"
        assert g2 == "B"
        assert g3 == "C"

    def test_parent_invalid_returns_fresh(self, tmp_path):
        """parent_group 无效（如 'X'）→ 走轮转路径"""
        from cb import assign_color_group
        # 'X' 不在 GROUP_POOL（A-Z）→ fallback to 轮转
        g = assign_color_group(tmp_path, parent_group="X")
        assert g in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
