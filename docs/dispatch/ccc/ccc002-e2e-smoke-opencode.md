# 任务卡 ccc002 · E2E smoke: OpenCode channel + worktree（OpenCode 执行）

> 关联：ccc-plan-007 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-06
> 变更记录：2026-08-06 Cursor 独立取证验收通过；分支 `codex/ccc002-e2e-smoke-opencode`（`c47a2c2`）已 ff 合入 `main`。

## 目标

最小可验收的 E2E 烟雾：Engine 能自动派发 OpenCode、建 worktree、commit+push 到独立分支，并把卡头回写为「已回写」。本卡只新增 1 个短说明文件，证明 OpenCode 通道整条流水线贯通。

## 红线（先看）

1. 只允许新增 1 个文件：`docs/notes/2026-08-06-e2e-smoke-opencode.md`（内容 ≤20 行，说明本次烟雾目的与验证链路）。
2. 禁止改动 `server/`、`desktop/`、权威短读、其它任务卡——越界即打回。
3. 允许改动本卡文件 `docs/dispatch/ccc/ccc002-e2e-smoke-opencode.md`——仅限卡头「状态」字段与「回写区」内容，不得改目标/红线/范围/步骤/验收标准。
4. 执行体必须为 OpenCode；交卷停在「已回写」，禁止自置「已关闭」（验收/关闭归 Codex）。

## 范围

白名单式（只此一项可触碰）：

- `docs/notes/2026-08-06-e2e-smoke-opencode.md`：新增，内容 ≤20 行，写明本次烟雾的目的与验证链路。
- 本卡 `docs/dispatch/ccc/ccc002-e2e-smoke-opencode.md`：仅卡头「状态」字段 + 「回写区」内容。

不在上列的任何改动 = 越界，验收打回。

## 步骤

1. 2017 上 `git pull` 拉到本卡（含出卡方 push 的卡头）。
2. Engine 识别到「派发：engine」+ 执行体 OpenCode → 自动拉起 OpenCode 执行体。
3. Engine 建 worktree：`ccc-dev-ws-ccc002`（源自卡号）。
4. 执行体在 worktree 内新增 `docs/notes/2026-08-06-e2e-smoke-opencode.md`（≤20 行）。
5. 执行体 commit + push 该文件到分支 `codex/ccc002-e2e-smoke-opencode`（不要直推 main）；合入 main 由验收后处理。
6. 卡头「状态」更新为「已回写」，并在回写区填实现说明 / 测试结果 / push 证据。

## 验收标准

1. `docs/notes/2026-08-06-e2e-smoke-opencode.md` 已 push 成功到分支 `codex/ccc002-e2e-smoke-opencode`（附 commit hash，`git log --oneline -1` 该分支可见）。
2. 卡头「状态」已为「已回写」，回写区填实现说明 + 测试结果 + push 证据。
3. HTTP 看板执行中曾出现本卡（执行列）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据。

## 回写区

**执行体**：OpenCode · 日期：2026-08-06

**实现说明**：OpenCode 执行体在 Engine 所建 worktree `ccc-dev-ws-ccc002` 内，按白名单新增 `docs/notes/2026-08-06-e2e-smoke-opencode.md`（≤20 行，写明烟雾目的与验证链路），并将本卡卡头「状态」更新为「已回写」。

**测试结果**：改动范围仅白名单内 2 项（新说明文件 + 本卡卡头/回写区），未触碰 server/、desktop/、权威短读及其它任务卡；git 状态确认无越界改动。

**push 证据**：分支 `codex/ccc002-e2e-smoke-opencode`，commit `c47a2c2`；已合入 `main`。

---

## 验收区（Cursor 独立取证 · 2026-08-06）

**判定：通过** ✅

| # | 标准 | 取证 |
|---|------|------|
| 1 | notes 文件在分支并合入 main | `docs/notes/2026-08-06-e2e-smoke-opencode.md`（17 行）@ `c47a2c2`，main ff 含该提交 |
| 2 | 卡头已回写 + 回写区齐全 | Engine `收单成功: work=ccc002 → 已回写`；回写区有实现/测试/push |
| 3 | 看板曾执行中 | `:7788/board/states` 观测 执行中:1 → 已回写:2；worktree `ccc-dev-ws-ccc002` + `--auto` 派发成功 |

补充观测：首次因 launchd PATH 找不到 `opencode` 打回（已改绝对路径）；第二次 exit 0 假成功（sandbox 拒读卡外路径，无产物）— 模板加 `--auto --dir {worktree}` 后第三次真通。

## 机审区

**机审：通过**
- 说明：历史卡，无存档证据，按看板已关闭态标注

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
