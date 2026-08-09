# 任务卡 ccc001 · E2E smoke: Engine dispatch + worktree + board dirty（Claude Code 执行）

> 关联：ccc-plan-007 · 执行体：Claude Code · 验收：OpenCode · 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-06
> 变更记录：2026-08-06 Cursor 独立取证验收通过；分支 `codex/ccc001-e2e-smoke-engine-dirty`（`1e13c538`）已 ff 合入 `main`。

## 目标

最小可验收的 E2E 烟雾：Engine 能自动派发 Claude Code、建 worktree、commit+push，并把卡头回写为「已回写」。本卡只新增 1 个短说明文件，证明整条流水线贯通。

## 红线（先看）

1. 只允许新增 1 个文件：`docs/notes/2026-08-06-e2e-smoke.md`（内容 ≤20 行，说明本次烟雾目的）。
2. 禁止改动 `server/`、`desktop/`、权威短读、其它任务卡——越界即打回。
3. 允许改动本卡文件 `docs/dispatch/ccc/ccc001-e2e-smoke-engine-dirty.md`——仅限卡头「状态」字段与「回写区」内容，不得改目标/范围/其它卡。
4. 执行体必须为 Claude Code；卡头状态保持「待分派」直到流水线自动回写，禁止手动改状态。

## 范围

白名单式（只此一项可触碰）：

- `docs/notes/2026-08-06-e2e-smoke.md`：新增，内容 ≤20 行，写明本次烟雾的目的与验证链路。
- 本卡 `docs/dispatch/ccc/ccc001-e2e-smoke-engine-dirty.md`：仅卡头「状态」字段 + 「回写区」内容。

不在上列的任何改动 = 越界，验收打回。

## 步骤

1. 2017 上 `git pull` 拉到本卡（含上一步 push 的卡头）。
2. Engine 识别到 `派发：engine` → 自动拉起 Claude Code 执行体。
3. Engine 建 worktree：`ccc-dev-ws-<id>`（源自卡号）。
4. 执行体在 worktree 内新增 `docs/notes/2026-08-06-e2e-smoke.md`（≤20 行）。
5. 执行体 commit + push 该文件到分支 `codex/ccc001-e2e-smoke-engine-dirty`（不要直推 main）；合入 main 由验收后处理。
6. 卡头「状态」更新为「已回写」，并在回写区填实现说明 / 测试结果 / push 证据。

## 验收标准

1. `docs/notes/2026-08-06-e2e-smoke.md` 已 push 成功到分支 `codex/ccc001-e2e-smoke-engine-dirty`（附 commit hash）；合入 `main` 可在验收后完成（`git log --oneline -1` 该分支可见）。
2. 卡头「状态」已为「已回写」，回写区填实现说明 + 测试结果 + push 证据。
3. HTTP 看板执行中曾出现本卡（执行列），且 ideally 看板出现 Δ dirty（worktree 污染物/脏标记变化）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据。

## 回写区

**执行体**：Claude Code · 日期：2026-08-06

### 实现说明
- 新增 `docs/notes/2026-08-06-e2e-smoke.md`（14 行，含目录 `docs/notes/`），说明本烟雾目的与验证链路；未触碰 `server/`、`desktop/`、权威短读、其它任务卡。
- 仅改本卡卡头「状态」及回写区，符合红线白名单。

### 测试结果
- 本文件新栈唯一改动 ≤20 行；白名单范围校验通过；`git diff` 仅含 notes 文件 + 本卡卡头/回写区。

### push 证据
- 分支 `codex/ccc001-e2e-smoke-engine-dirty`，commit `1e13c538`；已合入 `main`。

---

## 验收区（Cursor 独立取证 · 2026-08-06）

**判定：通过** ✅

| # | 标准 | 取证 |
|---|------|------|
| 1 | notes 文件在分支并合入 main | `docs/notes/2026-08-06-e2e-smoke.md` @ `1e13c538`，main ff 含该提交 |
| 2 | 卡头已回写 + 回写区齐全 | Engine 收单日志 `收单成功: work=ccc001 → 已回写`；回写区有实现/测试/push |
| 3 | 看板曾执行中 | `:7788/board/states` 观测到 执行中:1 → 已回写:2；worktree `ccc-dev-ws-ccc001` 创建成功 |

补充观测：首次 `--once` 曾因 kickstart 窗口误回收打回，复位待分派后自动派发成功；执行体日志 stdout 缓冲延迟，但产物与状态机正确。
