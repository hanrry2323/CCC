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

import re
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.board.plans import (
    VALID_STATES,
    accept_plan,
    convert_plan,
    create_plan,
    get_plan,
    list_plans,
    update_plan,
    sync_plan_progress,
    _void_cascade_cards,
    _extract_header_fields,
    _extract_title,
    _extract_acceptance,
    _extract_func_cards,
    _inject_func_card,
    _split_deps,
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


def _make_unique_new_card_script(tmp: Path) -> Path:
    """new-card.sh mock：每次调用生成唯一卡 ID（ccc001, ccc002, ...），供 slices/依赖测试。"""
    s = tmp / "scripts" / "new-card.sh"
    s.parent.mkdir(parents=True, exist_ok=True)
    body = """#!/usr/bin/env bash
project="ccc"
while [ $# -gt 0 ]; do
  case "$1" in
    --project) project="$2"; shift 2 ;;
    *) shift ;;
  esac
done
n=0
for f in docs/dispatch/$project/$project[0-9][0-9][0-9]-*.md; do
  [ -e "$f" ] || continue
  b=$(basename "$f" .md)
  if [[ "$b" =~ ^$project([0-9]{3}) ]]; then
    x=$((10#${BASH_REMATCH[1]}))
    (( x > n )) && n=$x
  fi
done
n=$((n+1))
nn=$(printf '%03d' "$n")
f="docs/dispatch/$project/$project$nn-mock.md"
mkdir -p "$(dirname "$f")"
printf '# 任务卡 %s%s\\n' "$project" "$nn" > "$f"
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

        # Phase2：create_plan 默认状态 = 已确认；更新为部分执行（合法流转）
        r2 = update_plan(tmp_path, rel_path=path, status="部分执行")
        assert r2.get("ok")

        detail = get_plan(tmp_path, path)
        assert detail["status"] == "部分执行"

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
        assert "状态：已确认" in detail["content"]  # 头部保留（Phase2 默认已确认，未改状态）

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

    def test_extract_header_fields_value_with_middle_dot(self):
        """033 M5：字段值含「 · 」不截断（里程碑标题 M2 · 稳控与可恢复 保持完整）。"""
        fields = _extract_header_fields(
            "> 项目：hp · 编号：hp-plan-008 · 状态：已确认 · 里程碑：M2 · 稳控与可恢复 · 作者：x"
        )
        assert fields.get("里程碑") == "M2 · 稳控与可恢复", fields
        assert fields.get("编号") == "hp-plan-008"
        assert fields.get("状态") == "已确认"

    def test_accept_plan_requires_daiyanshou(self, tmp_path: Path):
        """033 M4：accept_plan 仅对「待验收」方案生效；验收标准未勾选拒绝；拍板置已完成+批准行。"""
        _make_registry(tmp_path, ["ccc"])
        # 待验收方案 → 拍板成功（先全勾选验收项，_make_plan 默认 1 未勾）
        p = _make_plan(tmp_path, "ccc", "001", "test", "待验收")
        p.write_text(p.read_text().replace("- [ ] 测试项 1", "- [x] 测试项 1"))
        rel = str(p.relative_to(tmp_path))
        with patch("server.board.plans._git_commit_push", return_value=(True, "")):
            r = accept_plan(tmp_path, rel_path=rel)
        assert r.get("ok") is True, r
        assert "状态：已完成" in p.read_text()
        assert "老板验收拍板" in p.read_text()
        # 非待验收方案拒绝
        p2 = _make_plan(tmp_path, "ccc", "002", "test2", "已确认")
        r2 = accept_plan(tmp_path, rel_path=str(p2.relative_to(tmp_path)))
        assert "error" in r2
        # 待验收但验收标准未勾选拒绝
        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        p3 = plans_dir / "003-test3.md"
        p3.write_text(
            """# 方案 · 测试3

> 项目：ccc · 编号：ccc-plan-003 · 状态：待验收 · 作者：测试 · 工具：pytest
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无

## 目标

测试。

## 验收标准

- [ ] 未勾选项

""",
            encoding="utf-8",
        )
        r3 = accept_plan(tmp_path, rel_path="docs/projects/ccc/plans/003-test3.md")
        assert "error" in r3 and "验收标准" in r3["error"]

    def test_update_plan_yididing_transitions(self, tmp_path: Path):
        """033 F1：已确定 可流转到 已确认/作废，不可直跳已完成（白名单）。"""
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确定")
        rel = str(p.relative_to(tmp_path))
        with patch("server.board.plans._git_commit_push", return_value=(True, "")):
            # 已确定 → 已确认 允许（老板确认排队）
            r1 = update_plan(tmp_path, rel_path=rel, status="已确认")
            assert r1.get("ok") is True, r1
            # 已确认 → 已完成 拒绝（白名单不含）
            r2 = update_plan(tmp_path, rel_path=rel, status="已完成")
            assert "error" in r2

    def test_update_plan_date_not_corrupted(self, tmp_path: Path):
        """2026-08-16 机审修复（缺陷3）：update_plan 更新日期不被 `\\1{` 组引用歧义破坏（改用 `\\g<1>`）。"""
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确认")
        rel = str(p.relative_to(tmp_path))
        with patch("server.board.plans._git_commit_push", return_value=(True, "")):
            result = update_plan(tmp_path, rel_path=rel, status="部分执行")
        assert result.get("ok") is True
        text = p.read_text()
        assert re.search(r"更新：\d{4}-\d{2}-\d{2}", text), f"更新日期被破坏（\\1 组引用歧义）: {text}"
        assert "P2" not in text

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
        """验证转卡按钮存在且由人触发（027：节点②功能卡清单确认弹层）。"""
        text = self._page()
        assert "转为任务卡" in text
        assert "确认转卡" in text
        assert "_showConvertOverlay" in text

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
        """验证转卡支持功能卡清单（027：无 8 行限制，功能卡段优先解析）。"""
        text = self._page()
        assert "_parseFuncCards" in text
        assert "8 行" not in text
        assert "plans-form-project" in text
        assert "plans-form-title" in text

    def test_status_filter_options(self) -> None:
        """验证状态筛选为四态（草案已移除 · Bug 8）。"""
        text = self._page()
        for s in ["已确认", "部分执行", "已完成", "作废"]:
            assert s in text, f"Missing status: {s}"
        # 草案不再是流程列（Phase2 /plans/create 默认已确认，list 默认过滤草案）
        assert "状态（草案/已确认" not in text

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
        assert "关联卡已全部关闭/作废但状态仍为" in result.stdout


# ── 9. sync_plan_progress 测试 ──


class TestSyncPlanProgress:
    """Phase 4.1：方案进度自动回写测试。"""

    def test_no_cards(self, tmp_path: Path) -> None:
        """无关联卡时，进度为 0/0。"""
        _make_registry(tmp_path, ["ccc"])
        _make_plan(tmp_path, "ccc", "001", "test", "已确认")

        # 构造空的 cards.index.jsonl
        dispatch_dir = tmp_path / "docs" / "dispatch"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        idx_path = dispatch_dir / "cards.index.jsonl"
        idx_path.write_text("", encoding="utf-8")

        with patch("server.board.loader.load_index_file", return_value={}):
            result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
            assert result.get("ok") is True
            assert result["progress"]["total"] == 0
            assert result["progress"]["closed"] == 0

    def test_cards_set_to_none(self, tmp_path: Path) -> None:
        """关联卡字段为「无」时，进度为 0/0。"""
        _make_registry(tmp_path, ["ccc"])
        _make_plan(tmp_path, "ccc", "001", "test", "已确认")

        result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
        assert result.get("ok") is True
        assert result["progress"]["total"] == 0

    def test_with_cards(self, tmp_path: Path) -> None:
        """有 3 张关联卡，其中 2 张已关闭 → 进度 2/3 (66%)。"""
        _make_registry(tmp_path, ["ccc"])
        # 更新方案关联卡字段
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确认")
        content = p.read_text()
        content = content.replace("关联卡：无", "关联卡：ccc001, ccc002, ccc003")
        p.write_text(content)

        mock_index = {
            "ccc001": {"id": "ccc001", "state": "已关闭", "path": "docs/dispatch/ccc001-a.md"},
            "ccc002": {"id": "ccc002", "state": "已关闭", "path": "docs/dispatch/ccc002-b.md"},
            "ccc003": {"id": "ccc003", "state": "执行中", "path": "docs/dispatch/ccc003-c.md"},
        }
        with patch("server.board.loader.load_index_file", return_value=mock_index):
            result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
            assert result.get("ok") is True
            assert result["progress"]["total"] == 3
            assert result["progress"]["closed"] == 2
            assert result["progress"]["progress_pct"] == 66

            # 验证文件回写
            updated = p.read_text()
            assert "进度：2/3 (66%)" in updated

    def test_all_cards_closed(self, tmp_path: Path) -> None:
        """全部卡已关闭 → 进度 2/2 (100%)。"""
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确认")
        content = p.read_text()
        content = content.replace("关联卡：无", "关联卡：ccc001, ccc002")
        p.write_text(content)

        mock_index = {
            "ccc001": {"id": "ccc001", "state": "已关闭", "path": "x"},
            "ccc002": {"id": "ccc002", "state": "已关闭", "path": "x"},
        }
        with patch("server.board.loader.load_index_file", return_value=mock_index):
            result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
            assert result["progress"]["progress_pct"] == 100
            assert "进度：2/2 (100%)" in p.read_text()

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/999-x.md")
        assert "error" in result

    def test_invalid_path(self, tmp_path: Path) -> None:
        result = sync_plan_progress(tmp_path, "../etc/passwd")
        assert "error" in result

    def test_progress_field_update(self, tmp_path: Path) -> None:
        """已有进度字段时，应原地更新而非新增行。"""
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确认")
        content = p.read_text()
        content = content.replace("关联卡：无", "关联卡：ccc001")
        # 手动插入旧进度
        content = content.replace("关联方案：无\n", "关联方案：无\n> 进度：0/1 (0%)\n")
        p.write_text(content)

        mock_index = {"ccc001": {"id": "ccc001", "state": "已关闭", "path": "x"}}
        with patch("server.board.loader.load_index_file", return_value=mock_index):
            sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
            updated = p.read_text()
            # 应该是更新后的值，不是旧值
            assert "进度：1/1 (100%)" in updated
            # 只应出现一次进度行
            assert updated.count("进度：") == 1


# ── ccc-plan-027 核心流程：里程碑字段 / 功能卡段 / 自动完成 / 双向同步 ──


class Test027CoreFlow:
    def test_extract_func_cards(self):
        """功能卡段解析：### 小节 → {title, goal, impl, acceptance}。"""
        content = """## 目标

测试。

## 功能卡

### 登录功能
目标：实现登录页与接口。
实现：页面布局、API 对接、token 存储。
验收：登录成功跳转首页。

### 播放功能
目标：实现播放页。

## 备注

无
"""
        cards = _extract_func_cards(content)
        assert len(cards) == 2
        assert cards[0]["title"] == "登录功能"
        assert cards[0]["goal"] == "实现登录页与接口。"
        assert "API" in cards[0]["impl"]
        assert cards[0]["acceptance"] == "登录成功跳转首页。"
        assert cards[1]["title"] == "播放功能"
        assert cards[1]["goal"] == "实现播放页。"

    def test_extract_func_cards_absent(self):
        """无功能卡段 → 返回空列表。"""
        assert _extract_func_cards("## 目标\n\n无功能卡") == []

    def test_split_deps_strips_none_annotation(self):
        """2026-08-16 机审修复：依赖以「无」开头（含注解形态）→ 无依赖，不拆成伪依赖。"""
        assert _split_deps("") == []
        assert _split_deps("无") == []
        assert _split_deps("无（2026-08-16 三要素：待老板单独确认敏感清洗后再转卡执行）") == []
        assert _split_deps("无依赖。") == []
        assert _split_deps("hp023, hp024") == ["hp023", "hp024"]
        assert _split_deps("播放功能, hp009") == ["播放功能", "hp009"]

    def test_create_plan_milestone_field(self, tmp_path: Path):
        """create_plan 带 milestone：头部写「里程碑：标题」；roadmap.md linked_plans 同步。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        # 构造含里程碑的 roadmap.md
        rm_dir = tmp_path / "docs" / "projects" / "ccc"
        rm_dir.mkdir(parents=True, exist_ok=True)
        (rm_dir / "roadmap.md").write_text(
            "# 测试线路图\n\n> 项目：ccc · 更新：2026-08-09\n\n## 草案池\n\n无。\n\n## 里程碑\n\n### 我的里程碑\n- 状态：进行中\n",
            encoding="utf-8",
        )
        with patch("server.board.plans._git_commit_push", return_value=(True, "")):
            with patch("server.board.roadmap._repo_root", return_value=tmp_path):
                result = create_plan(
                    tmp_path, project="ccc", title="带里程碑方案", content="## 目标\n\ntest",
                    author="测试", tool="pytest", milestone="我的里程碑",
                )
        assert result.get("ok") is True
        p = tmp_path / "docs" / "projects" / "ccc" / "plans" / "001-task.md"
        assert "里程碑：我的里程碑" in p.read_text()
        # roadmap.md 同步：里程碑 linked_plans 包含该方案
        rm = (rm_dir / "roadmap.md").read_text()
        assert "关联方案：ccc-plan-001" in rm

    def test_convert_func_cards_success(self, tmp_path: Path):
        """convert 优先读功能卡段：按小节出卡 + 状态推进部分执行 + 关联卡写入。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        _make_new_card_script(tmp_path)
        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        p = plans_dir / "001-fc.md"
        p.write_text(
            """# 方案 · 功能卡测试

> 项目：ccc · 编号：ccc-plan-001 · 状态：已确认 · 作者：测试 · 工具：pytest
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无

## 目标

测试。

## 功能卡

### 登录功能
目标：实现登录页与接口。
""",
            encoding="utf-8",
        )
        result = convert_plan(tmp_path, rel_path=str(p.relative_to(tmp_path)), no_push=True)
        assert result.get("ok") is True
        assert result["cards"] == ["ccc999"]
        assert "状态：部分执行" in p.read_text()
        assert "关联卡：ccc999" in p.read_text()

    def test_convert_slices_subset(self, tmp_path: Path):
        """2026-08-16 逐步投入：slices 指定时只转该子集功能卡；不在方案的 slices 报错。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        _make_unique_new_card_script(tmp_path)
        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        p = plans_dir / "001-fc.md"
        p.write_text(
            """# 方案 · 功能卡测试

> 项目：ccc · 编号：ccc-plan-001 · 状态：已确认 · 作者：测试 · 工具：pytest
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无

## 目标

测试。

## 功能卡

### 登录功能
目标：登录。
颗粒度：登录页+接口。
依赖：无
架构位置：web

### 播放功能
目标：播放。
颗粒度：播放器。
依赖：无
架构位置：player
""",
            encoding="utf-8",
        )
        rel = str(p.relative_to(tmp_path))
        # 只转「登录功能」
        result = convert_plan(tmp_path, rel_path=rel, slices=["登录功能"], no_push=True)
        assert result.get("ok") is True
        assert result["cards"] == ["ccc001"]
        assert "关联卡：ccc001" in p.read_text()
        # 指定的不存在功能卡 → 报错
        result2 = convert_plan(tmp_path, rel_path=rel, slices=["不存在的卡"], no_push=True)
        assert "error" in result2
        assert "不在方案中" in result2["error"]

    def test_convert_dep_hard_constraint(self, tmp_path: Path):
        """2026-08-16 依赖硬约束：被依赖不在本批且非已有关卡 → 拒绝出卡。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        _make_unique_new_card_script(tmp_path)
        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        p = plans_dir / "001-fc.md"
        p.write_text(
            """# 方案 · 功能卡测试

> 项目：ccc · 编号：ccc-plan-001 · 状态：已确认 · 作者：测试 · 工具：pytest
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无

## 目标

测试。

## 功能卡

### 登录功能
目标：登录。
依赖：播放功能

### 播放功能
目标：播放。
依赖：无
""",
            encoding="utf-8",
        )
        rel = str(p.relative_to(tmp_path))
        # 只转「登录功能」：依赖「播放功能」不在本批 → 拒绝
        result = convert_plan(tmp_path, rel_path=rel, slices=["登录功能"], no_push=True)
        assert "error" in result
        assert "依赖" in result["error"]
        # 全部转：播放功能在本批 → 通过
        result2 = convert_plan(tmp_path, rel_path=rel, no_push=True)
        assert result2.get("ok") is True

        # 依赖不存在的卡 ID → 拒绝（即使全量转）
        p2 = plans_dir / "002-fc.md"
        p2.write_text(
            """# 方案 · 依赖悬空

> 项目：ccc · 编号：ccc-plan-002 · 状态：已确认 · 作者：测试 · 工具：pytest
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无

## 目标

测试。

## 功能卡

### 登录功能
目标：登录。
依赖：ccc999
""",
            encoding="utf-8",
        )
        result3 = convert_plan(tmp_path, rel_path=str(p2.relative_to(tmp_path)), no_push=True)
        assert "error" in result3
        assert "ccc999" in result3["error"]

    def test_convert_dep_passthrough(self, tmp_path: Path):
        """2026-08-16 依赖透传：同批依赖 → 解析为卡 ID 写回卡头「> 依赖：」。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        _make_unique_new_card_script(tmp_path)
        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        p = plans_dir / "001-fc.md"
        p.write_text(
            """# 方案 · 功能卡测试

> 项目：ccc · 编号：ccc-plan-001 · 状态：已确认 · 作者：测试 · 工具：pytest
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无

## 目标

测试。

## 功能卡

### 登录功能
目标：登录。
依赖：播放功能

### 播放功能
目标：播放。
依赖：无
""",
            encoding="utf-8",
        )
        result = convert_plan(tmp_path, rel_path=str(p.relative_to(tmp_path)), no_push=True)
        assert result.get("ok") is True
        # 登录→ccc001，播放→ccc002；登录卡头写「> 依赖：ccc002」
        assert result["cards"] == ["ccc001", "ccc002"]
        card1 = tmp_path / "docs" / "dispatch" / "ccc" / "ccc001-mock.md"
        assert "> 依赖：ccc002" in card1.read_text()
        card2 = tmp_path / "docs" / "dispatch" / "ccc" / "ccc002-mock.md"
        assert "> 依赖：" not in card2.read_text()

    def test_convert_env_prep_gate(self, tmp_path: Path):
        """2026-08-16 环境准备门禁：子项目方案缺「环境准备」声明 → 拒绝转卡。"""
        _make_registry(tmp_path, ["ccc"])
        _make_validate_script(tmp_path)
        _make_unique_new_card_script(tmp_path)
        plans_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        p = plans_dir / "001-fc.md"
        p.write_text(
            """# 方案 · 环境准备测试

> 项目：ccc · 编号：ccc-plan-001 · 状态：已确认 · 作者：测试 · 工具：pytest
> 创建：2026-08-09 · 更新：2026-08-09
> 关联卡：无
> 关联方案：无
> 里程碑：M1
> 子项目：1.1 测试子项目

## 目标

测试。

## 功能卡

### 功能A
目标：A。
颗粒度：小。
依赖：无
架构位置：web
""",
            encoding="utf-8",
        )
        rel = str(p.relative_to(tmp_path))
        # 缺环境准备声明 → 拒绝
        result = convert_plan(tmp_path, rel_path=rel, no_push=True)
        assert "error" in result
        assert "环境准备" in result["error"]
        # 补上环境准备 → 通过
        p.write_text(
            p.read_text().replace(
                "> 子项目：1.1 测试子项目\n",
                "> 子项目：1.1 测试子项目\n> 环境准备：已具备\n",
            )
        )
        result2 = convert_plan(tmp_path, rel_path=rel, no_push=True)
        assert result2.get("ok") is True

    def test_inject_func_card(self, tmp_path: Path):
        """功能卡注入：目标替换占位、实现插入 ## 实现 段、验收替换占位。"""
        card = tmp_path / "c.md"
        card.write_text(
            "# 任务卡 ccc001\n\n## 目标\n\n（一句话，可验收。）\n\n## 红线（先看）\n\n## 验收标准\n\n1. （可执行的验收点，附命令/可观察结果）\n",
            encoding="utf-8",
        )
        _inject_func_card(card, {"title": "登录", "goal": "实现登录页。", "impl": "页面+接口+存储。", "acceptance": "登录成功跳转。"})
        text = card.read_text()
        assert "实现登录页。" in text
        assert "## 实现" in text
        assert "页面+接口+存储。" in text
        assert "登录成功跳转。" in text

    def test_sync_plan_progress_auto_complete(self, tmp_path: Path):
        """033 M4：关联卡全关 → 方案自动推进「待验收」（非已完成，等老板/验收席拍板）。"""
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "部分执行")
        content = p.read_text()
        content = content.replace("关联卡：无", "关联卡：ccc001")
        p.write_text(content)
        mock_index = {"ccc001": {"id": "ccc001", "state": "已关闭", "path": "x"}}
        with patch("server.board.loader.load_index_file", return_value=mock_index):
            result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
        assert result.get("auto_completed") is True
        assert "状态：待验收" in p.read_text()
        assert "进度：1/1 (100%)" in p.read_text()

    def test_sync_plan_progress_not_all_closed(self, tmp_path: Path):
        """卡未全关 → 不自动完成。"""
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "部分执行")
        content = p.read_text()
        content = content.replace("关联卡：无", "关联卡：ccc001")
        p.write_text(content)
        mock_index = {"ccc001": {"id": "ccc001", "state": "执行中", "path": "x"}}
        with patch("server.board.loader.load_index_file", return_value=mock_index):
            result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
        assert result.get("auto_completed") is False
        assert "状态：部分执行" in p.read_text()

    def test_voided_cards_excluded_from_total(self, tmp_path: Path):
        """作废卡从总数剔除（人审统一化）：1 关 + 1 作废 + 1 执行中 → 活跃 2，进度 1/2。"""
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "部分执行")
        content = p.read_text()
        content = content.replace("关联卡：无", "关联卡：ccc001, ccc002, ccc003")
        p.write_text(content)
        mock_index = {
            "ccc001": {"id": "ccc001", "state": "已关闭", "path": "x"},
            "ccc002": {"id": "ccc002", "state": "作废", "path": "x"},
            "ccc003": {"id": "ccc003", "state": "执行中", "path": "x"},
        }
        with patch("server.board.loader.load_index_file", return_value=mock_index):
            result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
        # total 口径 = 活跃卡（剔除作废）
        assert result["progress"]["total"] == 2
        assert result["progress"]["closed"] == 1
        assert result["progress"]["progress_pct"] == 50
        assert result.get("auto_completed") is False
        assert "进度：1/2 (50%)（作废 1）" in p.read_text()

    def test_remaining_active_all_closed_with_voided_completes(self, tmp_path: Path):
        """033 M4：活跃卡全关（含部分作废）→ 方案自动置「待验收」（非已完成）。"""
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "部分执行")
        content = p.read_text()
        content = content.replace("关联卡：无", "关联卡：ccc001, ccc002")
        p.write_text(content)
        mock_index = {
            "ccc001": {"id": "ccc001", "state": "已关闭", "path": "x"},
            "ccc002": {"id": "ccc002", "state": "作废", "path": "x"},
        }
        with patch("server.board.loader.load_index_file", return_value=mock_index):
            result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
        assert result.get("auto_completed") is True
        assert "状态：待验收" in p.read_text()

    def test_all_voided_auto_void_plan(self, tmp_path: Path):
        """全作废边界：全部关联卡作废 → 方案自动置「作废」。"""
        _make_registry(tmp_path, ["ccc"])
        p = _make_plan(tmp_path, "ccc", "001", "test", "部分执行")
        content = p.read_text()
        content = content.replace("关联卡：无", "关联卡：ccc001, ccc002")
        p.write_text(content)
        mock_index = {
            "ccc001": {"id": "ccc001", "state": "作废", "path": "x"},
            "ccc002": {"id": "ccc002", "state": "作废（方案作废级联）", "path": "x"},
        }
        with patch("server.board.loader.load_index_file", return_value=mock_index):
            result = sync_plan_progress(tmp_path, "docs/projects/ccc/plans/001-test.md")
        assert result.get("auto_completed") is True
        assert "状态：作废" in p.read_text()

    def test_void_cascade_cards_marks_active_voided(self, tmp_path: Path):
        """方案作废级联：关联卡（待分派/执行中/已回写/打回）标作废，已关闭/已作废不动。"""
        _make_registry(tmp_path, ["ccc"])
        # 构造卡文件 + 索引
        dispatch_dir = tmp_path / "docs" / "dispatch" / "ccc"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        index: dict[str, dict] = {}
        for cid, state in [
            ("ccc001", "待分派"),
            ("ccc002", "执行中"),
            ("ccc003", "已关闭"),
            ("ccc004", "作废"),
        ]:
            card_file = dispatch_dir / f"{cid}-a.md"
            card_file.write_text(
                f"# 任务卡 {cid} · 示例\n\n> 关联：ccc-plan-001 · 执行体：OpenCode · 验收：Claude Code · 状态：{state} · 项目：ccc · 日期：2026-08-09\n",
                encoding="utf-8",
            )
            index[cid] = {"id": cid, "state": state, "path": f"docs/dispatch/ccc/{cid}-a.md"}

        with patch("server.board.loader.load_index_file", return_value=index):
            cascaded = _void_cascade_cards(tmp_path, list(index.keys()), "方案作废级联")
        assert sorted(cascaded) == ["ccc001", "ccc002"]
        assert "状态：作废（方案作废级联）" in (dispatch_dir / "ccc001-a.md").read_text()
        assert "状态：作废（方案作废级联）" in (dispatch_dir / "ccc002-a.md").read_text()
        # 已关闭 / 已作废 不动
        assert "状态：已关闭" in (dispatch_dir / "ccc003-a.md").read_text()
        assert "状态：作废" in (dispatch_dir / "ccc004-a.md").read_text()

    def test_update_plan_milestone_sync(self, tmp_path: Path):
        """update_plan 改里程碑：方案头更新 + roadmap 双向同步（新里程碑加入、旧里程碑移除）。"""
        _make_registry(tmp_path, ["ccc"])
        rm_dir = tmp_path / "docs" / "projects" / "ccc"
        rm_dir.mkdir(parents=True, exist_ok=True)
        (rm_dir / "roadmap.md").write_text(
            "# 测试线路图\n\n> 项目：ccc · 更新：2026-08-09\n\n## 草案池\n\n无。\n\n## 里程碑\n\n### 旧里程碑\n- 状态：进行中\n- 关联方案：ccc-plan-001\n\n### 新里程碑\n- 状态：草案\n",
            encoding="utf-8",
        )
        p = _make_plan(tmp_path, "ccc", "001", "test", "已确认")
        # 方案头补旧里程碑字段（业务场景：方案归属旧里程碑，现要改到新里程碑）
        content = p.read_text()
        content = content.replace("关联方案：无", "关联方案：无\n> 里程碑：旧里程碑")
        p.write_text(content)
        with patch("server.board.plans._git_commit_push", return_value=(True, "")):
            with patch("server.board.roadmap._repo_root", return_value=tmp_path):
                result = update_plan(
                    tmp_path, rel_path=str(p.relative_to(tmp_path)), milestone="新里程碑",
                )
        assert result.get("ok") is True
        assert "里程碑：新里程碑" in p.read_text()
        rm = (rm_dir / "roadmap.md").read_text()
        # 旧里程碑移除该方案
        assert "### 旧里程碑\n- 状态：进行中\n- 关联方案：ccc-plan-001" not in rm
        # 新里程碑加入该方案
        assert "### 新里程碑\n- 状态：草案\n- 关联方案：ccc-plan-001" in rm
