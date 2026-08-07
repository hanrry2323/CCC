# 任务卡 mx014 · crawl_all 图片本地化缓存补齐（OpenCode 执行）

> 关联：ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

修复 mx008 巡检 P1-4：后台自动巡检 `crawl_all` 与手动 `crawl_one` 对齐，成功写入条目后触发正文图片本地化预缓存（`replace_image_urls` / `ImageCacheService`），自动巡检拉回的文章离线可读、不再热链防盗。

## 红线（先看）

1. 只动白名单（RSS 爬虫调度/保存相关文件）；**禁止**改数据库表结构、前端代码、其他业务模块。
2. **静默降级**：图片缓存任何失败只 warn、不得导致条目保存失败或抓取中断（缓存是锦上添花，不是链路阻塞点）。
3. 行为对齐 `crawl_one`：复用既有 `replace_image_urls` / `ImageCacheService` 路径，禁止另写一套缓存逻辑。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/backend/core/src/` 下 RSS 爬虫调度与保存相关文件（scheduler.rs、crawler 相关）
- 相关测试文件

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读 `scheduler.rs`：`crawl_all` 与 `crawl_one` 的差异（`replace_image_urls` 调用位置、ImageCacheService 用法）。
2. 在 `crawl_all` 成功写入条目后调用图片本地化预缓存（与 `crawl_one` 一致）；失败分支 `tracing::warn!` 记录、不中断后续条目。
3. 自测（回写区记录）：构造含外部图片 URL 的 feed（本地样例源或测试服务器），跑 `crawl_all`，验证落库条目正文图片为本地 URL；含一个失效图片 URL 的场景验证降级不中断。
4. `cargo test`（RSS 相关）通过；`cargo check` 零警告。
5. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. crawl_all 成功写入条目后触发正文图片本地化预缓存（与 crawl_one 的 replace_image_urls 路径一致）；图片缓存失败静默降级、不影响条目保存
2. 自测：构造含外部图片的 feed 跑 crawl_all，落库条目正文图片为本地 URL（回写区记录）；既有测试全部通过
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
