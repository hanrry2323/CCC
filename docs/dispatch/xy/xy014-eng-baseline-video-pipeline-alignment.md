# 任务卡 xy014 · 工程化：video-pipeline 与旁路对齐 + 退役决策落盘（OpenCode 执行）

> 关联：ccc-plan: xianyu 工程化底座补齐 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

工程化：video-pipeline 与旁路对齐 + 退役决策落盘（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `.ccc/`
- `docs/research-notes/`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 只读核 src/xianyu/video/ 与 video-pipeline/ 的引用关系，结论写入 xianyu 仓 .ccc/ 决策文档（哪条是生产路径、旁路去向：退役/冻结/保留）
2. 12 个 launchd 守护清单 + 职责 + 停止命令成文于 xianyu 仓 .ccc/ops.md
3. openclaw 退役口径在 .ccc 档案中清除（不再提为现行部署）
4. 只改 xianyu 仓文档，零代码改动；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：
