# 失败复盘 · clw006 卡在流程里打转（2026-08-10）

> 性质：流程事故复盘。clw006（打包卡）因编号错位 → worktree 残留 → 空回写死循环，在 engine 流程里反复打转，延误整条 clw 链收口。
> 结论：先止血，再补流程防护，沉淀通用失败模式。本文档 7 天内进权威或归档（DOC-PROTOCOL）。

## 一、事故现象

- clw006 打包卡（clw006-package-acceptance）始终无法完成：engine 反复派发 → 执行体空回写 → 机审打回 → 再派，无限循环。
- 表面「卡在流程里」，实际是**执行体从未真正开发打包卡**——worktree 里根本没有打包卡文件。
- 残留：CCC 远端垃圾分支 `codex/clw006-resume-cwd-fix`、`ccc-dev-ws-clw006` 错误 worktree、`clw006.running`/runtime state 循环「已回写+upstream 冷却」记录。

## 二、根因链（三层叠加）

1. **编号错位（根源）**：出 clw007 修复卡时用 plan-to-cards 自动编号，因磁盘当时无 clw006 文件，修复卡被自动编号为 `clw006`（文件 `clw006-resume-cwd-fix.md`）。后人工 `git mv` 改名 `clw007-resume-cwd-fix.md`、卡头 ID 改 clw007。
2. **worktree/runtime 残留**：engine 的 `ccc-dev-ws-clw006` worktree 与 `clw006.running` 在改名**前**已生成。改名后 worktree 内无 `clw006` 卡文件（只有 clw007 卡），engine 按 work.id=clw006 派发时注入旧 card_path `clw006-resume-cwd-fix.md`。
3. **空回写死循环**：执行体在 worktree 里找不到对应卡 → 无法真正开发 → 回写为空/假 → 机审因「维护区空/未回写」打回 → engine 按失败重试（retry_count 递增）→ 再派 → 循环。期间被误判为「基础设施 upstream」进入 infra 冷却，进一步拖长循环。

## 三、关键证据

- worktree `ccc-dev-ws-clw006/docs/dispatch/clw/` 只有 clw001-005 + clw007，**无 clw006**（改名导致）。
- 执行体日志 clw006.log：注入提示要求 Read `clw006-resume-cwd-fix.md`（旧路径），执行体误判任务=clw007 修复内容并「假完成」。
- 业务仓 clwarp 零 clw006 提交（`git branch -r | grep clw006` 为空）→ 无打包、无 dmg。

## 四、止血动作（已执行）

1. 杀残留机审/执行体进程（clw006 相关）。
2. 删残留 runtime：`clw006.running` / `clw006-audit.running` / runtime state 中 clw006 记录。
3. 删 CCC 远端垃圾分支 `codex/clw006-resume-cwd-fix`。
4. `git worktree remove --force` 回收 `ccc-dev-ws-clw006`，删本地残留分支。
5. 确认 clw006 卡回「待分派」干净状态，索引正确指向 `clw006-package-acceptance.md`。
6. engine 自动重建 worktree（含正确打包卡）→ 新执行体（pid 48983）正常开发。**打转解除。**

## 五、通用教训（可复用的失败模式）

### 失败模式 A：卡改名/重编号后，派发现场未同步

- **触发**：任何对已出卡文件做 `git mv` / 卡头 ID 修改。
- **后果**：worktree 目录名（按 work.id）、派发注入的 card_path（按旧文件名 stem）、runtime 记录全部停留在改名前的状态 → 执行体读不到卡 → 空转。
- **铁律**：**出卡后禁止改名/改 ID**。若必须改（如编号冲突），必须同步清理 engine worktree + runtime + 远端分支，并确认无在途执行体。

### 失败模式 B：plan-to-cards 自动编号与方案计划编号错位

- **触发**：修复卡/附加卡用 plan-to-cards 自动编号，吃掉了方案链上预留的编号（本次 clw006 被 clw007 修复卡占用）。
- **后果**：方案编号语义断裂（clw006 应是打包卡），后续出卡混乱。
- **铁律**：**方案链上的编号必须显式保留**。非方案主链的修复/附加卡，一律用 `--id` 显式指定（如 clw007），禁止吃自动编号空位。

### 失败模式 C：空回写无上限，形成死循环

- **触发**：执行体无法真正开发（找不到卡/无产物）时，回写为空，机审打回，engine 无限重试。
- **后果**：卡在「待分派↔已回写↔打回」间打转，且可能被误判为 infra 冷却，拖长不可观测。
- **铁律**：**失败重试必须有上限**。已回写但产物空/维护区空 → 机审打回应直接进入「打回」终态（或人工介入），而非无限重试。engine 应区分「执行体真失败」与「执行体空转」。

## 六、待办（对应平台修复卡）

- [ ] engine 派发前校验 worktree 内 card_path 存在；不存在则重建 worktree 或跳过，禁止派空转。
- [ ] 空回写防护：回写无有效产物（diff 为空/维护区占位）→ 机审直接打回进「打回」态，不无限重试。
- [ ] plan-to-cards / new-card：方案链编号保护，附加卡显式编号，杜绝吃空位。
