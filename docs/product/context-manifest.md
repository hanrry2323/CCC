# Context Manifest（F4-1）

显式声明各角色 prompt 需要哪些 context 项，由 `board.context.build_role_context(role, task)` 按 `ROLE_CONTEXT_MANIFEST` 收集。信息分配可审计、可复用；不引入向量库 / RAG。

SSOT 代码：`scripts/board/context.py`（`ROLE_CONTEXT_MANIFEST` + collectors）。

## Manifest 项定义

| key | 含义 | 典型来源 |
|-----|------|----------|
| `skill` | 角色 SKILL.md | `skills/ccc-<role>/SKILL.md` |
| `baseline` | 项目基线摘要 | `_project_baseline.collect_baseline` |
| `profile` | 项目档案 | `.ccc/profile.md` |
| `code_ctx` | 代码树/热点摘要 | `product._get_code_context` |
| `ref_plans` | 近期 plan 参考 | `.ccc/plans/*.plan.md`（最多 2） |
| `recent_lessons` | 未 fixed 教训 | `_lessons.get_recent_lessons` |
| `current_epic` | 当前任务摘要 | `task.id/title/description` |
| `plan_template` | plan 模板 | `templates/plan.plan.md` |
| `plan` | 任务 plan | `.ccc/plans/<tid>.plan.md` |
| `phases` | 任务 phases | `.ccc/phases/<tid>.phases.json` |
| `skill_hints` | task hints.skills | board task `hints` |
| `pytest_failure` | pytest 回灌 | `.ccc/pids/<tid>.pytest_fail.md` |
| `verdict` | 已有 verdict | `.ccc/verdicts/<tid>.verdict.md` |

缺文件或收集失败 → **空串**，不抛（见 `OPTIONAL_CONTEXT_KEYS`；其余 key 同样兜底）。

## 每角色声明

| 角色 | keys | 迁移状态 |
|------|------|----------|
| `product` | skill, baseline, profile, code_ctx, ref_plans, recent_lessons, current_epic, plan_template | **已迁** |
| `dev` | plan, phases, skill_hints, pytest_failure, current_epic | **已迁** |
| `reviewer` | skill, plan, verdict, current_epic | **已迁** |
| `tester` | plan, phases, current_epic | TODO（占位） |
| `kb` | plan, current_epic | TODO（占位） |
| `ops` | profile, current_epic | TODO（占位） |
| `regress` | plan, recent_lessons, current_epic | TODO（占位） |

用法：

```python
from board.context import build_role_context

ctx = build_role_context("product", task, include_ref_plans=True)
prompt = f"...{ctx['profile']}...{ctx['skill']}..."
```

`include_ref_plans=False` 时 `ref_plans` 为「（无，重试模式）」文案（product 重试路径）。

## 如何加新项

1. 在 `ROLE_CONTEXT_MANIFEST` 对应角色 list 里追加 key。  
2. 实现 `_collect_<key>(...)`，注册进 `_COLLECTORS`（`skill` 走 `_load_role_skill`）。  
3. 若缺文件应静默：把 key 加入 `OPTIONAL_CONTEXT_KEYS`（或不加——collector 仍应返回 `""`）。  
4. 更新本表 + `tests/scripts/test_context_manifest.py` 断言。  
5. 角色 prompt 改为读 `ctx[key]`；勿在角色文件里再 ad-hoc 读盘拼装同一项。

红线：不改角色职责边界；不改 Engine 主循环 / transfer / flow / Desktop。
