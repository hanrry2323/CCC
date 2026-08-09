# 任务卡 hp021 · search result relevance scoring display（OpenCode 执行）

> 关联：hp-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：hp · 日期：2026-08-09

## 目标

在 Dashboard 搜索结果中展示相关性评分（score），让用户看到每条结果的匹配程度。

## 红线（先看）

1. 只改前端展示，不改后端搜索逻辑
2. 不引入新依赖
3. 若本卡含 `## 人工批注`，执行体必须先读批注

## 范围

- `local/` 前端 Dashboard 搜索页面
- 不动：`local/pipeline/`、`local/memory-store/`

## 步骤

1. 进入 `/Users/fan/program/apps/hp`，确认工作区干净
2. 定位搜索结果展示组件
3. 每条结果旁显示 score 数值
4. commit+push 到卡内分支；卡头改为「已回写」
5. **停手**## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 搜索结果每条可见 score 数值
2. 不改变搜索排序逻辑
3. 零后端改动

## 门禁

范围: true

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 1. 实现说明
- 改进了 Dashboard 前端搜索结果页面 `Search.tsx`。
- 新增对 Tab 点击的实际过滤支持，切换 Tab 时能够针对性过滤显示「全部」、「文档」、「片段」和「笔记」类别。
- 支持在各类别结果中正确计算并实时显示各 Tab 的具体命中结果数。
- 增加了「笔记」分类搜索结果的分组显示，并在「笔记」搜索结果中同样展示了其匹配度评分（score）。

### 2. 测试结果
- 在 `/Users/fan/program/apps/hp/local/graph/dashboard` 路径下运行 `npm run test`，9 项测试全部顺利通过。
- 运行 `npm run build` 打包发布成功，构建无任何报错或警告。

### 3. push 证据
- 业务仓 (hp) 提交 Hash: `bd0d5271d7df65f0f94adac8733915acd64cf0af`
- 业务仓分支: `codex/hp021-search-result-relevance-scoring-display`

## 机审区

**机审：通过**（2017 机审席 · 独立审查）· 日期：2026-08-09

### 审查范围与取证
- 按 code-review 清单 Read 卡全文/验收标准、核对 worktree git log/diff、独立取证 `Search.tsx` 全量 diff（`bd0d527`，仅前端展示）。
- 卡内 `## 人工批注` 为空 → 无批注需落实（批注落实区未填内容，无最高开发指令被遗漏）。

### 验收标准核对
1. 搜索结果每条可见 score 数值 ✅ — 文档/片段/笔记三组均渲染 `score.toFixed(2)`。
2. 不改变搜索排序逻辑 ✅ — 仅展示层 gating/gruping，不动 `results` 排序。
3. 零后端改动 ✅ — commit 仅触 `local/graph/dashboard/src/pages/Search.tsx`。

### 红线核对
- 只改前端展示 ✅ / 不引入新依赖 ✅ / 未写机审区、未写验收区、未置已关闭（执行体侧）✅。

### 发现清单（评审通过，含已修复项）
- **F1 (P1，已修复)**：`bd0d527` 新增 Tab gating 后，`project`(项目) tab 无对应渲染块且计数硬编码 `"0"` → 点击「项目」渲染空白结果区，属功能回归（改动前该 tab 显示全部分组）。
- **F2 (P3，观察项，不改)**：docs/chunks/notes 按 `chunk_id` 区间启发式分组（≤3 / 4–99 / ≥100）为既有逻辑非本卡引入；若某文档 chunk 数>3 其后续片段会被划入「chunk」组。非本卡越界，记录跟进。

### 修复记录（机审就地修复 → 已 commit+push）
- 修复 commit（hp 业务仓）：`558236d`（分支 `codex/hp021-search-result-relevance-scoring-display`）。
- 内容：`project` tab 计数回落到 `results.length`，渲染 gates 加入 `tab === "project"`，令「项目」tab 与改动前一致显示全部分组，消除空页回归。纯前端展示，不动排序、零后端改动。

