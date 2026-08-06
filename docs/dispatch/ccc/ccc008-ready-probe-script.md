# 任务卡 ccc008 · ready-probe 脚本（OpenCode 执行）

> 关联：ccc-plan: M7 ready-probe dogfood · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-07

## 目标

ready-probe 脚本（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）

## 范围

- `scripts/ready-probe.sh`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. test -x scripts/ready-probe.sh
2. scripts/ready-probe.sh | grep -E '^ready_count=[0-9]+$'

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 回写区

**执行体**：OpenCode · 日期：2026-08-07
- 实现说明：新建了 `scripts/ready-probe.sh` 脚本，具备执行权限，通过调用板端 API `/board/ready_for_merge` 获取待合入卡片数量，提取 count 并以 `ready_count=N` 格式进行输出。
- 测试结果：
  ```
  $ scripts/ready-probe.sh
  ready_count=0
  ```
  符合格式验证。
- push 证据：`666dcd5fcde6068a2dec3b5d3b428e3c446e4540`
