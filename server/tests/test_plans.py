"""server/tests/test_plans.py — 方案读写模块测试（S5 补件 · 2026-08-09）

覆盖：
1. list_plans: 按项目/状态/关键词筛选 + 排序
2. get_plan: 正常读取；非法路径拒绝（含 ../ 目录穿越）
3. create_plan: 自动编号递增；非法前缀拒绝；校验失败自删
4. update_plan: 非法状态拒绝；内容替换保留头部
5. convert_plan: 缺「转卡计划」段报错
6. 前端渲染契约：plansPage.js 结构验证
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAGES_DIR = PROJECT_ROOT / "server" / "web" / "legacy-chat" / "js" / "pages"

# ── helpers ──


def _make_plan(
    tmp: Path,
    prefix: str,
    num: str,
    slug: str,
    status: str,
    title: str = "测试方案",
    author: str = "测试",
    tool: str = "pytest",
    plan_section: str = "",
) -> Path:
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


def _make_registry(tmp: Path, prefixes: list[str], forbidden: set[str] | None = None) -> Path:
    """构造最小 registry.yaml。"""
    forbidden = forbidden or set()
    reg = tmp / "docs" / "projects" / "registry.yaml"
    reg.parent.mkdir(parents=True, exist_ok=True)
    lines = ["schema: ccc-project-registry-v1", "projects:"]
    for p in prefixes:
        lines.append(f"  - prefix: {p}")
        lines.append(f"    id: {p}")
        lines.append(f"    name: {p}")
        lines.append("    taskable: true")
        lines.append(f"    forbidden: {str(p in forbidden).lower()}")
        lines.append("    status: active")
    reg.write_text("\n".join(lines))
    return reg


def _make_validate_script(tmp: Path) -> Path:
    """构造一个最小 validate-plans.sh（始终返回 0）。"""
    s = tmp / "scripts" / "validate-plans.sh"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text("#!/usr/bin/env bash\nexit 0\n")
    s.chmod(0o755)
    return s


def _make_new_card_script(tmp: Path, *, fail_marker: str = "FAIL") -> Path:
    """构造最小 new-card.sh mock：输出真实格式「出卡成功 + validate 通过: <path>」。"""
    s = tmp / "scripts" / "new-card.sh"
    s.parent.mkdir(parents=True, exist_ok=True)
    body = f"""#!/usr/bin/env bash
title=""
project="ccc"
while [ $# -gt 0 ]; do
  case "$1" in
    --title) title="$2"; shift 2 ;;
    --project) project="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if printf '%s' "$title" | grep -q '{fail_marker}'; then
  echo "[ERROR] mock fail: $title" >&2
  exit 1
