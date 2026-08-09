# 任务卡 mx020 · RSS 保存事务化（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-08

## 目标

RSS 保存事务化（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/backend/core/src/ 下 RSS 条目保存与标签写入相关文件`
- `相关测试文件`

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读 `save_rss_item_with_auto_tags`（src/backend/core/src/ 下 RSS 保存模块）现状：INSERT rss_items → SELECT tags → 循环 INSERT rss_item_tags，当前无事务包裹。
2. 用 `sqlx::Transaction` 包裹单条保存流程（INSERT item + 标签关联在同一事务内）；批量导入路径（如一次多个条目）按批量事务或逐条事务权衡实现（回写区说明选择）。
3. 异常处理：事务失败整体回滚，不留半条数据；错误信息保留（不吞错）。
4. 自测/单测：构造中途失败场景（如非法数据触发约束错误）验证回滚；批量导入场景验证无 Busy 锁（如压力插入）；既有 RSS 相关测试通过。
5. `cargo test` / `cargo check` 通过（零警告）。
6. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. save_rss_item_with_auto_tags 及批量导入路径用 sqlx Transaction 包裹（单条/批量），大幅减少 commit I/O、避免 SQLite Busy 锁库
2. 写入原子性验证：中途失败回滚、不留半条数据（自测或单测）；既有 RSS 相关测试通过
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
