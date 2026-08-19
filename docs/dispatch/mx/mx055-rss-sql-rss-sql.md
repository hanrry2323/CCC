# 任务卡 mx055 · RSS 统计接口后端 SQL 聚合优化 — RSS 统计接口 SQL 聚合优化（OpenCode 执行）
> 批准：老板确认转卡 · 2026-08-19

> 关联：mx-plan-007 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：mx · 日期：2026-08-19




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/`（关联方案见卡头「关联」）

## 目标

消除前端拉 1000 条全量数据计算统计的卡顿，改后端 COUNT(*) 聚合返回数值。

## 实现

①后端 `api/routes/rss.rs` 新增 `GET /api/v1/rss/stats`，SQL `SELECT COUNT(*) ... WHERE unread=?` 组装 `{unread_count, starred_count}` 轻量 JSON；②前端 `RssStatsPage.tsx` 废弃 `rssApi.items({perPage:1000})` 全量拉取+filter，改请求新接口秒级渲染。

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

新接口数据准确不受阈值截断；前端统计页带宽<1KB；后端编译+前端打包测试全绿。

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

核心实现在 mx012（commit `f2bc5f9` "feat(rss): replace client-side aggregation with backend stats API"）已完成：
- 后端 `api/routes/rss.rs` 已有 `GET /api/v1/rss/stats`（`get_rss_stats`），使用 8 条 `COUNT(*)` SQL 聚合查询返回 `RssStatsResponse`（含 unread_items / starred_items / read_items 等）。
- 前端 `RssStatsPage.tsx` 已调用 `rssApi.stats()` 请求 `/rss/stats`，不拉取全量数据。
- 全仓搜索确认无 `perPage: 1000` 或全量拉取残留。

本卡补齐了缺失的测试覆盖：
1. **前端测试**（`client-pure.test.ts`）：验证 `rssApi.stats()` 调用 `/rss/stats` 并将 snake_case 响应正确映射为 camelCase。
2. **后端集成测试**（`tests/rss_stats.rs`，3 个用例）：
   - `stats_count_queries_are_accurate` — 5 条种子数据验证 unread/read/starred 计数准确。
   - `stats_count_no_threshold_truncation` — 1500 条数据验证 COUNT(*) 不受阈值截断。
   - `stats_top_subscriptions_aggregation` — JOIN + GROUP BY 聚合验证。

### 测试结果

| 检查项 | 结果 |
|--------|------|
| `cargo check` | 通过 |
| `cargo test --test rss_stats` | 3/3 通过 |
| `npx vitest run client-pure.test.ts` | 98/98 通过 |
| `npm run build`（tsc + vite） | 通过 |
| `eslint`（--max-warnings 0） | 0 警告 |

### Push 证据

- 业务仓分支：`codex/mx055-rss-sql-rss-sql`
- Commit：`c6c7a95`
- Remote：已 push 到 `origin/codex/mx055-rss-sql-rss-sql`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：mx-plan-007 状态更新为「已完成」，进度 1/1 (100%)，验收标准三项全勾选。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：mx012 实现了后端 COUNT(*) 聚合端点但未配套测试覆盖。本卡补齐了 stats 端点的前后端测试缺口——新功能交付时应同步交付集成测试。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：仅新增测试文件（tests/rss_stats.rs + client-pure.test.ts 测试用例），未改变项目结构/技术栈/路径。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：本卡为测试补强，不改变项目线路图或近况。

## 执行提示

- 项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）

- 项目仓（只读参考）：/Users/fan/program/apps/medio-0（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要：目标：解决 `RssStatsPage.tsx` 获取未读/已读统计时因全量拉取 1000 条数据导致的严重网络带宽与内存计算性能瓶颈，重构为由后端执行高性能 `COUNT(*)` SQL 并直接返回数值。验收标准：新统计接口可用，数据实时准确，不受全量拉取阈值截断。 前端载入统计页面不再拉取 1000 条全量数据，耗用带宽降低至 1KB 以下，彻底告别卡顿。 后端编译与前端编译打包、测试全绿。

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
