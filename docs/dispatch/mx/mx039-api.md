# 任务卡 mx039 · API 路由层服务复用（OpenCode 执行）

> 关联：mx-plan-003 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：mx · 日期：2026-08-15




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/`（关联方案见卡头「关联」）

## 目标

API 路由层 handler 不再每次请求 new RssService，改为从 AppState 子域取注入的单例服务。

## 实现

- 背景：API 路由层每次请求 new RssService（额外开销、屏蔽 DI，mx025 审计 P1）。
- 要求：路由构造统一从 AppState 子域取服务，删除 handler 内 new。
- 行为等价：不改业务语义，现有测试基线全绿。

## 红线（先看）

1. 只动本功能卡范围内模块，不碰无关模块。
2. 行为等价重构：不改业务语义/数据结构/API 契约。
3. 不直推 main；不写 `## 机审区` / `## 验收区` / 置「已关闭」。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

medio-0 后端 core 相关模块（见「实现」），白名单内改动。

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 路由 handler 无每次请求 new 服务（从 state 取注入单例）。
2. API 路由测试全绿。
3. `cargo test` 相关测试全绿。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-15

### 实现说明
1. 对 `AppState` 结构体进行了扩展，新增 `rss_service: Option<Arc<RssService>>` 字段、初始化设置以及对应的 `.with_rss_service(rss_service)` builder 方法。
2. 在 `src/backend/server/src/main.rs` 和 `src/backend/tauri/src/server_runner.rs` 初始化时实例化单例 `RssService`，并在构造 `AppState` 时注入此共享服务。
3. 在 `src/backend/core/src/api/routes/rss.rs` 路由层的所有 handlers 中，删除原先每次请求时局部调用 `RssService::new(state.db.clone())` 的行为，统一使用从 `AppState` 取出并克隆的注入服务实例。
4. 清理了 `rss.rs` 中因重构而变成未使用的 `use crate::service::rss::service::RssService;` 引入。

### 测试结果
- 全量/局部编译检查完美通过，且无任何警告。
- 本地 RSS 相关测试如 `tests/rss_list_items.rs` 和 `tests/service_crawler.rs` 运行全绿并顺利通过。

### push 证据
- 关联分支：`codex/mx039-api`
- 提交哈希：`e40cffe3a4770f8f6a4ac241168ad886b6f602a1`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案 mx-plan-003 进入部分执行阶段，关联卡为 mx039）
   - 说明：已同步状态并关联。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（此为按部就班的依赖注入重构，不涉及特殊的新教训）
   - 说明：无。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（没有新增项目或修改路径，仅内部依赖重构）
   - 说明：否。
4. **线路图**：项目近况/下一步是否变化？[否]（整体 v0.9.0 之后按计划平稳演进）
   - 说明：否。

## 执行提示

- 项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）

- 项目仓（只读参考）：/Users/fan/program/apps/medio-0（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要：目标：对 medio-0 后端 core 模块做依赖解耦与架构升级：恢复 WebSub 实时推送断链（P0）、消除 AppState 上帝状态、统一依赖注入（Arc 服务单例化）、配置外置化，为后续公开化与多端 CI 打稳底座。全部改造以行为等价为准（不改变业务语义，改动后现有测试全绿）。验收标准：WebSub 实时推送恢复（`rss/service.rs` 路径引用修复，联动逻辑可运行） ScanScheduler / RssService 不再内部 new 服务，统一注入 Arc 单例 AppState 拆分完成（子状态域各自独立，AppState 仅聚合） API 路由层 handler 复用注入服务（无每次 new） ImageCacheService 读 config（UA/超时），PlaybackService 注入 RateLimitMap `cargo test` +...

- 项目线路/近况：
  - 版本 **v0.9.0**（VERSION 文件）；35 张卡（mx001-035）全关闭，2 个方案（mx-plan-001 RSS 打磨、mx-plan-002 收口安全）已完成。
  - **2026-08-12 mx-plan-002 收口与安全加固完成**：修复 4 个 P1 安全漏洞（XSS/鉴权 fail-closed/暴力破解限制/SSRF）、Token 环境变量化、双机路径对齐、9 个积压分支清理、补打 v0.9.0 Tag、脚本审查清理（mx030-035）。
  - 三条功能分支（`library-management`/`ui-upgrade`/`rss-bugs`）已 100% 合入 main，集成风险为 0。

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：

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

  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。

## 机审区

**验收席**：2017 机审 · 日期：2026-08-15

**机审：通过**

### 审查摘要

- 审查范围：medio-0 仓 `codex/mx039-api` 分支 commit `e40cffe`（API 路由层服务复用）。4 个文件改动（`api/routes/rss.rs`、`api/state.rs`、`server/main.rs`、`tauri/server_runner.rs`），均在卡声明范围（后端 core 相关模块）内；CCC 仓 worktree 分支 `codex/mx039-api` 仅改卡文件，无平台越界。
- 实现审查：
  - `AppState` 新增 `rss_service: Option<Arc<RssService>>` 字段（state.rs:21）+ `with_rss_service()` builder（state.rs:79），`new()` 默认 `None`（state.rs:51），与既有 `cover_service`/`crawl_scheduler`/`media_service` 注入模式一致。
  - RssService 单例在两条启动路径各构造一次（server `main.rs:244`、tauri `server_runner.rs:123`），与 `state.db` 共用同一 `SqlitePool`（同一 Arc）；RssService 仅持 pool、无内部可变状态 → 并发安全、行为等价。
  - 15 个 RSS 路由 handler 全部由 `RssService::new(state.db.clone())` 反模式改为从 state 取注入单例；`grep RssService::new api/routes/rss.rs` = 0，全仓非测试构造点仅剩两条启动路径。未注入时返回 `AppError::Internal`（500），与同文件 `crawl_scheduler` 既有 `as_ref().ok_or_else` 防御写法一致，运行面两路径均注入、正常不可达。
  - 清理重构后未使用的 `use crate::service::rss::service::RssService;` 引入（rss.rs）；state.rs 新增同路径 import 被字段类型使用，无告警。
- 验收标准核对：
  1. 路由 handler 无每次请求 new 服务 ✔（rss.rs 内 `RssService::new` 清零）。
  2. API 路由测试全绿 ✔（机械门禁裁决，本机不再重复）。
  3. `cargo test` 相关测试全绿 ✔（机械门禁裁决，本机不再重复）。
- 维护区四问逐项填写、无占位；方案同步 [是] 与 `mx-plan-003` 状态「部分执行」一致（plan 文件 line 3 状态、line 5 关联卡 mx036-041 已核实）；push 证据 commit `e40cffe` 已上 `origin/codex/mx039-api`（本地与远端一致）；无声明不实。
- 协调提示（P2·不阻断）：本卡与并行卡 mx037（已机审通过，采用 `AppState::rss_service()` 防御性回退工厂）在 `state.rs` rss_service 字段/builder 与 `rss.rs` 15 个 handler 转换上重叠。两卡同属 mx-plan-003 并行拆分，属计划层面重复，非本卡缺陷。合入 main 时 rebase 会产生冲突，建议以 mx037 已通过的 helper 实现为准收敛。
- 小建议（不阻断）：15 处重复 `as_ref().ok_or_else` 可抽为 `AppState` 辅助方法（与 mx037 方向一致）；当前与同文件既有 `crawl_scheduler` 写法一致，可接受，不强制。