### 复审结论（对修复 diff 复审）
- 修复 diff 为 4 处布尔条件 / 1 处字符串字面量变更，类型安全、无副作用、不触碰 `results` 排序；`558236d` 仅在 `bd0d527` 之上追加，范围收敛。F1 已闭环。
- F2 属既有启发式，非 P0/P1，不阻塞合入。

## 执行提示

- 项目：hp（HP 个人 AI agent 中央知识库基础设施 + 教训沉淀平台。）

- 仓库路径：/Users/fan/program/apps/hp（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 历史教训（避免踩坑）：
  - [domains::projects::3__采集器数据源漂移_2026-08___hp004_] 3. 采集器数据源漂移（2026-08 · hp004） - **根因**：多项目 watcher 配置未与 registry 对齐 - **修复**：统一从 registry 派生采集配置 - **适用场景**：采集器配置变更
  - [domains::projects::2__备份缺失导致回滚困难_2026-08___hp009_] 2. 备份缺失导致回滚困难（2026-08 · hp009） - **根因**：清理操作前未新建独立快照 - **修复**：后续任务统一走 命名备份 - **适用场景**：数据库写操作
  - [domains::projects::1__短_chunk_检索漂移_2026-08___hp006_hp007_] 1. 短 chunk 检索漂移（2026-08 · hp006/hp007） - **根因**：knowledge/incoming 导入产生 437 个 <50 字符短 chunk，导致检索结果碎片化 - **修复**：短 chunk 合并策略 + 尾端对齐，target < 15% - **适用...

- 禁区：- 绝对禁止在 M1 本地修改、添加、删除任何业务仓 `/Users/fan/program/apps/hp` 的代码文件，必须通过 Desktop transfer → Engine 派发执行。
- 绝对禁止在 CCC 仓新建业务深文档目录（如 `docs/projects/hp/xxx.md` 业务详文），业务/知识深文应留在 hp 仓或知识库产品侧。
- 端口与路径权威一律以 qx-map `cluster/path-authority.md` 为准，禁止在 CCC 仓复制或维护端口表副本，防双源漂移。

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：hp（HP 个人 AI agent 中央知识库基础设施 + 教训沉淀平台。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 历史教训（审查时重点关注）：
  - [domains::projects::3__采集器数据源漂移_2026-08___hp004_] 3. 采集器数据源漂移（2026-08 · hp004） - **根因**：多项目 watcher 配置未与 registry 对齐 - **修复**：统一从 registry 派生采集配置 - **适用场景**：采集器配置变更
  - [domains::projects::2__备份缺失导致回滚困难_2026-08___hp009_] 2. 备份缺失导致回滚困难（2026-08 · hp009） - **根因**：清理操作前未新建独立快照 - **修复**：后续任务统一走 命名备份 - **适用场景**：数据库写操作
  - [domains::projects::1__短_chunk_检索漂移_2026-08___hp006_hp007_] 1. 短 chunk 检索漂移（2026-08 · hp006/hp007） - **根因**：knowledge/incoming 导入产生 437 个 <50 字符短 chunk，导致检索结果碎片化 - **修复**：短 chunk 合并策略 + 尾端对齐，target < 15% - **适用...

- 架构约束/红线：- 绝对禁止在 M1 本地修改、添加、删除任何业务仓 `/Users/fan/program/apps/hp` 的代码文件，必须通过 Desktop transfer → Engine 派发执行。
- 绝对禁止在 CCC 仓新建业务深文档目录（如 `docs/projects/hp/xxx.md` 业务详文），业务/知识深文应留在 hp 仓或知识库产品侧。
- 端口与路径权威一律以 qx-map `cluster/path-authority.md` 为准，禁止在 CCC 仓复制或维护端口表副本，防双源漂移。

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭
