# 任务卡 mx038 · AppState 拆子状态（OpenCode 执行）

> 关联：mx-plan-003 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：mx · 日期：2026-08-15




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/`（关联方案见卡头「关联」）

## 目标

把捆绑 7+ 服务的 AppState 上帝状态拆成子状态域（rss / media / scan / cache / playback），AppState 仅聚合子域，各管各的。

## 实现

- 背景：AppState 上帝状态捆绑 7+ 服务，改动全局、违反最少特权（mx025 审计 P1）。
- 要求：定义子状态域结构，迁移服务持有关系，AppState 组合子域，更新引用点。
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

1. AppState 不再直接捆绑全部服务。
2. 各子域独立可测试。
3. `cargo test` 相关测试全绿。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-15

1. **实现说明**：
   - 将上帝共享状态 `AppState` 解耦为 5 个领域子状态域（`rss`、`media`、`scan`、`cache` 和 `playback`），由 `AppState` 聚合，降低模块耦合。
   - 重构了 `AppState::new` 与相关 builder 模式注入方法（保持了 100% 对向后兼容性，避免影响其他启动/测试代码）。
   - 全量重构了 `medio-core` 下所有 API handler 以及相关路由中对 `AppState` 属性的引用方式，如 `state.cover_service` 重构为 `state.cache.cover_service`、`state.scan_in_progress` 改为 `state.scan.scan_in_progress` 等。
   - 修复了 `lib.rs` 中单元测试 `test_admin_token_env_var_injection` 因反序列化缺少 required 字段导致的报错，现全库测试完好通过。

2. **测试结果**：
   - 运行 `cargo test -p medio-core --lib`：所有 456 项测试全绿通过。

3. **Push 证据**：
   - 提交分支：`codex/mx038-appstate`
   - 提交哈希：`bb6b237`

## 机审区

机审：通过
- 审查摘要：范围 = medio-0 业务分支 `codex/mx038-appstate` 两张 commit：`bb6b237`（AppState 拆子状态）＋机审可修项 `9740a5c`（cargo fmt 收口）。逐条独立取证：
- 范围：`bb6b237` 仅改 9 个文件（`api/state.rs`、6 个 route 文件、`server/main.rs`、`core/lib.rs` 测试夹具），全部在「AppState 拆子状态」白名单内；`rss/service.rs`（WebSub 联动）零改动，mx025 历史教训（路径重构断 WebSub）未复发；未直推 main、未写验收区/未置已关闭。
- 架构与质量：`AppState` 拆为 rss/media/scan/cache/playback 五个子状态域，各域持有依赖、AppState 聚合，跨切面基础设施（db/config/event_tx/rate_limiter/audit_service）留在顶层合理；builder 注入方法（`with_cover_service` 等 6 个）保留，`AppState::new` 签名不变 → tauri `server_runner.rs` 与测试构造点零改动兼容；分支上 grep 无旧字段路径残留。
- 行为等价：纯字段搬家与路径改写，无业务语义/数据结构/API 契约变化；`main.rs` 结构体字面量各字段值与拆分前逐一一致；`lib.rs` 测试夹具补 host/port/data_dir 是修既有必失败测试（`ServerConfig` 该三字段无 serde default，原 TOML 缺字段必反序列化失败），已如实披露，非生产语义变更。
- 可修项（已就地修复）：`cargo fmt --check` 命中 mx038 改动文件 3 处格式差异（`rss.rs:620` 长行折行、`state.rs:24` 长行折行、`state.rs:50` 空白行尾随空格）→ 已 `cargo fmt` 修正并提交推送 `9740a5c`，`cargo fmt --check` 现为绿。
- 维护区（Doc-Gate）：四问逐项填写无占位——方案同步 [是]（已核 `003-base-decoupling-and-arch-upgrade.md` 状态「部分执行」且 mx038 在关联卡）、教训沉淀 [无]/档案 [否]/线路图 [否] 均与实际一致；Push 证据 `bb6b237` 经 `git show` 核实真实存在，与卡改动一致。
- 结论：无原则性红线问题（无业务意图违背/无系统性越界/无安全漏洞），通过。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：已在方案中将本卡关联与状态更新为已回写，持续推进 mx-plan-003。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：无。本项为纯结构层面的等价行为解耦。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：没有更改项目核心技术栈与对外公开的 API 契约，仅为后端核心 AppState 的内部微观解耦，项目整体架构与路径不变。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：按既定线路图与方案稳步推进，没有额外的变动。

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
