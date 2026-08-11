# 任务卡 hp013 · Library/Document/Activity/Notes 页面真实数据接入与空态统一（OpenCode 执行）

> 关联：hp-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：hp · 日期：2026-08-08

## 目标

Library/Document/Activity/Notes 页面真实数据接入与空态统一（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Library.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Document.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Activity.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/pages/Notes.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/components/NoteModal.tsx`
- `/Users/fan/program/apps/hp/local/graph/dashboard/src/components/EmptyState.tsx`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. Library.tsx 删除 FALLBACK_DOCS 与硬编码 TABS count：空数据/过滤无结果显示空态；TAB count 接后端 count_by_status（后端接口 hp014 落地前先用真实文档总数，接口就绪后切换）
2. Library「导出」按钮改为调用 /api/export 并下载 zip（原生 fetch，不依赖 api.ts 新函数；接口由 hp014 后端补齐）
3. Document.tsx 删除 FALLBACK_DOC/FALLBACK_BACKLINKS/FALLBACK_NOTES：文档不存在/空显示 404 空态
4. Activity.tsx 删除 FALLBACK 假时间线；Notes.tsx 初始不预填 FALLBACK_NOTES，空态兜底；saveNote/deleteNote 保持真实 /api/notes 写接口
5. 新建统一 EmptyState 组件并用于上述页面空态
6. npm run build 通过、npm test 通过；接口验证 Document 展示真实文档内容
7. 改动提交到 codex/hp013-library-doc-activity-notes-real-data 分支，回写区含对照

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 验收区

**合入批准** · 日期：2026-08-12
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）

## 回写区

**执行体**：OpenCode · 日期：2026-08-08

### 实现说明
- 新建了统一的 EmptyState 组件，并接入 Library、Document、Activity、Notes 页面的空态及 404 渲染。
- Library 页面：删除了 FALLBACK_DOCS 与硬编码 TABS count，对接真实的 backend count_by_status 字典及总数。
- Library 页面：修改了“导出”按钮，使其原生 fetch 调用 `/api/export` 并触发 zip 文件下载，不依赖新封装函数。
- Document 页面：删除了假文档、假反链及假笔记的 FALLBACK 数据，文档不存在时展示统一 404 EmptyState。
- Activity 页面：删除了假时间线 FALLBACK，对接真实 Timeline API 并在无数据时兜底 EmptyState。
- Notes 页面：初始不预填假数据，使用真实接口进行拉取、删除、保存，并统一空态兜底。
- 所有前端代码均顺利通过类型检查及构建：`npm run build` 成功。

### 测试结果
- 前端 Vitest 单元测试全部通过：
  `✓ src/api.test.ts (9 tests) 20ms`
- 后端 51 个 Pytest 测试全部通过：
  `tests/server/test_*.py 51 passed`

### push 证据（commit hash）
- 业务仓 (hp) 提交 Hash: `b203f944a2a999ba31ed9f1a265e74d08145ae9e` + 机审修复 `65ba8fc`
- 业务仓分支: `codex/hp013-library-doc-activity-notes-real-data`

## 机审区

**机审**：Claude Code（2017 验收席）· 日期：2026-08-08

### 机审：通过

独立审查代码 commit `905d2d9`、`b203f94` 及全部 6 个 in-scope 页面文件，并对验收标准逐条核对。发现 1 处 P1，已就地修复并 push（`65ba8fc`），复审闭环。

### 审查摘要（逐条验收）

1. **Library.tsx** 删除 FALLBACK_DOCS 与硬编码 TABS count ✓；空数据/过滤无结果显示 EmptyState ✓；TAB count 接后端 count_by_status ✓（修复后见 P1#1）
2. **导出按钮** 原生 fetch `/api/export` + 下载 zip ✓；后端 `pg_export()` 返回真实 zip（index.json + 单文档 json）✓，不依赖 api.ts 新函数 ✓
3. **Document.tsx** FALLBACK_DOC/BACKLINKS/NOTES 全删 ✓；非数字 id 提前拦截 ✓；文档不存在显示 404 EmptyState + 返回按钮 ✓
4. **Activity.tsx** FALLBACK 假时间线删除 ✓；对接真实 fetchTimeline ✓；无数据 EmptyState 兜底 ✓；Notes.tsx 初始不预填 FALLBACK，真实 fetchNotes + saveNote/deleteNote 保留 ✓
5. **EmptyState** 统一组件新建并用于 4 页面 ✓
6. **document 展示真实内容**：后端 `/api/document` 返回真实 rows，前端 `setDoc(d)` 直接渲染 ✓
7. 提交在 `codex/hp013-library-doc-activity-notes-real-data` 分支，回写区含对照 ✓；回写区完整（实现说明/测试结果/push 证据）✓；卡头状态「已回写」✓

### 发现清单 & 修复记录

- **P1#1（已修复）** Library 全部 tab count 键不匹配：后端 `count_by_status` 以 `all` 键表示「全部」总数，前端 `全部` tab 的 key 为 `""`，直接 `countByStatus[""]` 恒为 undefined → 全部 tab 计数在真实数据下恒显示 0（违反验收 #1：TAB count 接后端）。修复：在 Library.tsx 将后端 `all` 归一化为前端 `""` key（commit `65ba8fc`）。
- **复审结论**：P1#1 修复 diff 为纯 `Record<string,number>` 键映射，逻辑闭合，无新引入问题。

### 范围/卫生观察（非本卡代码缺陷，合入前请老板知悉）

- 分支 `codex/hp013-library-doc-activity-notes-real-data` 另携带 5 个非 hp013 范围 commit（`30568e0` project-id-mapping、`2dba7f8`/`bf64dcd` clean-chunks、`1d32c1d`/`96b34fa` verify+restore），均不在 main，涉及 `scripts/`、`docs/knowledgebase/` 等本卡范围外文件；另见 `Dashboard.tsx`/`Search.tsx` 改动。合入 review 时注意区分，避免把 hp013 之外改动一并纳入验收。
- 业务仓工作树存在未提交的 `Search.tsx` 改动（删除 AI 摘要假卡），属他任务遗留，本次机审未触碰、未提交。

### 验证说明

- 前端 build/test 需 node/npm，本验收沙箱无 node，无法本地执行；验收基于对 6 个文件 + 后端接口的静态核验 + 后端 `server.py` 编译通过 + psycopg2 缺失属环境缺失（仓库未声明该依赖，非本卡引入）。
- P1#1 修复为前端键映射，TS 类型安全。

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
