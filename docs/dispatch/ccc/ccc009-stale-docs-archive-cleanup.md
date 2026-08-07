# 任务卡 ccc009 · 文档卫生：过时/过期文档清理归档（OpenCode 执行）

> 关联：ccc-plan: 文档卫生与业务总线路图 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-07

## 目标

文档卫生：过时/过期文档清理归档（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `docs/ccc-hub-ports.md`
- `docs/vertical-qx.md`
- `docs/legacy-phase2-plan.md`
- `docs/legacy-retirement-list.md`
- `docs/REFACTOR-INDEX.md`
- `docs/workspace-binding.md`
- `docs/program-housekeeping.md`
- `docs/notes/`
- `docs/INDEX.md`
- `docs/DOC-PROTOCOL.md`
- `docs/automation-base.md`
- `docs/archive/`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. ls docs/ 不再存在 ccc-hub-ports.md vertical-qx.md legacy-phase2-plan.md legacy-retirement-list.md REFACTOR-INDEX.md workspace-binding.md program-housekeeping.md（原件在 docs/archive/ 标「史」）
2. docs/notes/ 已完成里程碑（m2-m6）迁入 docs/archive/milestones-2026-08-07/，notes 只留未闭环 next-plan
3. docs/INDEX.md §0 与 DOC-PROTOCOL 落点表指针更新为归档后路径
4. docs/automation-base.md 中 dispatch/T<n> 路径修正为 docs/dispatch/<prefix>/
5. git status 仅含本卡改动；validate 通过

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：
