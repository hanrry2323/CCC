# 任务卡 mx036 · 恢复 WebSub 实时推送断链（OpenCode 执行）
> 批准：老板合入批准 · 2026-08-15

> 关联：mx-plan-003 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-15




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/`（关联方案见卡头「关联」）

## 目标

修复 `rss/service.rs` 的路径引用断链，恢复 RssService 与 WebSub 实时推送联动，让订阅的网站一更新就主动推给 medio-0（不再依赖手动刷新轮询）。

## 实现

- 背景：WebSub 实时推送功能在之前路径重构时编译报错，被注释禁用（`rss/service.rs:94` 附近），功能断链（mx025 审计 P0）。
- 要求：
  1. 核对 `rss/service.rs:94` 断链处的引用路径（模块/函数路径与重构后不符）。
  2. 恢复 RssService 与 WebSub 的联动逻辑：订阅 → hub 推送 → 回调更新。
  3. 补测试覆盖推送链路。
- 行为等价：不改变业务语义，现有测试基线全绿。

## 红线（先看）

1. 只动 RSS/WebSub 联动相关文件（`rss/service.rs` 及直接依赖），不碰无关模块。
2. 行为等价重构：不改业务语义/数据结构/API 契约。
3. 不直推 main；不写 `## 机审区` / `## 验收区

**合入批准** · 日期：2026-08-15
- 判定：通过
` / 置「已关闭」。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/backend/core/rss/service.rs`（及直接相关的 rss 模块引用）
- 相关测试文件

## 步骤

1. Read 卡全文 + 项目基准（README/ARCHITECTURE）+ `docs/architecture-coupling.md`（WebSub 断链说明）。
2. 在 worktree 内核对 `rss/service.rs:94` 断链引用路径，恢复 WebSub 联动逻辑，补测试。
3. 跑 `cargo test`（相关测试全绿）确认行为等价。
4. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
5. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `rss/service.rs` 断链路径引用修复，编译通过。
2. WebSub 推送链路（订阅 → 推送 → 回调更新）逻辑恢复，无注释禁用残留。
3. 相关测试通过（`cargo test` 中 rss/websub 相关用例绿）。
4. 无无关模块改动（范围白名单内）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-15

1. **实现说明**：
   - 联动订阅触发：在 `RssService::detect_and_save_websub` 成功检测并保存 WebSub 支持后，主动构造 `WebSubService` 实例并调用 `subscribe()`，向 hub 发起真正的订阅请求，自动把状态机从 `detected` 推进至 `pending`。
   - 回调更新解析与自动标签：在 `WebSubService::handle_notification` 中，检测推送内容，若为 XML 内容（RSS 2.0 / Atom），则分别使用 `::rss::Channel` 和 `atom_syndication` 进行格式解析，并提取 `RssItem`。最后通过 `save_rss_item_with_auto_tags` 自动持久化并联动 NLP 系统进行文章分类和自动标签。
   - 同名模块遮蔽修复：使用全局绝对路径 `::rss::Channel::read_from`，解决 Rust 同名子模块 `crate::service::rss` 造成的遮蔽编译问题。
2. **测试结果**：
   - 全量 `cargo test --lib rss` 通过（包含 132 个单元测试）。
   - 新增 `test_handle_notification_with_xml_content` 覆盖 WebSub 推送 XML (RSS 2.0 / Atom) 的端到端解析入库和自动标签验证。
3. **push 证据**：
   - 业务仓分支：`codex/mx036-websub`
   - 业务仓 commit hash：`6b3604a11f287317d7b38d38760fa0ec3534dbe2`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `mx-plan-003` 目前状态仍为「部分执行」（本卡 mx036 为其子卡首期完成）。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：已在业务仓 `docs/lessons.md` 中新增一条关于「同名模块遮蔽」与「WebSub 闭环联动逻辑恢复」的教训归档。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：本卡不涉及项目结构/技术栈或新公开文件路径的变化。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：项目近况/路线保持不变，按计划继续推进架构升级方案。

## 机审区

**验收席**：2017 机审席 · 日期：2026-08-15 · 状态：**机审：通过**

### 审查摘要

独立核对业务仓 `medio-0` worktree（`/Users/fan/program/apps/.ccc-wt/mx/mx036`）分支 `codex/mx036-websub` 相对 `origin/main` 全量 diff，以及本卡回写区/维护区声明。

**范围核对**：改动落在 `src/backend/core/src/service/rss/service.rs`、`src/backend/core/src/service/rss/websub.rs`、`docs/lessons.md`（教训沉淀，维护区勾选所需）；机审修复另触及 RSS API 路由层 `src/backend/core/src/api/routes/rss.rs`（RSS/WebSub 直接依赖）。全部在卡片白名单内，无无关模块改动。

**WebSub 联动恢复评估**：
1. 断链修复：`detect_and_save_websub` 检测到 hub 后主动构造 `WebSubService::subscribe()`，把状态从 `detected` 推进到 `pending`，恢复「订阅 → hub 推送 → 回调更新」闭环，无注释禁用残留。
2. 回调更新：`handle_notification` 移除仅查 secret 的 `get_secret`，改为整行 `Subscription` 查询，并用 `::rss::Channel`（显式全局路径解决同名模块遮蔽）与 `atom_syndication` 解析推送内容，经 `save_rss_item_with_auto_tags` 幂等落库并联动 NLP 自动打标；空/非 XML 推送优雅降级。
3. 新增 `test_handle_notification_with_xml_content` 覆盖 RSS 2.0 推送端到端解析入库与自动标签。

**机审修复（就地）**：发现自动订阅回调基础地址硬编码 `http://127.0.0.1:3000`（`service.rs`），违反项目「零硬编码」原则，且与路由层 `server.host:port` 约定不一致——server 配置变更后推送链路会静默失效。已修复：新增 `RssService::with_websub_callback` 构造器注入配置派生回调地址，`create_subscription` 与 `import_opml` 两个生产入口改为注入 `http://{server.host}:{server.port}`（与 verification/notification 处理器同一来源）；未注入回调地址时跳过自动订阅。修复后 `cargo check -p medio-core` 通过、`cargo test -p medio-core --lib rss` 132 个用例全绿（含本卡新增用例），commit `f2aebb3` 已 push 至 `codex/mx036-websub`。

**完成钩子（Doc-Gate）**：维护区四问逐项勾选且说明非占位；[是] 声明「mx-plan-003 部分执行」核实为真（`docs/projects/mx/plans/003-base-decoupling-and-arch-upgrade.md` 状态=部分执行）；[有] 声明 `docs/lessons.md` 新增条目真实存在（2026-08-15 条目）。声明与卡改动一致。

**非阻断建议**（记录不判）：`handle_notification` 前置 guard 用 `trimmed_content` 判断、解析用 `content`（未 trim）——推送体前导空白极罕见，可后续统一为 trim 后字节。

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
