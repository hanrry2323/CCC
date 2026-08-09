# 任务卡 ccc013 · 新流程全链路验证（OpenCode 执行）

> 关联：ccc-plan-004 · 新流程验证（2026-08-08） · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-08

## 目标

验证 CCC 升级后自动化流程全链路闭环（sidecar 状态保持 + 回写 + 机审）：新增一个最小探针脚本，走完「待分派 → 执行中 → 已回写 → 机审通过」全流程，为后续业务卡铺路。

## 红线（先看）

1. 只新增 `scripts/pipeline-flow-verify.sh` 一个文件，禁止改其他任何文件；禁止碰 `server/`、`docs/dispatch/` 其他卡。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `scripts/pipeline-flow-verify.sh`（新增，≤60 行）

## 步骤

1. 新增 `scripts/pipeline-flow-verify.sh`：脚本依次输出三行阶段标记并退出 0——
   - `PROBE_STATE_HOLD`（验证回写后状态保持）
   - `PROBE_WORKTREE_OK`（验证 worktree 生命周期探针）
   - `PROBE_EXIT_OK`
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `scripts/pipeline-flow-verify.sh` 存在且 `bash -n scripts/pipeline-flow-verify.sh` 通过
2. `bash scripts/pipeline-flow-verify.sh` 实际运行输出含 `PROBE_STATE_HOLD` / `PROBE_WORKTREE_OK` / `PROBE_EXIT_OK` 三行并退出 0（回写区附真实输出）
3. 回写区填实现说明、测试结果、push 证据（commit hash）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-08

### 1. 实现说明

新增了最小探针脚本 `scripts/pipeline-flow-verify.sh`，仅包含 `set -euo pipefail` 和输出三行状态标志的核心逻辑，无额外注释。

### 2. 测试结果

`bash -n scripts/pipeline-flow-verify.sh` 通过，本地执行输出：
```
PROBE_STATE_HOLD
PROBE_WORKTREE_OK
PROBE_EXIT_OK
```
进程退出码：`0`

### 3. push 证据

- Commit Hash: `dcb0e7910be6ef234d0152c737425ea2ce998e41`
- 目标分支: `codex/ccc013-flow-verify-pipeline` (已成功 push 至 origin)

## 机审区

**机审：通过**

机审席：Claude Code（独立审查）· 日期：2026-08-08

### 审查摘要

新流程全链路验证卡 ccc013，只新增最小探针脚本 `scripts/pipeline-flow-verify.sh`（5 行，≤60），走完「已回写 → 机审通过」。与验收标准对照全部满足。

### 发现清单

无 P0 / P1 发现。

### 修复记录

无 —— 本轮零发现，未触发就地修复。

### 复审结论

PASS。红线合规（仅新增脚本 + 必要卡头/回写区更新，未碰 `server/`、其他卡、无关文件，未触碰机审区/验收区/已关闭/直推 main）；三种探针标志实机输出与回写一致，退出码 0；人工批注节为空无需落实。建议合入。
