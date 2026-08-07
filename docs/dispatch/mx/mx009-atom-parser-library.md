# 任务卡 mx009 · Atom 解析器换标准库（OpenCode 执行）

> 关联：ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

修复 mx008 巡检 P0-1：`builtin.rs` 的 `extract_atom_entries` 从裸字符串 `split`/`find` 手工解析替换为成熟 XML/Atom 库的结构化解析，解决 CDATA、命名空间、不标准格式下的解析遗漏/截断/错误；输出字段语义与旧实现兼容。

## 红线（先看）

1. **解析语义兼容**：新实现输出的标题/链接/更新时间等字段语义必须与旧实现一致（前端行为零破坏）；纯解析重构，禁止顺手改其他 RSS 逻辑（爬虫/调度/存储）。
2. 只动白名单（RSS 解析相关文件、Cargo.toml 依赖、测试）；**禁止**改数据库表结构、前端代码、其他业务模块。
3. 依赖选择注意：若选 quick-xml 0.41+，其 API 有 breaking changes，须完整适配编译；优先评估 `atom-syndication` 等专门库；禁止装包以外的依赖引入。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/backend/core/src/` 下 RSS 解析相关文件（builtin.rs 及 rss 模块）
- `Cargo.toml` / `Cargo.lock`（仅新增解析依赖）
- 新增/更新 Rust 测试文件（解析用例）

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读 `src/backend/core/src/` 下 `extract_atom_entries` 现状（定位裸 split/find 逻辑与输出字段）。
2. 选型：优先 `atom-syndication`；若用 quick-xml 须适配 breaking changes。`Cargo.toml` 增加依赖，`cargo check` 确认可编译。
3. 重写 `extract_atom_entries`：结构化解析 title/link/updated/id 等字段；正确处理 CDATA、命名空间（Atom 标准 ns 与自定义 ns）、换行/属性顺序变体；输出字段语义与旧实现逐字段对齐。
4. 新增解析用例：CDATA 字段、带命名空间源、非标准换行/属性顺序源、空条目、多条目源；既有 RSS 相关测试全部通过；`cargo check` 通过。
5. 兼容性对比自测：构造旧实现会失败的样例源，验证新实现解析正确（回写区记录样例与结果）。
6. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. extract_atom_entries 改为结构化解析（成熟 XML/Atom 库），不再裸字符串 split/find；CDATA、命名空间、换行/属性顺序变体源能正确解析
2. 新增解析用例（CDATA/命名空间/非标准格式）与既有测试全部通过；cargo check 通过
3. 输出字段语义与旧实现兼容（标题/链接/时间等），前端行为无破坏；只动白名单；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
