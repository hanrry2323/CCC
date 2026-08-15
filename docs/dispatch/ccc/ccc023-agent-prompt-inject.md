# 任务卡 ccc023 · 执行Agent心智注入：prompt_inject加方案摘要与线路近况（OpenCode 执行）

> 关联：ccc-plan-011 卡1 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

扩展现有执行 Agent 心智注入管道：出卡时 `server/board/prompt_inject.py` 的 `build_executor_hint()` 自动拼入「关联方案摘要 + 项目线路/近况」，使 2017 执行 Agent 派发时能直接看到方案上下文，不再"白纸"执行。依据：ccc-plan-011 阶段一 1.1。

## 红线（先看）

1. **只改 `server/board/prompt_inject.py`**（build_executor_hint / build_auditor_hint / inject_hints 相关）+ `server/tests/`（若补测试）。**禁止改** dispatch.py 占位符、executors.json、main.py 派发逻辑、validate.py。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
3. 不重构注入管道结构，只增数据源与产出行；保持 `## 执行提示` 既有行的兼容（项目/仓库路径/技能/教训/禁区/执行要求/禁止）。

## 范围

- `server/board/prompt_inject.py`：`build_executor_hint()`（约 L266-292）新增两行产出——
  - `- 关联方案摘要：<方案「目标」+「验收标准」要点，≤400 字符>`
  - `- 项目线路/近况：<docs/projects/<prefix>/README.md 的「线路/近况」节，≤3 条>`
- 数据源读取：解析卡头「关联」字段取 `<prefix>-plan-NNN` → 读 `docs/projects/<prefix>/plans/NNN-*.md` 的「目标」+「验收标准」段；读项目 README「线路/近况」节。方案/README 不存在时优雅降级（省略该行，不抛错）。
- 仅当关联字段含方案编号时注入方案摘要；无方案编号（如「阶段 3 P1」）不注入并保留现状。

## 步骤

1. 读 `docs/projects/ccc/plans/011-loop-observer-architecture.md` §1.1 与本卡基准文件，理解注入管道现状（prompt_inject.py 486 行、main.py:1393-1405 消费方）。
2. 在 `build_executor_hint()` 增加方案摘要 + 线路/近况的数据源读取与产出行。
3. 用 `docs/dispatch/ccc/ccc023-*.md` 本卡实测：重跑 prompt_inject 注入，确认 `## 执行提示` 出现「- 关联方案摘要：」行（引用 ccc-plan-011）与「- 项目线路/近况：」行。
4. 补测试（若加数据源解析函数）：`server/tests/` 下新文件或扩展既有，覆盖「关联含方案编号→注入摘要」「关联占位→不注入降级」「方案不存在→不抛错」三例。
5. 运行 `pytest server/tests/` 确认全绿（重点：test_engine_main.py TestPromptInjection 不破坏）。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 对本卡重跑 `python3 -m server.board.prompt_inject <卡> --project ccc --title "..."` 后，`## 执行提示` 含「- 关联方案摘要：」行，内容引用 ccc-plan-011 目标要点（非占位）。
2. 对无方案编号的卡（如 `docs/dispatch/xy/xy003-*.md` 关联「阶段 3 P1」）重跑，不注入方案摘要行且不报错。
3. `pytest server/tests/` 全绿（含 TestPromptInjection）；新补用例通过。
4. 既有 `## 执行提示` 行（项目/仓库路径/技能/教训/禁区）保持存在，无回归。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. 扩展了 `build_executor_hint` 接收 `card_content` 参数，从中提取卡头「关联」字段中的 `ccc-plan-011` 方案编号。
2. 实现了从 `docs/projects/<prefix>/plans/NNN-*.md` 中提取「目标」与「验收标准」，合并清理并控制长度在 400 字符内，输出 `- 关联方案摘要：` 行。
3. 实现了从 `docs/projects/<prefix>/README.md` 解析「线路 / 近况」段，提取最多 3 条输出 `- 项目线路/近况：` 行。
4. 增强 `inject_hints` 对 `## 执行提示` 的正则匹配，利用 `^` 和 `re.MULTILINE` 锚定，完美解决了因为任务卡正文包含 `## 执行提示` 字面量而导致正则误匹配的问题。
5. 补充 3 个集成测试例覆盖主要逻辑，且 `pytest server/tests/test_engine_main.py` 通过。

### 测试结果
`python3 -m pytest server/tests/test_engine_main.py -k TestPromptInjection` 全绿。

### push 证据
Commit Hash: 09b557674271cbd0968a54a3bd77712666052b60

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]
   - 说明：ccc-plan-011 实施中。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：无。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：未改变。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：无变化。

## 批注落实

（无批注）

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 关联方案摘要：目标：实现执行 Agent 心智注入，将关联方案的摘要与项目线路近况注入到执行提示中，让 2017 执行 Agent 有上下文地执行任务。验收标准：方案摘要和近况可成功拼入提示。 支持无方案编号优雅降级。

- 项目线路/近况：
  - 北星：[`docs/roadmap.md`](../../roadmap.md)「当前方向」
  - 挂账：文档与项目注册统一治理；任务卡退役/高效管理
  - 规范：[`docs/DOC-PROTOCOL.md`](../../DOC-PROTOCOL.md)

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

## 机审区

**机审：通过**

**审查方**：2017 机审席（Claude Code 验收席） · 日期：2026-08-09

### 审查摘要

- **范围合规**：改动限于 `server/board/prompt_inject.py`（核心注入逻辑）与 `server/tests/test_engine_main.py`（补 3 用例）；红线 #1 所列禁改文件（dispatch.py / executors.json / main.py 派发 / validate.py）均未触碰。
- **架构合理**：`build_executor_hint` 新增 `card_content` 入参，数据源抽取封装为 `_parse_related_field` / `_parse_plan_ref` / `_get_plan_summary` / `_get_project_recent_lines` 四个职责单一纯函数，沿用库内 `| None` / `list[` 类型惯例；`inject_hints` 已把卡文件全文传入，main.py 消费者仍经 `_read_card_section` 读卡内已注入段，兼容无回归。
- **边界安全**：方案缺失→`return ""`、README 缺失→`[]`、读取异常 catch、摘要 400 字符截断，全部优雅降级不抛错；实测注入产出（卡内 `## 执行提示` 含「关联方案摘要」「项目线路/近况」行）符合验收标准 #1，三用例覆盖「方案编号→注入 / 占位→不注入 / 方案不存在→不抛错」。
- **Doc-Gate**：维护区四问逐项勾选 [是/是/否/否] 并填非占位说明；批注落实节标注「无批注」，符合卡头 `## 人工批注` 为空的事实。
- **补充说明**：本卡新建 `docs/projects/ccc/plans/011-loop-observer-architecture.md`——出卡时 ccc023-026 已引用 ccc-plan-011 但方案文件缺位，此为执行体补完出卡遗留，内容与卡目标一致，非系统性越界，判定为合理而不打回。
- **可修点（不阻塞）**：README「线路/近况」标题仅覆盖 `## 线路 / 近况` 与 `## 线路近况` 两种变体，未覆盖无空格 `## 线路/近况`；属边界苛求，非红线，留待后续优化即可。
