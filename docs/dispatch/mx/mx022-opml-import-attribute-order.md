# 任务卡 mx022 · OPML 导入属性顺序修复（OpenCode 执行）

> 关联：ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-08

## 目标

OPML 导入属性顺序修复（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/backend/core/src/ 下 RSS OPML 导入解析相关文件（api/routes/rss.rs 或 opml 模块）`
- `相关测试文件`

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读 `parse_opml`（src/backend/core/src/ 下 api/routes/rss.rs 或 opml 模块）现状：属性循环内 push 导致的 xmlUrl 先于 text 时 name 丢失 bug。
2. 重构：改为先完整解析一个 `<outline>` 的所有属性到临时结构体，循环外按优先级设定 name（text > title > url）再 push；移除循环内 push。
3. 兼容：现有 OPML 导入行为（xmlUrl/text/title 属性、嵌套 outline 分组）不回归；缺 name 时仍回落 url。
4. 新增/更新解析用例：xmlUrl 先、text 先、缺 text、嵌套分组、属性乱序；既有测试通过。
5. `cargo test`（rss/opml 相关）/ `cargo check` 通过（零警告）。
6. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. parse_opml 不再在属性循环内 push：完整解析 outline 全部属性后再按优先级设定 name 并 push，xmlUrl 在 text 之前时订阅名正确显示
2. 新增/更新解析用例覆盖属性顺序变体（xmlUrl 先、text 先、缺 text）；既有测试通过
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
