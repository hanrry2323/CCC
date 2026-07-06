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
| 形态 | SKILL 资产型框架(v0.7.0) |
| 主语言 | Bash + Python 3.11+ |
| Profile 路径 | `.ccc/profile.md` |
| 本文件路径 | `.ccc/state.md` |

---

## 最近任务(按完成时间倒序,最多 5 条)

| 时间 | 任务 ID | 计划 | 报告 | 验收 | 状态 |
|------|---------|------|------|------|------|
| 2026-07-07 | v0.7f | [plan](plans/v0.7f.plan.md) | [report](reports/v0.7f.report.md) | (umbrella release) | PASS |
| 2026-07-07 | v0.7e-fix | [plan](plans/v0.7e-fix.plan.md) | [report](reports/v0.7e-fix.report.md) | — | PASS |
| 2026-07-07 | v0.7e | [plan](plans/v0.7e.plan.md) | [report](reports/v0.7e.report.md) | [verdict](verdicts/v0.7-slim.verdict.md) | CONDITIONAL_PASS |
| 2026-07-07 | v0.7d-prime | [plan](plans/v0.7d-prime.plan.md) | [report](reports/v0.7d-prime.report.md) | — | PASS |
| 2026-07-07 | v0.7d | [plan](plans/v0.7d.plan.md) | [report](reports/v0.7d.report.md) | — | PASS |

> 表格为空表示项目无历史任务。新任务开始时,Executor 完成前应追加本表。

---

## 当前任务(进行中)

**v0.7 任务链**:✅ **已完结**(2026-07-07,umbrella release v0.7.0)

下一阶段决策点(待用户拍板):

- **v0.8a**:定时调度优先 —— 更自动化(本地 cron / launchd 调 ccc-exec-launcher)
- **v0.8b**:知识飞轮 + 队列模式优先 —— 更适合长期(flywheel 简化版 + goal-mode 重启)
- **v0.8c**:先消化当前 v0.7,等用户派新活

> 当前**不启动** v0.8 任何任务,等用户拍板。Planner 收到决策后,在本节追加"启动: v0.8X — 主题 — 启动日期"行。

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
5. **v0.7-slim 精简决策** (2026-07-07): 删除 cluster-bus / dispatch / flywheel / 成本报告 / precommit / 多 IDE adapter 等"路线预留"代码。砍掉为未来预留的过度工程化，回到"1 个 SKILL.md + 5 个核心脚本"的小型框架定位。如需这些功能,按需从头重写更简单的版本。
6. **v0.7 完结 + v0.8 待拍板** (2026-07-07): v0.7-slim → v0.7a → v0.7b → v0.7c → v0.7d → v0.7d-prime → v0.7e → v0.7e-fix → v0.7f 共 9 子任务全部 PASS / CONDITIONAL_PASS,统一收束为 `v0.7.0` umbrella release。流程层版本从 1.2.0 回落至代码层 v0.7.0(代码能力级别)。后续 v0.8 起重新自增。

---

## 维护说明

- **追加任务**: 在"最近任务"表头部插入,保留最多 5 条
- **去重**: lessons.md 写入按 `(date, task_id)` 去重 (红线 10 机制钩子)
- **过期归档**: 超过 30 天的任务可移到 `.ccc/archive/state-YYYY-MM.md`
- **禁止手动改写历史行**: 只能追加新行,不能修改已完成任务的 hash

---

**最后更新**: 2026-07-07 (v0.7 任务链完结,v0.7.0 umbrella release)
**下次启动必读顺序**:
1. 读本文件(state.md)
2. 读 `.ccc/profile.md`
3. 读最近一条 plan + report + verdict
4. 才开工
