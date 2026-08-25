# 任务卡 ccc007 · M5 audit dogfood rebase hint（OpenCode 执行）

> 关联：ccc-plan-001 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：manual · 项目：ccc · 日期：2026-08-07
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 目标

在 `scripts/new-card.sh` 出卡模板加一行 rebase 提醒（减 `--close-only`），并走 Engine `--audit` 真机审落盘（不经 `first-audit-evidence`）。

## 红线（先看）

1. 只改 `scripts/new-card.sh` 模板步骤文案（≤3 行净增）；不写新 SOP、不改席位/Hub/Desktop。
2. 不直推 main 业务码；走分支 `codex/ccc007-m5-audit-dogfood-rebase-hint`。
3. 禁止自写 `## 机审区` / `## 验收区` / 置「已关闭」。

## 范围

- `scripts/new-card.sh`：步骤区加合入前 rebase 提醒。
- 本卡：已回写 → 等 2017 Engine `--audit` → 合入批准。

## 步骤

1. 改 `new-card.sh` 步骤：回写 push 后、合入前 `git fetch origin && git rebase origin/main`。
2. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `scripts/new-card.sh --dry-run`（任意标题）生成正文含 `rebase origin/main`。
2. 2017 存在 `~/.ccc/logs/exec/ccc007.audit.log`，且生产卡出现 `## 机审区` + `机审：通过`（Engine 真机审，非 evidence 补录）。
3. 未新增 SOP / 席位文档。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 回写区

**执行体**：Cursor（M5 地基）· 日期：2026-08-07

### 实现说明
- `scripts/new-card.sh` 步骤 2 增加合入前 rebase 一行（对齐 `docs/product/north-star-slice.md` 分支卫生）。

### 测试结果
```
./scripts/new-card.sh --title "dry" --project cd --dry-run | grep -F 'rebase origin/main'
```

### push 证据
- 分支：`codex/ccc007-m5-audit-dogfood-rebase-hint`
- commit：774dd92

## 机审区

**机审方**：Claude Code（2017）· 机审：通过

- 验收1 ✓：`scripts/new-card.sh --dry-run` 生成正文含 `rebase origin/main`（实测 grep -F 命中）。
- 验收2 ✓：`~/.ccc/logs/exec/ccc007.audit.log` 存在，engine 起 audit 子进程（child_pid，真机审非 evidence 补录）。
- 验收3 ✓：分支 `25384cbe..HEAD` 仅改 `scripts/new-card.sh`（1 行净改）+ 本卡，未新增 SOP/席位文档。
- 红线 ✓：未直推 main；禁写验收区/已关闭（本席未写）；范围 ≤3 行净增。

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