fi
f="docs/dispatch/${{project}}/${{project}}999-mock.md"
mkdir -p "$(dirname "$f")"
printf '# 任务卡 %s999\\n' "$project" > "$f"
echo "[OK] 出卡成功 + validate 通过: $f"
"""
    s.write_text(body)
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

        result = create_plan(tmp_path, project="ccc", title="新方案", content="## 目标\n\n测试", author="T", tool="T")
        assert result.get("ok")
        assert result["id"] == "ccc-plan-002"

        # cleanup
        (tmp_path / result["path"]).unlink()

    def test_first_plan_num_001(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)

        result = create_plan(tmp_path, project="ccc", title="首个方案", content="## 目标\n\n测试", author="T", tool="T")
        assert result.get("ok")
        assert result["id"] == "ccc-plan-001"

        (tmp_path / result["path"]).unlink()

    def test_invalid_prefix_rejected(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)

        result = create_plan(tmp_path, project="qh", title="非法", content="## 目标", author="T", tool="T")
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

        result = create_plan(tmp_path, project="ccc", title="失败方案", content="## 目标", author="T", tool="T")
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
        result = create_plan(tmp_path, project="ccc", title="测试", content="## 目标\n\n测试", author="T", tool="T")
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
        result = create_plan(tmp_path, project="ccc", title="测试", content="## 目标", author="T", tool="T")
        assert result.get("ok")
        path = result["path"]

        r2 = update_plan(tmp_path, rel_path=path, status="乱写")
        assert "error" in r2
        assert "无效状态" in r2["error"]

        (tmp_path / path).unlink()

    def test_nonexistent_file(self, tmp_path: Path):
        r = update_plan(tmp_path, rel_path="docs/projects/ccc/plans/999-x.md", status="已确认")
        assert "error" in r

    def test_content_replacement_preserves_header(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        result = create_plan(tmp_path, project="ccc", title="测试", content="## 目标\n\n旧内容", author="T", tool="T")
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
        result = create_plan(tmp_path, project="ccc", title="测试", content="## 目标\n\n测试", author="T", tool="T")
        assert result.get("ok")
        path = result["path"]

        r2 = update_plan(tmp_path, rel_path=path, cards="ccc001, ccc002")
        assert r2.get("ok")

        detail = get_plan(tmp_path, path)
        assert "ccc001" in detail["cards"]

        (tmp_path / path).unlink()

    def test_transition_draft_to_done_rejected(self, tmp_path: Path):
        """草案到已完成应被拒绝。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        result = create_plan(tmp_path, project="ccc", title="test", content="## ok", author="T", tool="T")
        assert result.get("ok")
        path = result["path"]

        r2 = update_plan(tmp_path, rel_path=path, status="已完成")
        assert "error" in r2
        assert "流转非法" in r2["error"]

        (tmp_path / path).unlink()

    def test_transition_done_to_draft_rejected(self, tmp_path: Path):
        """已完成到草案应被拒绝（终态不可改）。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        result = create_plan(tmp_path, project="ccc", title="test", content="## ok", author="T", tool="T")
        assert result.get("ok")
        path = result["path"]

        # 合法流转到已完成
        update_plan(tmp_path, rel_path=path, status="已确认")
        update_plan(tmp_path, rel_path=path, status="部分执行")
        update_plan(tmp_path, rel_path=path, status="已完成")

        # 已完成到草案应拒绝
        r2 = update_plan(tmp_path, rel_path=path, status="草案")
        assert "error" in r2

        (tmp_path / path).unlink()

    def test_transition_confirm_to_partial_allowed(self, tmp_path: Path):
        """已确认到部分执行应放行（转卡自动推进）。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        result = create_plan(tmp_path, project="ccc", title="test", content="## ok", author="T", tool="T")
        assert result.get("ok")
        path = result["path"]

        # 草案到已确认（合法）
        update_plan(tmp_path, rel_path=path, status="已确认")
        # 已确认到部分执行（合法）
        r2 = update_plan(tmp_path, rel_path=path, status="部分执行")
        assert r2.get("ok")

        (tmp_path / path).unlink()


# ── 5. convert_plan ──


