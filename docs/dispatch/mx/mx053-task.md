# 任务卡 mx053 · 后端核心模块测试覆盖率除债与单测补齐 — 后端核心模块测试覆盖率补齐（OpenCode 执行）
> 批准：老板确认转卡 · 2026-08-19

> 关联：mx-plan-008 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：mx · 日期：2026-08-19




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/`（关联方案见卡头「关联」）

## 目标

收窄 tarpaulin 覆盖率屏蔽，补 websub_service/scan_scheduler/rss_service 等核心后端单测，行覆盖率≥80%。

## 实现

①`Cargo.toml`/`tarpaulin.toml` 移除对 `service/rss/*`、`scan_scheduler` 等的排除项（覆盖率屏蔽收缩）；②为 rss_service、scan_scheduler 设计 SQLite `:memory:` 无状态单测套件，覆盖订阅状态转换、扫描重试递增、错误日志写回等边界逻辑。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

（明确本卡改动范围，白名单式列出。）

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

覆盖率排除配置缩减后单测全绿；后端核心模块实际行覆盖率≥80%。

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：
编译：
lint：
范围：false

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-19

### 实现说明

1. tarpaulin 配置收窄（.tarpaulin.toml）：crawler 全目录排除收窄为仅排除 scheduler.rs/builtin.rs；trait.rs/registry.rs/mod.rs 纳入统计。
2. rss_service 单测补齐（service/rss/service.rs）：新增 mark_unread 往返、with_websub_callback 构造、边界测试等共 4 个。
3. websub_service 单测补齐（service/rss/websub.rs）：新增 handle_notification 边界、detect_websub_links 引号边界共 8 个。
4. scan_scheduler 单测补齐（service/scan_scheduler.rs）：新增 builder、跳过逻辑、状态转换、persist_scan 语义等共 5 个。
5. clippy 修复：auth.rs manual_contains、websub.rs redundant_slicing。

### 测试结果

- cargo test -p medio-core：481 passed; 0 failed
- cargo clippy -p medio-core -- -D warnings：0 errors
- cargo tarpaulin --config .tarpaulin.toml：83.60% coverage（>=80% 门禁通过）

### push 证据

- 分支：codex/mx053-task
- commit d4f4c94：test(mx053): narrow tarpaulin exclusions + add unit tests
- commit 9748ab4：fix(clippy): resolve manual_contains and redundant_slicing lints
- 已 push 到 origin/codex/mx053-task

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：mx-plan-008 关联卡 mx053 已完成执行，方案状态待中枢同步。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：tarpaulin --lib 仅跑内联测试会显著低估覆盖率（78.59% vs 83.60%），CI 应不加 --lib。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：仅新增测试和收窄覆盖率配置，未改变项目结构。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：覆盖率除债完成，线路图无变化。

## 批注落实

无人工批注，本节留空。

## 执行提示

- 项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）

- 项目仓（只读参考）：/Users/fan/program/apps/medio-0（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要：目标：收窄 `tarpaulin` 工具对核心代码的广泛过滤，补齐 `websub_service`、`scan_scheduler`、`rss_service` 等核心后端逻辑的真实单元测试，将后端核心 core 模块真实覆盖率推升至 80% 以上。验收标准：后端 core 模块在覆盖率排除配置缩减后，单元测试执行全绿通过。 后端实际测试行覆盖率（Line Coverage）不低于 80%。

- 项目线路/近况：
  - 版本 **v0.9.0**（VERSION 文件）；35 张卡（mx001-035）全关闭，2 个方案（mx-plan-001 RSS 打磨、mx-plan-002 收口安全）已完成。
  - **2026-08-12 mx-plan-002 收口与安全加固完成**：修复 4 个 P1 安全漏洞（XSS/鉴权 fail-closed/暴力破解限制/SSRF）、Token 环境变量化、双机路径对齐、9 个积压分支清理、补打 v0.9.0 Tag、脚本审查清理（mx030-035）。
  - 三条功能分支（`library-management`/`ui-upgrade`/`rss-bugs`）已 100% 合入 main，集成风险为 0。

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::plans::mx::003-base-decoupling-and-arch-upgrade::备注] 备注 - 全部改造行为等价：现有测试基线（后端 cargo test / 前端 vitest / 冒烟）全绿为验收前提。 - 依赖 Mac2017 源码（），开发由引擎在 Mac2017 执行。 - 公开化（mx-plan-004）涉及签名私钥清洗，独立另排，不在本方案范围。

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
