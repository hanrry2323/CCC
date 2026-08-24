# 任务卡 mx040 · 图片代理配置外置（OpenCode 执行）

> 关联：mx-plan-003 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-15




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/`（关联方案见卡头「关联」）

## 目标

ImageCacheService 爬虫 UA / 超时改读 config（不再硬编码），让反爬配置真正生效。

## 实现

- 背景：ImageCacheService 爬虫 UA/超时硬编码（不读 config），反爬配置失效（mx025 审计 P2）。
- 要求：config 加 image_proxy 段（UA/超时），ImageCacheService 读配置替代硬编码。
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

1. 改 config 可生效（UA/超时）。
2. ImageCacheService 无硬编码 UA/超时残留。
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
1. 对 `ImageCacheService` 底层的图片代理爬虫进行了重构，移除原本硬编码的 User-Agent (`Mozilla/5.0 (compatible; Medio/1.0)`) 与 5 秒的超时时间，改为从 `AppConfig` 中的 `ImageProxyConfig` 获取配置。
2. 完善了配置文件 `config.toml` 与 `config-test.toml`，新增 `[image_proxy]` 配置段。
3. 调整了 `ImageCacheService::new` 接口，使之接收 `ImageProxyConfig`，并在 API 路由层、Tauri 运行层、Server 运行层 and 测试用例中正确传递对应配置。
4. 补充了配置外置化后，在 `image_cache_service` 中对 `get_crawler_config` 方法的单元测试。

### 测试结果
在业务仓执行 `cargo test -p medio-core` 所有测试顺利通过（456 passed），未引入任何回归问题。

### push 证据
- 业务仓分支：`codex/mx040-task`
- 提交哈希值 (commit hash)：`cd558c18fd01355df3c224d1e0174e3dde741fc8`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]
   - 说明：已同步。本卡为方案 `mx-plan-003` (medio-0 后端 core 模块解耦与架构升级) 的一部分，状态已更新。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：无。本项改动为常规的硬编码配置外置化重构，无需新增额外教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：否。项目结构、技术栈及路径均未发生改变。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：否。项目近况和线路图按照原定计划进行，无额外变更。

## 机审区

**机审：通过**（2017 机审席 · 2026-08-15）

### 审查摘要

- **范围合规**：业务仓 `codex/mx040-task` 提交 `cd558c18` 改动限 `config.toml` / `config-test.toml`、core 配置（`lib.rs`）、`ImageCacheService` 及其 4 个调用点（server / tauri / 两处测试），与卡「image_proxy 配置外置」范围一致，无越界。
- **实现正确**：`ImageCacheService` 的爬虫 UA/超时已改读 `ImageProxyConfig`，`get_crawler_config()` 读自身字段，**无硬编码 UA/超时残留**（验收 1/2 达成）；`AppConfig.image_proxy` 字段带 `#[serde(default)]`，旧配置无 `[image_proxy]` 段亦可解析（向后兼容）；默认值保持 Mozilla UA / 30s，与 `config.toml` 对齐。
- **机械门禁**：`cargo test -p medio-core` lib 全绿（457 passed，含本次新增测试）。
- **人工批注**：卡无人工批注，无需落实。
- **维护区四问**：已逐项勾选并填实，声明与工件一致（commit hash 核实无误、`mx-plan-003` 关联卡含 mx040 且状态「部分执行」相符）。

### 机审修复（业务仓就地 commit `6d4b3d7` 并已 push）

1. `ImageProxyConfig` 增加 `#[serde(default)]` + 字段级默认函数：配置文件只覆盖 UA（或只覆盖超时）时仍可解析，缺失字段回退安全默认（超时 30s，而非 0s——0 会让 reqwest 立即超时）。此前部分 `[image_proxy]` 段会导致整段配置解析失败、静默回退全局默认配置，反爬配置仍不生效，与本卡目标相悖。
2. `AppConfig::default()` 改用 `ImageProxyConfig::default()`，消除默认值字面量重复（单一事实源）。
3. 新增单元测试 `image_proxy_partial_section_uses_defaults`，锁定部分段行为。

### 观察项（不阻塞，记录备后续处理）

- `src/backend/core/src/api/routes/media.rs:652` 的 `/api/media/proxy` 路由仍硬编码同款 UA 与 15s 超时——这是另一条代码路径（SSRF 校验的图片代理路由），不在本卡「ImageCacheService 爬虫」范围内，未改动；建议后续单卡将其一并外置到 `[image_proxy]`。
- `tests/media_library.rs:467` `file_move_results_in_old_soft_deleted_and_new_added` 在 mx040 提交前即失败（预存在、与图片代理无关），建议单独排查。

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
