# .ccc/state.md — CCC 接力索引(红线 10 强制)

> **本文件是 CCC 框架跨会话接力的唯一可信输入**。
> 任何 CCC 角色 session **必须第一个读本文件**(红线 10)。
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
| 2026-07-07 | v0.7e-fix | [plan](plans/v0.7e-fix.plan.md) | [report](reports/v0.7e-fix.report.md) | [verdict](verdicts/v0.7e-fix.verdict.md) | PASS |
| 2026-07-07 | v0.7e | [plan](plans/v0.7e.plan.md) | [report](reports/v0.7e.report.md) | (随 v0.7-slim.verdict) | CONDITIONAL_PASS |
| 2026-07-07 | v0.7d-prime | [plan](plans/v0.7d-prime.plan.md) | [report](reports/v0.7d-prime.report.md) | [verdict](verdicts/v0.7d-prime.verdict.md) | PASS |
| 2026-07-07 | v0.7d | [plan](plans/v0.7d.plan.md) | [report](reports/v0.7d.report.md) | [verdict](verdicts/v0.7d.verdict.md) | PASS |

### v0.7 子任务全集(2026-07-07 closure,共 9 子任务)

| # | 任务 ID | 报告 | 验收 | 状态 |
|---|---------|------|------|------|
| 1 | v0.7-slim | [report](reports/v0.7-slim.report.md) | [verdict](verdicts/v0.7-slim.verdict.md) | PASS |
| 2 | v0.7a | [report](reports/v0.7a.report.md) | [verdict](verdicts/v0.7a.verdict.md) | PASS |
| 3 | v0.7b | [report](reports/v0.7b.report.md) | [verdict](verdicts/v0.7b.verdict.md) | PASS |
| 4 | v0.7c | [report](reports/v0.7c.report.md) | [verdict](verdicts/v0.7c.verdict.md) | PASS |
| 5 | v0.7d | [report](reports/v0.7d.report.md) | [verdict](verdicts/v0.7d.verdict.md) | PASS |
| 6 | v0.7d-prime | [report](reports/v0.7d-prime.report.md) | [verdict](verdicts/v0.7d-prime.verdict.md) | PASS |
| 7 | v0.7e | [report](reports/v0.7e.report.md) | (随 v0.7-slim) | CONDITIONAL_PASS |
| 8 | v0.7e-fix | [report](reports/v0.7e-fix.report.md) | [verdict](verdicts/v0.7e-fix.verdict.md) | PASS |
| 9 | v0.7f | [report](reports/v0.7f.report.md) | (umbrella release) | PASS |

> 表中显示的"最近 5 条"按完成时间取尾 5 个,完整 v0.7 子任务链见下方子集。

> 表格为空表示项目无历史任务。新任务开始时,Executor 完成前应追加本表。

---

## 当前任务(进行中)

**v0.11 任务链**:✅ **已完结**(2026-07-07,开箱即用调度 + 队列真测试 + bfix)

- 启动: v0.11 — a+b — 2026-07-07
- 完结: v0.11.0 — 2026-07-07
- 关键产出:
  - 3 个钩子模板(post-exec / on-error / pre-commit)
  - install-ccc-scheduler.sh(install/uninstall/status/--dry-run)
  - 队列 N phase 真测试(3 pytest: pass/mid_fail/resume)
  - 修红线 X2 失守(killpg + pkill -f 兜底)
  - 修 opencode run positionals 截断(--file 协议)
- 测试: 66 passed
- Verdict: PASS (.ccc/verdicts/v0.11-verdict.md)

**v0.11 消化(本次)**:✅
- 追加 lessons 34(killpg 不可靠) + 35(opencode 写代码超人工)
- 验 scheduler install/uninstall 闭环
- roadmap 标 v0.11 + 范式转变(opencode 写 + 人工 review)
- 远端 5 tag: v0.7.0/v0.8.0/v0.9.0/v0.10.0/v0.11.0

**v0.12 任务链**:✅ **已完结**(2026-07-07,bug fix sweep)

- 启动: v0.12 — bug fix — 2026-07-07
- 完结: v0.12.0 — 2026-07-07
- 修 3 真 bug + 复查 4 非 bug:
  - Bug 1+3: opencode-exec 长 prompt 临时文件泄漏
  - Bug 2: ccc-finish bare except → JSONDecodeError
  - Bug 6: 钩子 timeout=30 写死 → CCC_HOOK_TIMEOUT + perl 兜底
  - Bug 4-5,7: 复查后非 bug, 加注释说明
- 测试: 69 passed (66 + 3 新增)
- 远端 6 tag: v0.7.0/v0.8.0/v0.9.0/v0.10.0/v0.11.0/v0.12.0

**v0.12 消化(本次)**:✅
- 追加 lesson 36(bug 分类 + 修复模式)
- roadmap 标 v0.12 + 质量纪律段(bug 扫描 → 必修 → 复查 → 沉淀 4 步)
- CHANGELOG 加 v0.12 段
- 远端 6 tag 完整

**v0.13 任务链**:✅ **已完结**(2026-07-07,跨项目支持 qx-observer)

