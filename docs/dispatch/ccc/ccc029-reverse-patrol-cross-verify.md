# 任务卡 ccc029 · 逆向巡查与交叉验证Agent（OpenCode 执行）

> 关联：ccc-plan-011 卡7 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

实现逆向巡查 + 交叉验证：已关闭卡 → 反推方案可行性/状态推进是否合理；同一疑点由 ≥2 种巡查视角独立确认即升红旗（cross_confirm）。依据：ccc-plan-011 阶段二 2.3。

## 红线（先看）

1. **只改 `server/engine/observer.py`（逆向巡查逻辑）+ `server/tests/`**。**禁止改** registry/卡/方案/roadmap 内容；巡查只读、只产报告。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
3. 交叉验证升红旗必须有 ≥2 个独立视角证据（如治理巡查发现卡关联失配 + 逆向巡查发现方案无对应卡），单视角只到黄旗。

## 范围

- `server/engine/observer.py` 新增逆向巡查逻辑：
  - **方案可行性反推**：已关闭卡 → 检查其关联方案是否推进到「已完成」（现状 ccc-plan-010 卡已关方案仍"部分执行"——失配样本）；方案验收标准勾选 vs 关联卡关闭数。
  - **方案「已完成」但卡没全关** / **卡全关但方案没推进** 双向检测。
- **交叉验证（cross_confirm）**：设计发现对象 `acting_on`（方案编号/卡号/项目），同一 acting_on 上若治理巡查（卡6）与逆向巡查（本卡）都命中 → `cross_confirm=1.0` 升红旗，报告标注「交叉确认」。
- 产出并入卡6的风险报告（`docs/notes/YYYY-MM-DD-<prefix>-patrol.md`），或独立逆向报告，二者可互相引用。
- 补测试：构造「卡关方案没推进」「方案已完成但卡没关」样本断言触发。

## 步骤

1. 读探查 F 失配样本：ccc-plan-010（卡已关方案仍部分执行）、002/009（已完成但关联卡=无）。
2. 在 observer.py 实现逆向巡查（方案状态 vs 关联卡关闭集合比对）。
3. 实现 cross_confirm 交叉验证（复用卡6的 acting_on 发现）。
4. 补测试；本地 `--once` 跑出逆向报告，验证命中 ccc-plan-010 样本。
5. `pytest server/tests/test_observer.py` 全绿。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `--once` 跑出逆向报告，命中 ccc-plan-010 失配（卡已关闭但方案仍部分执行）。
2. 交叉验证逻辑生效：至少 1 个 `acting_on` 被治理+逆向双视角命中并升红旗（cross_confirm=1.0）。
3. 只写 `docs/notes/`，未改任何 registry/卡/方案文件。
4. `pytest server/tests/test_observer.py` 全绿。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 1. 实现说明
- 在 `server/engine/observer.py` 中实现了逆向巡查与治理巡查的双重检测核心，支持 `--once` CLI 运行并自动产出 `docs/notes/YYYY-MM-DD-ccc-patrol.md`。
- 实现了对 roadmap 业务线路段落缺失、卡头关联方案格式、已关闭卡维护区占位检测、路线图状态漂移及方案关联卡完备性/双向状态状态推进的校验。
- 实现交叉验证（cross_confirm），合并多视角下同一个 `acting_on` 的异常点升级为红旗（cross_confirm=1.0）并标注 `【交叉确认】`。
- 完成自研测试用例 `server/tests/test_observer.py` 覆盖巡查及报告生成机制。

### 2. 测试结果
- `pytest server/tests/test_observer.py` 全绿通过。
- `--once` 实测产出 400+ 条真实漂移/不一致异常，成功命中 `ccc-plan-010` 双视角失配、`ccc-plan-002`/`009` completed 但关联卡为无，以及 `hp004-006` 状态漂移并对其实施交叉验证升为红旗。

### 3. Commit Hash
- `fa61d61bcf8e8d41a8cbb4b8f001fde593e3431f`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：方案 ccc-plan-011 卡7 关联的逆向巡查已完成，卡头已同步更新为已回写。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：目前逻辑健全无特殊需要沉淀的架构级新教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：新增的 `observer.py` 及测试文件均符合已有 `server/` 项目 standard 架构。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：无变化，按 ccc-plan-011 路线稳步前进。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 机审区

**机审：通过**（2017 机审席 · 2026-08-09）

**审查摘要**：
- 范围核对：改动仅限 `server/engine/observer.py` + `server/tests/test_observer.py` + 卡文件 + 产出 `docs/notes/2026-08-09-ccc-patrol.md`；未触碰 registry/卡内容/方案/roadmap 数据。
- 目标达成：逆向巡查（方案已完成无关联卡 / 卡关方案未推进 / 已完成但卡未关）与 cross_confirm（同一 acting_on 治理+逆向双视角命中 → RED + cross_confirm=1.0 + 【交叉确认】）均已实现；`--once` 实测 15 处 RED 交叉确认，命中目标样本 `ccc-plan-010`。
- 逻辑验证（机审自跑，非引擎代判）：`pytest server/tests/test_observer.py` → 2 passed；`python -m server.engine.observer --once` → 400 异常、ccc-plan-010 双视角命中。
- 维护区四问：已逐项勾选并填实质说明，符合完成钩子。
- 可修问题（已就地修复）：断言6报告文案「未回答 of」→「未作答」，消除英文残留口误；测试复跑仍绿。
- 边界记录（不阻塞）：交叉验证按「同一 acting_on 实体 + gov/rev 双 type 命中」判定，与验收标准2措辞一致，但会把同一实体上不同疑点的命中整体标红，属「同一疑点」粒度的后续可收紧项；assertion 1/7 的 evidence 定位略粗略，不影响检测正确性。

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
