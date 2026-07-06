# .ccc/state.md — CCC 接力索引(红线 10 强制)

> **本文件是 CCC 框架跨会话接力的唯一可信输入**。
> 任何 Planner / Executor / Verifier session **必须第一个读本文件**(红线 10)。
> 禁止依赖 session 内隐式记忆;所有历史结论必须显式 grep `.ccc/` 内文件。

---

## 项目身份

| 字段 | 值 |
|------|----|
| 项目名 | CCC (Connect–Claude Code) |
| 路径 | `/Users/apple/program/CCC` |
| 形态 | SKILL 资产型框架(v1.2.0) |
| 主语言 | Bash + Python 3.11+ |
| Profile 路径 | `.ccc/profile.md` |
| 本文件路径 | `.ccc/state.md` |

---

## 最近任务(按完成时间倒序,最多 5 条)

| 时间 | 任务 ID | 计划 | 报告 | 验收 | 状态 |
|------|---------|------|------|------|------|
| 2026-07-06 | hello-ccc-demo | [plan](plans/hello-ccc-demo.plan.md) | [report](reports/hello-ccc-demo.report.md) | [verdict](verdicts/hello-ccc-demo.verdict.md) | CONDITIONAL_PASS |

> 表格为空表示项目无历史任务。新任务开始时,Executor 完成前应追加本表。

---

## 进行中任务(活跃)

| 任务 ID | 当前 phase | owner | 启动时间 | 上次更新 |
|---------|-----------|-------|----------|----------|
| hello-ccc-demo-v2 | phase 1/3 (pending) | executor | 2026-07-06 | 2026-07-06 (precheck 7/7 PASS) |

---

## 待办任务(用户已承诺,未启动)

> 当前无待办任务。Planner 接受新任务时追加。

---

## 已知约束(项目级)

- **不新增平台依赖**: CCC = SKILL 资产,跨 IDE/跨模型
- **4 文件契约**: plans / phases / reports / verdicts 必须严格走 `.ccc/`
- **跨 IDE symlink**:
  - `~/.claude/skills/ccc-protocol` → CCC repo
  - `~/.zcode/skills/ccc-protocol` → CCC repo
  - `~/.config/skills/ccc-protocol` → CCC repo (通用)
- **不可触碰**: `/etc/*`, `~/.env`, `~/.aws/*` (红线 1)
- **commit 规则**: 单 phase 单 commit + commit msg 必含 `ccc-task-id=<task> phase=N`

---

## 工具链状态

| 工具 | 版本 | 状态 |
|------|------|------|
| Python | 3.11+ | ✅ |
| Bash | 5.x | ✅ |
| Claude Code CLI | 2.1.193+ | ✅ |
| ruff | 0.8.6 | ✅ |
| shellcheck | latest | ✅ |
| pytest | latest | ✅ |

---

## 关键历史决策(影响后续任务)

1. **CCC 形态选择** (2026-07-06): 选 SKILL 资产而非 framework 代码库 — 跨 IDE/跨模型维护成本最低
2. **三角色边界** (2026-07-06): Planner / Executor / Verifier 严格分离,禁止互串 (红线 6)
3. **红线 11** (2026-07-06): Verifier 必须写真 verdict 文件,口头 PASS 不算 PASS (Lesson 28)
4. **执行方式 4 选 1** (2026-07-06): `manual` / `auto` / `loop` / `goal` (其他术语禁止)

---

## 维护说明

- **追加任务**: 在"最近任务"表头部插入,保留最多 5 条
- **去重**: lessons.md 写入按 `(date, task_id)` 去重 (红线 10 机制钩子)
- **过期归档**: 超过 30 天的任务可移到 `.ccc/archive/state-YYYY-MM.md`
- **禁止手动改写历史行**: 只能追加新行,不能修改已完成任务的 hash

---

**最后更新**: 2026-07-06 (CCC v1.2.0 流程跑通初始化)
**下次启动必读顺序**:
1. 读本文件(state.md)
2. 读 `.ccc/profile.md`
3. 读最近一条 plan + report + verdict
4. 才开工
