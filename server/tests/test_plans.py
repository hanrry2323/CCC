"""server/tests/test_plans.py — 方案读写模块测试（S5 补件 · 2026-08-09）

覆盖：
1. list_plans: 按项目/状态/关键词筛选 + 排序
2. get_plan: 正常读取；非法路径拒绝（含 ../ 目录穿越）
3. create_plan: 自动编号递增；非法前缀拒绝；校验失败自删
4. update_plan: 非法状态拒绝；内容替换保留头部
5. convert_plan: 缺「转卡计划」段报错
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.board.plans import (
    VALID_STATES,
    convert_plan,
    create_plan,
    get_plan,
    list_plans,
    update_plan,
    _extract_header_fields,
    _extract_title,
    _extract_acceptance,
)


# ── helpers ──

def _make_plan(tmp: Path, prefix: str, num: str, slug: str, status: str,
               title: str = "测试方案", author: str = "测试", tool: str = "pytest",
               plan_section: str = "") -> Path:
    """在临时目录下构造一个方案文件。"""
    plans_dir = tmp / "docs" / "projects" / prefix / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_id = f"{prefix}-plan-{num}"
    content = f"""# 方案 · {title}

> 项目：{prefix} · 编号：{plan_id} · 状态：{status} · 作者：{author} · 工具：{tool}
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无

## 目标

测试方案内容。

## 验收标准

- [ ] 测试项 1
- [x] 测试项 2

## 转卡计划

{plan_section}

## 备注

