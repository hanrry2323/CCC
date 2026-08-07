# 任务卡 mx015 · crawl_all 错误状态写回数据库（OpenCode 执行）

> 关联：ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

修复 mx008 巡检 P1-3：后台自动巡检 `crawl_all` 的失败状态对齐 `crawl_one` 写回数据库（`last_error` / `last_error_at` / `retry_count`），自动调度的订阅失败在前端订阅源列表可见，异常追踪链路统一。

## 红线（先看）

1. 只动白名单（RSS 调度错误处理）；**禁止**改数据库表结构（字段已存在）、前端代码。
2. 语义与 `crawl_one` **完全一致**：失败写回错误信息/时间/递增重试计数；成功路径清理错误状态（对齐既有逻辑）。
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/backend/core/src/` 下 RSS 调度错误处理相关文件（scheduler.rs）
- 相关测试文件

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读 `scheduler.rs`：`crawl_one` 的错误写回逻辑（字段名/语义/成功清理）与 `crawl_all` 的 Err 分支现状（当前只 `tracing::warn!`）。
2. 对齐实现：`crawl_all` 单源抓取失败时写回 `last_error`、`last_error_at`、`retry_count` 递增（与 `crawl_one` 一致）；成功时清理错误状态。
3. 自测（回写区记录）：构造一个失败源（如不存在的域名），跑 `crawl_all`，直接查询 SQLite 验证错误字段正确写入、重试计数递增；再构造恢复场景验证成功清理。
4. `cargo test`（RSS 相关）通过；`cargo check` 零警告。
5. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. crawl_all 单源抓取失败时写回 last_error / last_error_at / retry_count（语义与 crawl_one 一致）；成功时清理错误状态
2. 自测：造一个失败源跑 crawl_all，DB 错误字段正确更新（回写区记录）；既有测试通过
3. 只动白名单；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