- 启动: v0.13 — 跨项目支持 qx-observer — 2026-07-07
- 完结: v0.13.0 — 2026-07-07
- 关键产出:
  - qx-observer profile.md 加 v0.12 section
  - precheck 7/7 PASS in qx-observer
  - launcher 跑 test phase: exit 0, 9.97s
  - watchdog 0 残留
  - CCC 资产跨项目就绪（不需改主代码）
- Verdict: PASS

下一阶段决策点(待用户拍板):

- **v0.14**:飞轮候选 review 合并 / e2e 加 verifier 验收 / 跨项目 qx + xianyu
- **v0.15**:消化,等新活

> 当前**不启动** 任何新任务,等用户拍板。

---

**v0.14 任务链**:✅ **已完结**(2026-07-07,真落地: 35 commit push + scheduler 装)

- 35 commit qx-observer 推远端 (7e5fd57..d10cf23)
- qx-observer lessons.md 42 行 task-test-001 噪声清
- qx-observer profile.md 接 v0.12 section
- CCC scheduler (com.ccc.flywheel-scan) 装 launchd 跑 3600s 周期
- 远端 5 tag: v0.7.0/v0.8.0/v0.9.0/v0.10.0/v0.11.0

**v0.15 任务链**:✅ **已完结**(2026-07-07,真自动化开发)

- 启动: v0.15 — 自动化开发 — 2026-07-07
- 完结: v0.15.0 — 2026-07-07
- 关键产出:
  - `scripts/ccc-auto-dev.sh` — 你说"按 CCC 跑 X"的入口
  - `templates/hooks/post-exec.sh` — 加 git push (v0.15d)
  - 修 launcher 传 workspace + post-exec 改用 $2 (Lesson 38)
  - 真验: qx-observer v0.15b-test5 8 分钟, post-exec 自动落远端
- 测试: 69 passed (无关 v0.15)
- 远端 8 tag

**v0.16 任务链**:✅ **已完结**(2026-07-07,6 角色 + 任务看板)

- 启动: v0.16 — 6 角色定时开发系统 — 2026-07-07
- 完结: v0.16.0 — 2026-07-07
- 关键产出:
  - `.ccc/board/` 6 列任务看板
  - `scripts/ccc-board.py` 6 角色核心
  - `scripts/roles/{product,dev,reviewer,tester,ops,kb,regress}.sh` × 7
  - `scripts/install-ccc-roles.sh` 一键装 7 launchd plist
  - 频率: product 4h / dev 10min / reviewer 2h / tester 4h / ops 30min / kb 每天 23:00
  - e2e: 1 个 task backlog→released 全 6 步
- 测试: 69 passed (无关 v0.16)

**v0.17 任务链**:✅ **已完结**(2026-07-07,战略地图 + 文档体系对齐)

- 启动: v0.17 — 战略地图 — 2026-07-07
- 完结: v0.17.0 — 2026-07-07
- 关键产出:
  - `docs/STRATEGY-MAP.md` — 战略地图 (启动必读第一)
  - `SKILL.md` v1.1 → v1.6, 加启动必读段
  - `CLAUDE.md` 6 角色矩阵 (替换 3 角色旧路由)
  - `references/red-lines.md` 加 X4 (看板流转) / X5 (plist 必装) / X6 (频率不许改)
  - `docs/roadmap.md` 5 次范式转变标注
  - `docs/lessons.md` Lesson 37 (战略地图教训) + 38 (post-exec workspace bug)
- 远端 9 tag 完整: v0.7.0 → v0.16.0

下一阶段决策点(待用户拍板):

- **v0.18**:跨项目任务 (qx-observer / xianyu / qx 用 6 角色系统)
- **v0.19**:跑 1 个真 backlog task 看 6 角色端到端流转 (harness 配合)
- **v0.20**:消化,等新活

> 当前**不启动** 任何新任务,等用户拍板。

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

**最后更新**: 2026-07-07 (v0.7.0 closure — tagged, pushed, working tree clean, v0.8 路线全部终止)
**v0.7.0 收尾**:
- 8 个 verdict 齐全(v0.7-slim + v0.7a/b/c/d/d-prime/e-fix/f),主干 42 pytest passed
- 8 commits 已 push 到 origin/main (96d14ca..171eea9)
- Tag `v0.7.0` 已打 + push(已于更早完成,本轮确认存在)
- `fix(scripts): ccc-finish.sh whitelist regex` commit 171eea9 已合入
- **v0.8 路线终止** (2026-07-07 拍板):
  - 删除分支: `v0.8-wip` / `worktree-agent-a7965bfee02705990` / `worktree-agent-aab121d485296969d` / `worktree-oral-calc-commit`
  - 删除 worktree: `.claude/worktrees/agent-{a7965bfee02705990,aab121d485296969d}` + `/Users/apple/program/CCC-v0.8-wip`
  - 丢弃 v0.8 WIP 代码(stash 已 drop): ccc-exec-launcher.sh / ccc-poll.sh / ccc-window-init.sh + 3 个新测试
  - main 分支不再含任何 v0.8 路线代码,版本停止在 v0.7.0
- 当前状态: `git status` 干净,origin/main 与本地同步,版本 v0.7.0
**下次启动必读顺序**:
1. 读本文件(state.md)
2. 读 `.ccc/profile.md`
3. 读最近一条 plan + report + verdict
4. 才开工
**v0.8+ 路线决策**: 当前无任何活跃 v0.8 任务,等用户重新派活才启动新流程。
