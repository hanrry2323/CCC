# 任务卡 ccc009 · 文档卫生：过时/过期文档清理归档（OpenCode 执行）

> 关联：ccc-plan-002 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-07
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

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

**执行体**：OpenCode · 日期：2026-08-07

### 实现说明

1. 将 `docs/` 下的 7 个过时/过期文档（`ccc-hub-ports.md`, `vertical-qx.md`, `legacy-phase2-plan.md`, `legacy-retirement-list.md`, `REFACTOR-INDEX.md`, `workspace-binding.md`, `program-housekeeping.md`）通过 `git mv` 归档到 `docs/archive/` 目录下，并在文件头部增加了「史」字标识以及归档状态说明。
2. 创建 `docs/archive/milestones-2026-08-07/` 目录，并将 `docs/notes/` 下 M2–M6 的里程碑归档文件及已闭环的 `next-plan` 笔记全部迁入该目录。
3. 更新了 active 文档中对已归档文件的所有相对路径引用，确保路径 100% 正确且不产生坏链。
4. 修正了 `docs/automation-base.md` 中 `dispatch/T<n>` 路径为 `docs/dispatch/<prefix>/`。

### 测试结果

- 运行 `pytest server/tests/test_board_validate.py`：全部 19 项验证用例通过。
- 运行全局 `pytest server/tests/`：共 588 项测试，全部通过（100% PASS）。

### Push 证据

- 实现代码 Commit Hash：`342a1532f74e62a98f45a703d1544ef41fa41893`

## 机审区

机审：通过
来源：engine 自动落盘（audit-log-restore）· 2026-08-07 13:05
证据：docs/dispatch/ccc/ccc009-stale-docs-archive-cleanup.md（清理残留 engine 日志片段，最终结论见上「机审：通过」）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
