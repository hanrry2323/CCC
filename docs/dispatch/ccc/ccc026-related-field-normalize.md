# 任务卡 ccc026 · 存量卡关联字段治理：方案编号规范化（OpenCode 执行）

> 关联：ccc-plan-011 卡4 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

治理存量任务卡的「关联」字段失配：将 194 张卡中仅 3.6%（7 张）用真方案编号的现状提升到规范化——「阶段 3 P1」占位与「ccc-plan: 描述」无实体引用补真方案编号；hp/mx 空方案池补首方案，使卡↔方案双向追踪可机器 parse。依据：ccc-plan-011 阶段一 1.4 + 探查 F 红旗 #1。

## 红线（先看）

1. **只改 `docs/dispatch/<prefix>/<prefix>NNN-*.md` 卡头「关联」字段 + `docs/projects/<prefix>/plans/` 方案文件**。**禁止改** registry.yaml、服务端代码、validate.py 校验逻辑、已关闭卡的正文实现。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
3. 只改「关联」字段的**指向格式**，不改卡状态/执行体/验收/日期；不重写卡正文内容。改动每张卡须保持 validate 通过。

## 范围

- **补方案编号**：55 张「阶段 3 P1」占位 + 60 张「ccc-plan: 描述」卡（hp/mx/xy 为主）→ 关联字段改为真实方案编号 `ccc-plan-NNN`/`hp-plan-NNN`/`mx-plan-NNN`/`xy-plan-NNN`。
- **补方案实体**：hp/mx 的 `plans/` 空目录 → 各补 1 个里程碑方案（参考 ccc-plan-011 模板，含目标/验收标准/转卡计划，状态草案）；将 60 张「描述方案」卡按描述归类挂到对应方案。
- **方案「关联卡」回填**：被关联方案的头部 `> 关联卡：` 字段补全实际关联卡号（逗号分隔）。
- **产出映射表**：`docs/notes/2026-08-09-related-mapping.md` 记录每张卡的旧→新关联对照（可审计）。

## 步骤

1. 读 `docs/projects/ccc/plans/011-loop-observer-architecture.md` §阶段一 + 探查 F 的关联字段统计表，明确需治理卡清单。
2. 先为 hp/mx 补方案实体（模板 `docs/projects/_template/plan-template.md`），确认编号规则（`<prefix>-plan-001`）。
3. 逐项目批量更新卡头「关联」字段（脚本或手改均可，须保留 validate 通过）；每改一批跑一次 `python -m server.board.validate docs/dispatch`。
4. 回填各方案头部「关联卡」字段。
5. 写 `docs/notes/2026-08-09-related-mapping.md` 映射表。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 抽查 20 张原「阶段 3 P1」/「ccc-plan: 描述」卡（hp/mx/xy 各 ≥5），「关联」字段已改为真实方案编号，且对应方案文件存在。
2. hp/mx 各 ≥1 个方案文件落地（`docs/projects/hp/plans/001-*.md`、`docs/projects/mx/plans/001-*.md`）。
3. 被关联方案头部「关联卡」含实际卡号（抽查 ≥3 方案）。
4. `python -m server.board.validate docs/dispatch` 全绿。
5. 映射表 `docs/notes/2026-08-09-related-mapping.md` 存在，覆盖 ≥40 张卡。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. **补方案编号**：对 134 张包含描述性「关联」字段或「阶段 3 P1」占位的历史任务卡进行了批量治理，一律映射替换为真实的、可在 `docs/projects/<prefix>/plans/` 下被机器追踪解析的方案编号（`ccc-plan-NNN`、`hp-plan-001`、`mx-plan-001`、`xy-plan-001` 等）。
2. **补方案实体**：
   - 补全 `hp` 空方案目录：新建首个里程碑方案 `docs/projects/hp/plans/001-knowledge-base-milestone.md`（ID: `hp-plan-001`），含 4 个步骤和 20 个关联卡列表。
   - 补全 `mx` 空方案目录：新建首个里程碑方案 `docs/projects/mx/plans/001-rss-polish-milestone.md`（ID: `mx-plan-001`），含 5 个步骤和 29 个关联卡列表。
3. **方案「关联卡」回填**：两份新方案文件的头部 `关联卡` 字段已精确填入所有关联卡 ID。
4. **产出映射表**：生成审计凭证 `docs/notes/2026-08-09-related-mapping.md` 对照表，记录 134 张卡片的旧值->新方案编号映射，覆盖远超标准 40 张的要求。

### 测试结果
运行 `python3 -m server.board.validate docs/dispatch` 成功，204 张卡片校验通过（无 errors）。

### Push 证据
Commit Hash: `73f0198c` (分支：`codex/ccc026-related-field-normalize`)

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：已新建 `hp-plan-001` 与 `mx-plan-001` 方案文件，并在头部填入了完整的关联卡。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：纯净的任务卡关联关系字段治理，无额外逻辑与架构设计引入。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：未改变项目结构或技术栈。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：无变化。

## 批注落实

（无批注。）

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 前端依赖： - 前端 lint：（oxlint） - 前端构建：（tsc -b && vite build） - Rust 编译检查： - Rust 发布构建： - 开发启动：（仓根，先 npm install） - 出卡： - 看板：CCC 项目=clw

- 禁区：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。
