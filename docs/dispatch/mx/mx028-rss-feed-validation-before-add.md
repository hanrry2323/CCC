# 任务卡 mx028 · RSS feed validation before add（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭 · 派发：engine · 项目：mx · 日期：2026-08-09

## 目标

在 RSS 源添加流程中增加 feed URL 合法性校验：添加前先对 URL 做 HTTP HEAD 请求，验证返回 200 且 Content-Type 含 xml/rss/atom，无效 URL 拒绝添加并返回错误提示。

## 红线（先看）

1. 只改 RSS 源添加流程，不改其他业务逻辑
2. 校验失败时给出明确错误信息，不静默跳过
3. 若本卡含 `## 人工批注`，执行体必须先读批注

## 范围

- `src/backend/core/src/rss/`：RSS 源添加逻辑
- 不动：`src/backend/server/`、`src/frontend/`

## 步骤

1. 进入 `/Users/fan/program/apps/medio-0`，确认工作区干净
2. 定位 RSS 源添加入口（HTTP handler 或 service 层）
3. 添加 URL 校验逻辑：HTTP HEAD → 检查 status 200 + Content-Type
4. 无效 URL 返回明确错误
5. commit+push 到卡内分支；卡头改为「已回写」
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 添加无效 URL 时返回错误提示（非 200 或非 xml/rss/atom）
2. 添加有效 RSS 源正常工作
3. 零业务逻辑改动（仅校验层）

## 门禁

范围: true

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. 深入定位到了 `RssService::create_subscription` 添加入口，并加入了 URL 校验逻辑。
2. 限制在添加订阅前对目标 URL 触发 HTTP HEAD 请求。
3. 校验机制：
   - 验证 HTTP 响应状态码必须是 `200 OK`。
   - 验证 HTTP 响应头中的 `Content-Type` 必须包含 `xml`、`rss` 或 `atom` 关键字之一。
   - 校验不通过或请求失败时，直接拦截插入数据库并返回清晰具体的错误信息。
4. 在测试环境下提供了优雅的 Mock 方案，确保本地单测能够完美、稳定地在离线环境下完成逻辑验证。
5. **SSRF Mock 域名支持**：修复了测试环境下模拟域名因未通过 `validate_safe_url` 的 SSRF 检查而被拦截的问题（引入 `is_mock` 在测试中拦截并放行 `mock-` 域名的安全检查，解决离线测试环境下 DNS 解析失败的痛点）。

### 测试结果
1. 包含了三个针对校验的单元测试：
   - `create_subscription_rejects_invalid_status`：验证非 200 返回码的 URL 会被拦截并报错。
   - `create_subscription_rejects_invalid_content_type`：验证不含 xml/rss/atom 的 content-type 的 URL 会被拦截并报错。
   - `create_subscription_rejects_request_failed`：验证 HEAD 请求失败的 URL 会被拦截并报错。
2. 所有新增的测试用例与原有用例编译完全正常。在业务仓 `/Users/fan/program/apps/medio-0` 中，执行 `cargo test --package medio-core --lib service::rss::service::tests`，所有 37 个 RSS 单元测试完全通过。

### push 证据
- 业务仓 (medio-0) 提交哈希: `d5be9868fb1a638759daacfb2fde32c19a56f296`
- 业务仓分支: `codex/mx028-rss-feed-validation-before-add`

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）

- 仓库路径：/Users/fan/program/apps/medio-0（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 历史教训（避免踩坑）：
  - [domains::projects::4__WebSub_断链_2026-08___mx025_审计_] 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **状态**：mx026 修复中（P0） - **适用场景**：RSS 模块路径或依赖变更

- 禁区：- 前缀是 `mx` 不是 `medio`；卡文件名必须 `mxNNN-…`
- 禁止在 CCC 建业务深文档目录

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）

- 审查清单：
  - [domains::projects::section_0] mx (medio-0) 代码审查清单 > 项目：medio-0 > 审查重点：基于历史审计发现（mx025）和架构决策（ADR-001~013）
  - [domains::projects::4__WebSub_断链_2026-08___mx025_审计_] 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **状态**：mx026 修复中（P0） - **适用场景**：RSS 模块路径或依赖变更

- 历史教训（审查时重点关注）：
  - [domains::projects::4__WebSub_断链_2026-08___mx025_审计_] 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **状态**：mx026 修复中（P0） - **适用场景**：RSS 模块路径或依赖变更

- 架构约束/红线：- 前缀是 `mx` 不是 `medio`；卡文件名必须 `mxNNN-…`
- 禁止在 CCC 建业务深文档目录

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

## 验收区

**验收人**：Claude Code · 日期：2026-08-09

**审查结论**：✅ 判定：通过。

- 范围：仅 `src/backend/core/src/service/rss/service.rs`，零越界
- 测试：RSS 37 全绿（含 3 新增），core 全量 426 全绿
- 安全：`#[cfg(test)]` 隔离 mock 逻辑，生产 SSRF 不受影响
- 功能：HTTP HEAD → 200 + Content-Type 校验，失败返回明确错误

**合入说明**：机审因执行体首次写回状态错误（completed→已回写）被跳过，人工补审通过，手动合入。

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
