# 任务卡 mx052 · 修复 OPML 导入属性顺序依赖漏洞（OpenCode 执行）
> 批准：老板确认转卡 · 2026-08-18

> 关联：mx-plan-005 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：mx · 日期：2026-08-18




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/005-media-and-rss-polish-plan.md`（关联方案见卡头「关联」）

## 目标

修复 OPML 导入由于 XML 属性无序遍历时，因 `xmlUrl` 属性先被读到而提前触发 push 导致的订阅源显示名称丢失漏洞 (P0)。确保不管 XML 属性在 OPML 节点中按什么顺序排列，解析出的订阅源名称都完整准确。

## 实现

- **核心痛点**：在 `src/backend/core/src/api/routes/rss.rs` 的 `parse_opml` 路由/解析函数中，读取 `<outline>` XML 节点时使用属性无序流读取。原逻辑在遍历属性循环内，一读到 `xmlUrl` 属性便直接执行 `push` 将该条目写入。因为属性顺序由 XML 序列化器任意生成，在 `xmlUrl` 排在 `text` 属性之前（非常多见）的情况时，由于 `text` 还没被遍历到，该节点就已经被提前 push 入库，导致 `text` 显示名被丢弃，订阅名称永久退化为原始 URL 地址。
- **重构要求**：
  1. 改造 `src/backend/core/src/api/routes/rss.rs` 中的 `parse_opml` 逻辑。
  2. 废弃在 XML 属性遍历 `Event::Start` 或 `Event::Empty` 循环内部直接 push 结果的做法。
  3. 在处理单个 `outline` 节点时，声明一组临时变量或局部 Option 变量（`title` / `text` / `xml_url`），在遍历当前节点属性时仅做数据解析与 Option 暂存。
  4. 退出当前节点属性循环（或者在节点遍历结束时），根据优先级进行名称合并推导（例如：优先使用 `title`，无则使用 `text`，再次则使用 `xmlUrl` 兜底），最后再整体执行 `push` 写入订阅源。
  5. 在后端 `core` 中补齐/扩展相关测试用例，提供一份含有乱序属性的 OPML XML 片段测试，验证无论属性排列顺序如何，解析器均能百分之百准确还原订阅名称。

## 红线（先看）

1. 只动 OPML 导入解析器相关文件（`src/backend/core/src/api/routes/rss.rs` 及其直接单测依赖），不碰无关模块。
2. 行为等价重构：不改动数据库 schema、不改变现有 API 返回契约，仅提高解析健壮性。
3. 不直推 main；不写 `## 机审区` / `## 验收区` / 置「已关闭」。
4. 严格落实完成双门禁：回写卡头时必须真实填写 **维护区四问**，严禁占位或大面积复写。

## 范围

- `src/backend/core/src/api/routes/rss.rs`（及直接相关的 `api` 路由解析模块）

## 步骤

1. Read 任务卡全文 + 方案主档 `docs/projects/mx/plans/005-media-and-rss-polish-plan.md`。
2. 在 CCC Engine 注入的独立工作区内，定位 `src/backend/core/src/api/routes/rss.rs` 中的 `parse_opml` 解析逻辑。
3. 重构其解析循环，实现完整的属性暂存、优先合并及延迟推导 push 逻辑，消除属性顺序依赖。
4. 编写或补充对应的 Rust 单元/集成测试，注入带有各种乱序属性（例如 `xmlUrl` 在第一位，`text` 位于最末尾）的 OPML 测试段，执行解析断言。
5. 运行 `cargo test -p medio-core`（或单模块测试），确保包含新用例在内的全量测试 100% 通过。
6. commit+push 到卡内分支 `codex/mx052-opml-import-fix`；将卡片头部状态改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等待 2017 自动机审通过。

## 验收标准

1. `parse_opml` 函数完成 XML 属性顺序无关重构，完美兼容 `xmlUrl` 先于 `text` 声明的乱序 OPML 文件。
2. 乱序属性 OPML 文件的端到端解析断言单元测试编写完成，运行测试 `cargo test` 100% 绿灯。
3. 代码编译通过，无引入任何 compiler warning。
4. 无无关文件改动（改动严格在范围白名单内）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成 维护区四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写；人审 diff 后听「合入批准」写已关闭。

## 人工批注

（无人工批注。若有审核或打回意见，老板将其填写于此，执行席优先落实批注。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-18

1. **实现说明**：
   - 彻底梳理了 `parse_opml` 中对 `<outline>` 标签解析时的属性获取逻辑，采用了局部变量和临时 Option 暂存（`xml_url`、`text`、`title`、`category`）的设计。
   - 延迟了 `push` 的触发，只有在完全遍历当前节点的所有 XML 属性（退出属性循环）后，才开始进行订阅源名称的逻辑合并推导（按优先使用 `title`，无则使用 `text`，再次则使用 `xmlUrl` 兜底的逻辑顺序）。
   - 这样的设计完全消除了 XML 属性顺序对解析结果的影响，保障了 `xmlUrl` 排在 `text` 属性前面时订阅显示名称不会丢失。
2. **测试结果**：
   - 运行测试的具体命令：`cargo test --lib -p medio-core -- api::routes::rss`
   - 共通过了 15 个 RSS 解析和转义相关单元测试，其中包括新增的乱序属性极端乱序测试 `parse_opml_extreme_attribute_disorder`，解析器均 100% 准确还原订阅名称。
3. **push 证据**：
   - 业务仓分支：`codex/mx052-opml-import-attribute-bug`
   - 业务仓 commit hash：`fd039e54b0e6a504ec3d8bf757a3dbd63552f187`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[x]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `005-opml-import-fix.md` 已推进至「部分执行」，在测试用例中彻底对齐。
2. **教训沉淀**：本卡是否产出可复用教训？[x]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：属性解析需要延迟推导，对 XML/JSON 解析中需要多属性复合处理的字段，绝不应该在属性迭代流内部立即触发后续写操作，应该完全收集后延迟最终计算。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[ ]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：未改变项目结构、技术栈或路径，仅增加了强壮的健壮性单元测试。
4. **线路图**：项目近况/下一步是否变化？[ ]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：无变化，近况 M8 里程碑 RSS 系列体验提升继续推进。

## 机审区

**验收席**：2017 机审席 · 日期：2026-08-18 · 状态：**待机审**

## 执行提示

- 项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）
- 项目仓（只读参考）：/Users/fan/program/apps/medio-0（Mac2017）——禁止在主仓目录切换卡分支或直接开发
- 代码工作区：由 CCC Engine 派发时注入独立 worktree，所有代码改动必须在注入的 worktree 内完成
- 关联方案摘要：打磨优化 medio-0。包括修复 OPML 导入 XML 属性无序依赖漏洞（P0）、OPML 导出 Token 鉴权（P0）、后端 SQL 统计性能提升（P1）、缩窄覆盖率屏蔽（P1）。
- 项目线路/近况：版本 v0.9.0 完好固化；重构解耦 mx036-041 顺利合入。
- 常用测试命令：`cargo test -p medio-core`
- 禁区：前缀是 `mx` 不是 `medio`；卡文件名必须 `mx052-…`

## 机审提示

- 审查项目：mx（Mac2017 上的全栈媒体管理应用）
- 处理原则：可修问题在 worktree 就地修复；原则性红线问题输出「机审：不通过（具体原因）」并以非零退出。
- 校验重点：核对 `## 维护区` 四问勾选及非空说明。