class TestConvertPlan:
    def test_missing_plan_section(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        # 使用已确认状态，避免被草案拦截
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确认", plan_section="")

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

    def test_convert_draft_rejected(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        p = _make_plan(tmp_path, "ccc", "001", "test", "草案", plan_section="- test card")
        rel = str(p.relative_to(tmp_path))
        result = convert_plan(tmp_path, rel_path=rel)
        assert "error" in result
        assert "不可转卡" in result["error"]

    def test_convert_completed_rejected(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        p = _make_plan(tmp_path, "ccc", "001", "test", "已完成", plan_section="- test card")
        rel = str(p.relative_to(tmp_path))
        result = convert_plan(tmp_path, rel_path=rel)
        assert "error" in result
        assert "不可转卡" in result["error"]

    def test_forbidden_prefix_rejected(self, tmp_path: Path):
        """禁出卡前缀（平台自研红线）禁止转卡，方案仍可存在。"""
        _make_registry(tmp_path, ["ccc"], forbidden={"ccc"})
        _make_validate_script(tmp_path)
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确认", plan_section="- alpha")
        rel = str(p.relative_to(tmp_path))
        result = convert_plan(tmp_path, rel_path=rel)
        assert "error" in result
        assert "禁出卡" in result["error"]

    def test_convert_success_no_push(self, tmp_path: Path):
        """成功路径：生成卡 + 状态推进 + 关联卡写入（no_push 跳过 git）。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        _make_new_card_script(tmp_path)
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确认", plan_section="- alpha")
        rel = str(p.relative_to(tmp_path))
        result = convert_plan(tmp_path, rel_path=rel, no_push=True)
        assert result.get("ok") is True
        assert result["cards"] == ["ccc999"]
        content = p.read_text()
        assert "状态：部分执行" in content
        assert "关联卡：ccc999" in content
        assert (tmp_path / "docs" / "dispatch" / "ccc" / "ccc999-mock.md").exists()

    def test_convert_partial_failure_rolls_back(self, tmp_path: Path):
        """部分失败：已生成卡回滚，方案状态不推进，重试不产生重复卡。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        _make_new_card_script(tmp_path)
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确认", plan_section="- alpha\n- FAIL")
        rel = str(p.relative_to(tmp_path))
        result = convert_plan(tmp_path, rel_path=rel)
        assert "error" in result
        assert not (tmp_path / "docs" / "dispatch" / "ccc" / "ccc999-mock.md").exists()
        assert "状态：已确认" in p.read_text()


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

    def test_extract_acceptance_ignores_prose(self):
        """验收统计只计 checkbox 行，说明文字/子标题不计。"""
        content = """## 验收标准

- [x] 已完成
说明文字不算
- [ ] 未完成
### 子标题
- [x] 完成 2
## 其他段
"""
        a = _extract_acceptance(content)
        assert a["total"] == 3
        assert a["done"] == 2

    def test_create_empty_author_rejected(self, tmp_path: Path):
        """空作者应被拒绝。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        result = create_plan(tmp_path, project="ccc", title="test", content="## ok", author="", tool="T")
        assert "error" in result
        assert "作者" in result["error"]


# ── 7. 前端渲染契约 ──


class TestPlansPageContract:
    """plansPage.js 前端渲染契约（静态断言，无 JS 运行时）。"""

    @staticmethod
    def _page() -> str:
        return (PAGES_DIR / "plansPage.js").read_text(encoding="utf-8")

    def test_file_exists(self) -> None:
        assert (PAGES_DIR / "plansPage.js").exists()

    def test_exports_mount(self) -> None:
        text = self._page()
        assert "export async function mountPlans" in text
        assert "export function unmountPlans" in text

    def test_api_endpoints(self) -> None:
        """验证前端调用了正确的 API 端点。"""
        text = self._page()
        assert "/plans/list" in text
        assert "/plans/detail" in text
        assert "/plans/create" in text
        assert "/plans/update" in text
        assert "/plans/convert" in text

    def test_filter_controls(self) -> None:
        """验证筛选控件存在（plansPage 重写后契约：项目按钮 ptool-proj + 状态 select + 搜索）。"""
        text = self._page()
        assert "ptool-proj" in text
        assert "plans-status-select" in text
        assert "plans-search" in text

    def test_convert_button(self) -> None:
        """验证转卡按钮存在且由人触发（confirm 弹窗）。"""
        text = self._page()
        assert "转为任务卡" in text
        assert "confirm" in text

    def test_has_grid_layout(self) -> None:
        """验证卡片网格布局（重写后为 plans-flow 流式布局）。"""
        text = self._page()
        assert "plans-flow" in text

    def test_create_form(self) -> None:
        """验证新建表单存在。"""
        text = self._page()
        assert "plans-btn-new" in text
        assert "plans-form-overlay" in text
        assert "plans-form-project" in text
        assert "plans-form-title" in text

    def test_author_required(self) -> None:
        """验证作者必填校验。"""
        text = self._page()
        assert "作者不能为空" in text

    def test_dynamic_projects(self) -> None:
        """验证动态项目加载。"""
        text = self._page()
        assert "loadProjects" in text
        assert "_projects" in text

    def test_convert_line_limit(self) -> None:
        """验证转卡计划 8 行限制。"""
        text = self._page()
        assert "8 行" in text or "lines.length > 8" in text
        assert "plans-form-project" in text
        assert "plans-form-title" in text

    def test_status_filter_options(self) -> None:
        """验证状态筛选包含五态。"""
        text = self._page()
        for s in ["草案", "已确认", "部分执行", "已完成", "作废"]:
            assert s in text, f"Missing status: {s}"

    def test_markdown_renders_links_and_tables(self) -> None:
        text = self._page()
        assert "_blank" in text
        assert "pre" in text.lower()
        assert "ul" in text.lower()
        assert "table" in text.lower()

    def test_auto_refresh(self) -> None:
        """验证 30s 自动刷新 + 状态保护（详情/表单打开时不重建 DOM）。"""
        text = self._page()
        assert "setInterval" in text
        assert "30000" in text
        assert "_detailPath" in text
        assert "_formOpen" in text
        assert "updateListOnly" in text


# ── 8. validate-plans.sh 脚本测试 ──


class TestValidatePlansScript:
    """Test the scripts/validate-plans.sh script directly."""

    @staticmethod
    def _setup_script(tmp: Path) -> Path:
        # Copy the real validate-plans.sh to tmp/scripts/
        real_script = PROJECT_ROOT / "scripts" / "validate-plans.sh"
        dest_dir = tmp / "scripts"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_script = dest_dir / "validate-plans.sh"
        dest_script.write_text(real_script.read_text())
        dest_script.chmod(0o755)
        return dest_script

    def test_script_valid_plan(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        script = self._setup_script(tmp_path)

        # Create a valid card and a plan referring to it
        # Cards are in docs/dispatch/
        dispatch_dir = tmp_path / "docs" / "dispatch"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        card_file = dispatch_dir / "ccc001-test.md"
        card_file.write_text("# 卡1\n\n> 状态：开发中\n")

        # Create a plan (status: 部分执行)
        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / "001-test.md"
        plan_file.write_text(
            "# 方案 · 测试\n\n"
            "> 项目：ccc · 编号：ccc-plan-001 · 状态：部分执行 · 作者：T · 工具：T\n"
            "> 创建：2026-08-10 · 更新：2026-08-10\n"
            "> 关联卡：ccc001\n"
            "> 关联方案：无\n\n"
            "## 目标\n\n测试\n\n"
            "## 验收标准\n\n- [ ] 测试验收\n"
        )

        import subprocess
        result = subprocess.run(["bash", str(script), str(plan_file)], capture_output=True, text=True)
        assert result.returncode == 0

    def test_script_completed_but_unchecked(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        script = self._setup_script(tmp_path)

        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / "001-test.md"
        plan_file.write_text(
            "# 方案 · 测试\n\n"
            "> 项目：ccc · 编号：ccc-plan-001 · 状态：已完成 · 作者：T · 工具：T\n"
            "> 创建：2026-08-10 · 更新：2026-08-10\n"
            "> 关联卡：无\n"
            "> 关联方案：无\n\n"
            "## 目标\n\n测试\n\n"
            "## 验收标准\n\n- [ ] 测试验收\n"
        )

        import subprocess
        result = subprocess.run(["bash", str(script), str(plan_file)], capture_output=True, text=True)
        assert result.returncode != 0
        assert "验收未勾选" in result.stdout

    def test_script_completed_and_checked(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        script = self._setup_script(tmp_path)

        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / "001-test.md"
        plan_file.write_text(
            "# 方案 · 测试\n\n"
            "> 项目：ccc · 编号：ccc-plan-001 · 状态：已完成 · 作者：T · 工具：T\n"
            "> 创建：2026-08-10 · 更新：2026-08-10\n"
            "> 关联卡：无\n"
            "> 关联方案：无\n\n"
            "## 目标\n\n测试\n\n"
            "## 验收标准\n\n- [x] 测试验收\n"
        )

        import subprocess
        result = subprocess.run(["bash", str(script), str(plan_file)], capture_output=True, text=True)
        assert result.returncode == 0

    def test_script_cards_all_closed_but_not_advanced(self, tmp_path: Path):
        _make_registry(tmp_path, ["ccc"])
        script = self._setup_script(tmp_path)

        dispatch_dir = tmp_path / "docs" / "dispatch"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        card_file = dispatch_dir / "ccc001-test.md"
        card_file.write_text("# 卡1\n\n> 状态：已关闭\n")

        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / "001-test.md"
        plan_file.write_text(
            "# 方案 · 测试\n\n"
            "> 项目：ccc · 编号：ccc-plan-001 · 状态：部分执行 · 作者：T · 工具：T\n"
            "> 创建：2026-08-10 · 更新：2026-08-10\n"
            "> 关联卡：ccc001\n"
            "> 关联方案：无\n\n"
            "## 目标\n\n测试\n\n"
            "## 验收标准\n\n- [ ] 测试验收\n"
        )

        import subprocess
        result = subprocess.run(["bash", str(script), str(plan_file)], capture_output=True, text=True)
        assert result.returncode != 0
        assert "关联卡已全部关闭但状态仍为" in result.stdout
