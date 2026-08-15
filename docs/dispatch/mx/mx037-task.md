# 任务卡 mx037 · 统一服务依赖注入（OpenCode 执行）
> 批准：老板合入批准 · 2026-08-15

> 关联：mx-plan-003 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-15




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/`（关联方案见卡头「关联」）

## 目标

引入依赖注入（DI）层：ScanScheduler / RssService 等服务一次构造为 Arc 单例，注入到使用处，消灭函数内 `new Service()` 的重复初始化。

## 实现

- 背景：ScanScheduler 内部现场 new MediaLibraryService（两次实例，冗余且无法 mock 测试）；RssService 等在多处 new。
- 要求：新增服务构造/注入层，改造 ScanScheduler（两次 new → 注入单例）、RssService 构造点，统一走注入。
- 行为等价：不改变业务语义，现有测试基线全绿。

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

1. grep 无 `new MediaLibraryService` / `new RssService`（非构造点）。
2. 服务单例注入后单测可 mock。
3. `cargo test` 相关测试全绿。

## 回写区

**执行体**：OpenCode · 日期：2026-08-15

1. **实现说明**：
   - 为 `AppState` 引入了 `rss_service` 单例域（`Option<Arc<RssService>>`）。
   - 在 Axum 服务器和 Tauri 主进程启动时，统一构造 `media_service`、`rss_service` 单例并作为 `Arc` 注入到 `AppState`。
   - 重构了 `ScanScheduler`：增加 `media_service` 注入属性，在 `run_scan_static` 内消除了原本的两次 `MediaLibraryService::new(...)` 现场实例初始化（一次用于 scan 扫描、一次用于异步元数据 ffprobe 探测），改为统一使用依赖注入的 `media_service` 实例。
   - `MediaLibraryService` 引入 `set_progress_callback(&self, cb)` 支持动态/线程安全的回调函数变更（内部由 `std::sync::RwLock` 保证并发读写安全性），使 `ScanScheduler` 在扫描触发时能够安全、动态注入扫描进度监听逻辑。
   - 彻底改造了 `api/routes/rss.rs` 中的 15 个接口处理器，将其现场硬写 `RssService::new(state.db.clone())` 的反模式替换为统一复用依赖注入单例 `state.rss_service`（带优雅的 fallback 逻辑保持最佳兼容性）。
   - 在 `lib.rs` 的 `test_admin_token_env_var_injection` 集成测试中补全了安全重构所需 server 配置必填字段，修复了此前破损的单测基线。

2. **测试结果**：
   - `cargo test --lib` 456 个单元/集成测试全绿通过，包括 RssService、ScanScheduler 等核心功能验证。
   - `cargo clippy --lib` 零错误，代码符合高标准重构要求。

3. **push 证据**：
   - 分支：`codex/mx037-task`
   - Commit Hash: `53a536baf9efe9432def3692756072ba417e3099`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `mx-plan-003` 正在由执行体逐步拆解落实，关联卡 `mx037` 开发已执行，进入已回写待合并阶段。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：本次重构为常规 Rust Arc 依赖注入与 RwLock 共享回调实现，不涉及外部非预期踩坑。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：内部服务解耦，不影响外部目录结构或部署路径。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：项目近况与线路规划稳定，按既定节奏演进。

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

  - **打回原因必须可执行**：格式 "问题 -> 文件:行号 + 唯一最佳动作"；禁止 "体验不好/不规范" 等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。

## 机审区

**验收席**：2017 机审 · 日期：2026-08-15

**机审：通过**

### 审查摘要

- 审查范围：medio-0 仓 `codex/mx037-task` 分支 commit `53a536b`（统一依赖注入）+ 机审修复 `f7cac77`（收敛 RssService 单例访问）。8 个文件改动，均在卡声明范围（core 依赖注入相关）内，未触碰无关模块。
- 实现审查：
  - RssService 在 server `main.rs` 与 tauri `server_runner.rs` 两个启动路径各构造一次 Arc 单例，注入 `AppState`；15 个 RSS 路由 handler 由 `RssService::new(state.db.clone())` 反模式改为取注入单例（机审修复收敛为 `AppState::rss_service()` 一处回退工厂，消除 15 处重复 `unwrap_or_else`）。
  - ScanScheduler 注入 media_service 单例，消除 `run_scan_static` 原两次 `MediaLibraryService::new`（scan 与 probe 改为共用 `service.clone()`）；`on_progress` 改 `RwLock<Option<ProgressCallback>>` + `set_progress_callback(&self, …)`，支持共享单例动态注入回调。`probe_and_update_metadata` 不读 `on_progress`，probe 复用无行为偏移；扫描单飞（scan_in_progress）保证回调不并发覆盖。
  - 防御性回退保留（`AppState::rss_service()` 工厂、scan_scheduler 未注入分支并注释说明），生产路径（server/tauri）始终注入，正常运行时不可达。
  - `lib.rs` 单测补 `host/port/data_dir` 必填字段：`ServerConfig` 三字段无 `serde(default)`，main 上该测试本已破损（`test_admin_token_env_var_injection`），修复合理。
- 验收标准核对：
  1. 路由层/扫描层 grep 无 `new RssService`/`new MediaLibraryService`（非构造点）——handler 已清零，仅剩构造点与已注释的防御性回退。
  2. 服务为 Arc 单例注入 AppState/ScanScheduler，单测可注入 mock。
  3. `cargo test` 全绿由引擎机械门禁裁决（456 tests）。
- 维护区四问逐项填写、无占位；`mx-plan-003` 状态「部分执行」与关联卡声明一致，无声明不实。
- 机审修复 commit `f7cac77` 已 push `codex/mx037-task`。