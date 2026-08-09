# 任务卡 ccc030 · 巡查权重打分与转卡接线（OpenCode 执行）

> 关联：ccc-plan-011 卡8 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

实现巡查风险权重打分机制 + 转卡接线：每条风险发现按 `weight = cross_confirm × impact × frequency` 打分，看板/报告可按权重排序，高权重发现优先转卡（走 new-card.sh 既有出卡链）。依据：ccc-plan-011 阶段三 3.1。

## 红线（先看）

1. **只改 `server/engine/observer.py`（打分逻辑）+ 出卡接线（不碰 new-card.sh 本体，只在报告里给建议命令）+ `server/tests/`**。**禁止改** new-card.sh / registry / validate.py。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
3. **打分只排优先级、不自动出卡**：转卡必须走 `scripts/new-card.sh --related "patrol: <报告名>"` 且经既有审批链；巡查 Agent 绝无自动出卡/自动合入权。

## 范围

- `server/engine/observer.py` 新增权重打分：
  ```
  weight = cross_confirm × impact × frequency
  cross_confirm 0~1：多视角独立发现则加权（卡7交叉验证产出）
  impact 1~5：影响项目数/卡数/模块/用户路径
  frequency 1~5：每天/每周/偶发/一次性
  ```
- 风险报告头带 weight 字段 + 排序（高权重优先）；报告末节输出「建议转卡命令」（`scripts/new-card.sh --project <prefix> --title "修复：<发现>" --related "patrol: <报告名>"`，仅打印不执行）。
- 打分规则可配置（impact/frequency 由巡查 LLM 判定或规则表，首版用规则表：断链类 impact≥4、段落漂移 impact=2 等）。
- 补测试：构造已知 weight 样本断言计算与排序正确。

## 步骤

1. 读 ccc-plan-011 §3.1 权重公式与探查 F 的红旗分级建议。
2. 在 observer.py 实现权重打分 + 报告排序 + 建议转卡命令输出。
3. 补测试（weight 计算/排序/建议命令格式）。
4. 本地 `--once` 跑出带权重的报告，验证高权重发现（三层断链类）排序靠前。
5. `pytest server/tests/test_observer.py` 全绿。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 风险报告每条含 weight 值，按 weight 降序排列。
2. 报告末「建议转卡命令」输出合法 `new-card.sh` 命令（含 --project/--title/--related）。
3. 高权重发现（断链/失配类，impact≥4）排序靠前。
4. `pytest server/tests/test_observer.py` 全绿；无任何自动出卡行为（报告只打印命令不执行）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. 实现了权重打分机制：新增了 `DEFAULT_SCORING_RULES` 默认规则配置表，支持通过 `OBSERVER_SCORING_RULES` 进行自定义规则注入。每条风险发现按照 `weight = cross_confirm × impact × frequency` 进行打分，并打上红/黄/蓝旗的 severity。
2. 一致性扫描与自动诊断：
   - 检查每个 taskable 项目在 roadmap.md 中是否有业务线路段落；
   - 检查已关闭卡在 roadmap.md 和卡文件中的状态漂移与不一致；
   - 检查已完成方案所关联卡是否全关闭；
   - 检查已完成方案中关联引用的卡是否存在；
   - 检查已关闭卡是否缺失或未填写维护区四问（说明为空或包含模板占位）。
3. 风险报告自动生成：每天或触发运行时生成 `docs/notes/YYYY-MM-DD-ccc-patrol.md` Markdown 报告，自动按权重降序排列，并在报告末尾针对风险，输出对应的 `scripts/new-card.sh` 转卡建议命令。

### 测试结果
1. 在 `server/tests/test_observer.py` 中补充了 `test_weight_scoring_and_report_ordering` 测试用例，对打分公式、权重计算、降序排列以及 new-card 命令输出进行全方位覆盖。
2. 运行 `python3 -m pytest server/tests/test_observer.py` 结果全绿。
3. 通过 `python3 -m server.engine.scheduler --config test_config.env --once` 本地跑通单次巡查流程，产出带权重的巡查报告 `docs/notes/2026-08-09-ccc-patrol.md`。

### Push 证据
- Commit Hash: ea4f1a9b8c715997b4877e10cd51a0c29bf05e2c

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：ccc-plan-011 方案的阶段三（3.1 权重公式与打分）已经随着本卡的开发得以部分落实。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：无
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：未改变项目结构/技术栈/路径，不影响 `docs/projects/ccc/README.md`。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：项目近况和下一步依然严格遵循 ccc-plan-011 的既定路线运行，没有新增和变更方向。

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
