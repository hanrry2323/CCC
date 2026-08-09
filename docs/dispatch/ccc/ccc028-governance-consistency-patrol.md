# 任务卡 ccc028 · 治理一致性巡查Agent：三层断链自动发现（OpenCode 执行）

> 关联：ccc-plan-011 卡6 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

实现治理一致性巡查 Agent（挂在卡5的 observer 框架内）：对线路图↔计划↔看板三层做机器可读断言比对，发现漂移/失配，产出带红旗/黄旗/蓝旗分级的风险报告落 `docs/notes/`。依据：ccc-plan-011 阶段二 2.2 + 探查 F 真实失配样本。

## 红线（先看）

1. **只改 `server/engine/observer.py`（巡查逻辑）+ `server/tests/`**。**禁止改** registry/卡/方案/roadmap 内容本身；巡查只读、只产报告，绝不改数据。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
3. 存量问题（189 张缺维护区等）不一次性全标红旗——按「新卡先跑稳、存量定裁决口径」分批，先出统计黄旗。

## 范围

- `server/engine/observer.py` 新增巡查断言（复用 `server/board/registry.py:145 load_projects()` / `loader.py:200 load_dispatch_cards()` / `plans.py:114 list_plans()`）：
  1. 每个 taskable 项目 roadmap.md 有「业务线路（<prefix>）」段（现缺 qb/cd/clw）
  2. 卡头「关联」字段是方案编号（非「阶段 3 P1」/INT/描述）
  3. 方案「已完成」→ 关联卡全「已关闭」
  4. 方案「关联卡」字段引用的卡存在
  5. roadmap 段落卡状态 = 看板真实卡状态（hp004-006 漂移样本）
  6. 已关闭卡缺维护区四问（统计黄旗）
- 产出 `docs/notes/YYYY-MM-DD-<prefix>-patrol.md`：每发现带 severity（红/黄/蓝）+ `acting_on` 对象 + 证据（文件:行号）。
- 断言 2/5 因「关联字段自由文本」需 LLM 判定，首版做「机器可判子集」（段存在性/方案已完成但卡未关/关联卡引用不存在卡），LLM 语义判定留待卡7交叉验证。

## 步骤

1. 读探查 F 报告的失配样本（hp004-006 段落过时、60+ 卡引用不存在方案等），作为断言 ground truth。
2. 在 observer.py 实现 6 条断言中「机器可判」的子集（1/3/4/6 可纯 parse；2/5 需语义，首版标记待 LLM）。
3. 产出风险报告写入 `docs/notes/`（只写报告，不动数据）。
4. 补测试：构造小样本（缺段项目/方案卡失配/段落过时）断言触发。
5. `pytest server/tests/test_observer.py` 全绿；本地 `--once` 跑出真实报告，对照探查 F 样本验证 ≥5 条命中。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 本地 `--once` 跑出 `docs/notes/2026-08-09-ccc-patrol.md`（或当日），命中 ≥5 条真实漂移（对照探查 F：qb/cd/clw 缺段、hp004-006 段落过时、60+ 卡引用不存在方案）。
2. 报告每条含 severity + acting_on + 证据（文件:行号）。
3. 只写 `docs/notes/`，未改任何 registry/卡/方案/roadmap 文件。
4. `pytest server/tests/test_observer.py` 全绿。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是/否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：
2. **教训沉淀**：本卡是否产出可复用教训？[有/无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是/否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：
4. **线路图**：项目近况/下一步是否变化？[是/否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

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