无
"""
    p = plans_dir / f"{num}-{slug}.md"
    p.write_text(content)
    return p


def _make_registry(tmp: Path, prefixes: list[str]) -> Path:
    """构造最小 registry.yaml。"""
    reg = tmp / "docs" / "projects" / "registry.yaml"
    reg.parent.mkdir(parents=True, exist_ok=True)
    lines = ["schema: ccc-project-registry-v1", "projects:"]
    for p in prefixes:
        lines.append(f"  - prefix: {p}")
        lines.append(f"    id: {p}")
        lines.append(f"    name: {p}")
        lines.append(f"    taskable: true")
        lines.append(f"    forbidden: false")
        lines.append(f"    status: active")
    reg.write_text("\n".join(lines))
    return reg


def _make_validate_script(tmp: Path) -> Path:
    """构造一个最小 validate-plans.sh（始终返回 0）。"""
    s = tmp / "scripts" / "validate-plans.sh"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text("#!/usr/bin/env bash\nexit 0\n")
    s.chmod(0o755)
    return s


# ── 1. list_plans ──

class TestListPlans:
    def test_list_all(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc", "xy"])
        _make_plan(tmp_path, "ccc", "001", "test-a", "草案")
        _make_plan(tmp_path, "ccc", "002", "test-b", "已确认")
        _make_plan(tmp_path, "xy", "001", "video", "已确认")

        plans = list_plans(tmp_path)
        assert len(plans) == 3

    def test_filter_by_project(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc", "xy"])
        _make_plan(tmp_path, "ccc", "001", "test-a", "草案")
        _make_plan(tmp_path, "xy", "001", "video", "已确认")

        plans = list_plans(tmp_path, project="ccc")
        assert len(plans) == 1
        assert plans[0]["project"] == "ccc"

    def test_filter_by_status(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_plan(tmp_path, "ccc", "001", "draft", "草案")
        _make_plan(tmp_path, "ccc", "002", "confirmed", "已确认")

        plans = list_plans(tmp_path, status="草案")
        assert len(plans) == 1
        assert plans[0]["status"] == "草案"

    def test_filter_by_keyword(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_plan(tmp_path, "ccc", "001", "upgrade", "草案", title="系统升级方案")
        _make_plan(tmp_path, "ccc", "002", "fix", "已确认", title="修复计划")

        plans = list_plans(tmp_path, q="升级")
        assert len(plans) == 1
        assert "升级" in plans[0]["title"]

    def test_sort_order(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc", "xy"])
        _make_plan(tmp_path, "ccc", "003", "c", "草案")
        _make_plan(tmp_path, "ccc", "001", "a", "草案")
        _make_plan(tmp_path, "ccc", "002", "b", "草案")
        _make_plan(tmp_path, "xy", "001", "x", "草案")

        plans = list_plans(tmp_path)
        # 按 project + num 排序
        ids = [p["id"] for p in plans]
        assert ids == ["ccc-plan-001", "ccc-plan-002", "ccc-plan-003", "xy-plan-001"]


# ── 2. get_plan ──

class TestGetPlan:
    def test_normal_read(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "草案")

        detail = get_plan(tmp_path, str(p.relative_to(tmp_path)))
        assert detail is not None
        assert detail["id"] == "ccc-plan-001"
        assert detail["status"] == "草案"
        assert "## 目标" in detail["content"]

    def test_not_found(self, tmp_path: Path):
        assert get_plan(tmp_path, "docs/projects/ccc/plans/999-nonexistent.md") is None

    def test_invalid_path_format(self, tmp_path: Path):
        """非法路径格式应拒绝。"""
        assert get_plan(tmp_path, "docs/dispatch/ccc/ccc001-test.md") is None

    def test_directory_traversal_rejected(self, tmp_path: Path):
        """../ 目录穿越应拒绝。"""
        assert get_plan(tmp_path, "../etc/passwd") is None
        assert get_plan(tmp_path, "docs/projects/ccc/plans/../../../etc/passwd") is None


# ── 3. create_plan ──

class TestCreatePlan:
    def test_auto_increment(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        _make_plan(tmp_path, "ccc", "001", "existing", "草案")

        result = create_plan(tmp_path, project="ccc", title="新方案",
                             content="## 目标\n\n测试", author="T", tool="T")
        assert result.get("ok")
        assert result["id"] == "ccc-plan-002"

        # cleanup
        (tmp_path / result["path"]).unlink()

    def test_first_plan_num_001(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)

        result = create_plan(tmp_path, project="ccc", title="首个方案",
                             content="## 目标\n\n测试", author="T", tool="T")
        assert result.get("ok")
        assert result["id"] == "ccc-plan-001"

        (tmp_path / result["path"]).unlink()

    def test_invalid_prefix_rejected(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)

        result = create_plan(tmp_path, project="qh", title="非法",
                             content="## 目标", author="T", tool="T")
        assert "error" in result
        assert "无效项目前缀" in result["error"]

    def test_validation_failure_self_delete(self, tmp_path: Path):
        """校验脚本返回非 0 时，创建的文件应自删。"""
        _make_registry(tmp_path, ["ccc"])
        # 构造一个始终失败的校验脚本
        s = tmp_path / "scripts" / "validate-plans.sh"
        s.parent.mkdir(parents=True, exist_ok=True)
        s.write_text("#!/usr/bin/env bash\necho 'FAIL' >&2\nexit 1\n")
        s.chmod(0o755)

        result = create_plan(tmp_path, project="ccc", title="失败方案",
                             content="## 目标", author="T", tool="T")
        assert "error" in result

        # 文件应已自删
        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        md_files = list(plans_dir.glob("*.md")) if plans_dir.exists() else []
        assert len(md_files) == 0, f"文件应已自删，但存在: {md_files}"


# ── 4. update_plan ──

class TestUpdatePlan:
    def test_update_status(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        result = create_plan(tmp_path, project="ccc", title="测试",
                             content="## 目标\n\n测试", author="T", tool="T")
        assert result.get("ok")
        path = result["path"]

        r2 = update_plan(tmp_path, rel_path=path, status="已确认")
        assert r2.get("ok")

        detail = get_plan(tmp_path, path)
        assert detail["status"] == "已确认"

        (tmp_path / path).unlink()

    def test_invalid_status_rejected(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        result = create_plan(tmp_path, project="ccc", title="测试",
                             content="## 目标", author="T", tool="T")
        assert result.get("ok")
        path = result["path"]

        r2 = update_plan(tmp_path, rel_path=path, status="乱写")
        assert "error" in r2
        assert "无效状态" in r2["error"]

        (tmp_path / path).unlink()

    def test_nonexistent_file(self, tmp_path: Path):
        r = update_plan(tmp_path, rel_path="docs/projects/ccc/plans/999-x.md",
                        status="已确认")
        assert "error" in r

    def test_content_replacement_preserves_header(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        result = create_plan(tmp_path, project="ccc", title="测试",
                             content="## 目标\n\n旧内容", author="T", tool="T")
        assert result.get("ok")
        path = result["path"]

        # 替换内容
        r2 = update_plan(tmp_path, rel_path=path, content="## 目标\n\n新内容")
        assert r2.get("ok")

        detail = get_plan(tmp_path, path)
        assert "新内容" in detail["content"]
        assert "项目：ccc" in detail["content"]  # 头部保留
        assert "状态：草案" in detail["content"]  # 头部保留（未改状态）

        (tmp_path / path).unlink()

    def test_update_cards_field(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        result = create_plan(tmp_path, project="ccc", title="测试",
                             content="## 目标\n\n测试", author="T", tool="T")
        assert result.get("ok")
        path = result["path"]

        r2 = update_plan(tmp_path, rel_path=path, cards="ccc001, ccc002")
        assert r2.get("ok")

        detail = get_plan(tmp_path, path)
        assert "ccc001" in detail["cards"]

        (tmp_path / path).unlink()


# ── 5. convert_plan ──

class TestConvertPlan:
    def test_missing_plan_section(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        # 方案没有「转卡计划」段
        p = _make_plan(tmp_path, "ccc", "001", "test", "草案", plan_section="")

        rel = str(p.relative_to(tmp_path))
        result = convert_plan(tmp_path, rel_path=rel)
        assert "error" in result
        assert "转卡计划" in result["error"]

    def test_nonexistent_file(self, tmp_path: Path):
        result = convert_plan(tmp_path, rel_path="docs/projects/ccc/plans/999-x.md")
        assert "error" in result

    def test_invalid_path_format(self, tmp_path: Path):
        result = convert_plan(tmp_path, rel_path="../etc/passwd")
        assert "error" in result


# ── 6. helpers ──

class TestHelpers:
    def test_extract_header_fields(self):
        content = """# 方案 · 测试

> 项目：ccc · 编号：ccc-plan-001 · 状态：草案 · 作者：测试 · 工具：pytest
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无

## 目标
"""
        fields = _extract_header_fields(content)
        assert fields["项目"] == "ccc"
        assert fields["编号"] == "ccc-plan-001"
        assert fields["状态"] == "草案"
        assert fields["作者"] == "测试"

    def test_extract_header_stops_at_blank_line(self):
        """头部提取应在遇到非 > 行时停止，不被后续旧状态字段覆盖。"""
        content = """# 方案 · 测试

> 项目：ccc · 编号：ccc-plan-001 · 状态：作废 · 作者：测试
> 创建：2026-08-09

## 目标

> 旧状态：已确认（这是旧的，不应被提取）
"""
        fields = _extract_header_fields(content)
        assert fields["状态"] == "作废"
        assert "旧状态" not in fields

    def test_extract_title(self):
        assert "测试" in _extract_title("# 方案 · 测试方案")
        assert _extract_title("没有标题") == ""

    def test_extract_acceptance(self):
        content = """## 验收标准

- [x] 已完成
- [ ] 未完成
- [x] 已完成 2
## 其他段
"""
        a = _extract_acceptance(content)
        assert a["total"] == 3
        assert a["done"] == 2