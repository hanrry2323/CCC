# 任务卡 mx010 · OPML 导出支持 Bearer 鉴权（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

修复 mx008 巡检 P0-9：RSS OPML 导出按钮（`RssSidebar.tsx` 原生 `<a>` 直链）改为 `fetch` 携带 Bearer 头获取内容 → `Blob` URL → 虚拟 `<a>` 模拟点击下载；未开启鉴权时行为不变，开启鉴权时导出不再 401。

## 红线（先看）

1. 只动白名单（RssSidebar 及前端 API 层、后端 OPML 导出端点仅当鉴权适配需要）；**禁止**改其他页面/组件与业务逻辑。
2. 导出内容与行为（文件名、格式、内容）不得改变；仅改传输方式。
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/frontend/src` 下 RssSidebar.tsx 及相关组件
- 前端 API 工具/鉴权头注入相关文件（沿用现有 token 注入方式）
- 后端 OPML 导出端点（如鉴权适配需要）

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读 `RssSidebar.tsx` 导出按钮现状（原生 `<a href=.../rss/opml>`）与前端现有鉴权头注入方式（API 客户端如何带 Authorization）。
2. 改为 `fetch`（携带 Authorization 头，方式与现有 API 客户端一致）获取 OPML 内容 → `Blob` 包装 → 创建虚拟 `<a>` 并 `click()` 下载；文件名与现有导出一致。
3. 未开启鉴权场景：同样走 fetch（行为不变），验证可正常导出。
4. 后端核对（只读）：`/rss/opml` 端点鉴权行为确认（若需调整按白名单最小改动）。
5. 验证：开启鉴权配置下点击导出成功下载且内容正确；`npm run test` / lint / build 通过。
6. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 开启 Bearer 鉴权时点击导出能携带 Authorization 头成功下载 OPML；未开鉴权行为不变
2. 前端相关测试（vitest）或手动验证记录通过；lint/build 零错误
3. 只动白名单；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 实现说明

1. **前端 RssSidebar.tsx 改造**：
   - 导入 `adminToken` 管理工具。
   - 将原生的 `<a>` 导出直链改为 `<button>`，使用 `onClick` 事件通过 `fetch` 获取 `rssApi.opml.export()`。
   - `fetch` 选项中通过 Headers 自动注入 Bearer Authorization Token（如果存在 `adminToken`）。
   - 提取响应文本，使用 `Blob` 包装并创建 Object URL，构建虚拟 `<a>` 标签模拟点击进行下载，下载完毕后及时清理。
   - 发生 401 错误时派发 `medio:unauthorized` 事件以触发 token 输入浮层，且包含健壮的异常捕获与 Toast 提示。

2. **后端鉴权中间件适配（src/backend/core/src/middleware/auth.rs）**：
   - 调整 `requires_auth` 逻辑：对 `GET` 方法下的 `/rss/opml` 和 `/rss/opml/` 端点强制启用鉴权（有 admin_token 场景下）。
   - 新增 `opml_export_requires_auth` 单元测试，确保 `GET /rss/opml` 的鉴权白名单防护符合预期。

### 测试结果

- 前端 Lint 检查（`npm run lint`）与 TypeScript 类型检查（`npx tsc -b`）顺利通过。
- 前端全量单元测试（`npm run test`）363 项全部 Pass。
- 后端新增 `opml_export_requires_auth` 单元测试。

### Push 证据 (Commit Hash)

- 业务仓 (`medio-0`) 同名分支 `codex/mx010-opml-export-bearer-auth` 提交哈希: `0eafdb7`

## 机审区

机审：通过

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
