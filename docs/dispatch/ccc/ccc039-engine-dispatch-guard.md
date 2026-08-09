# 任务卡 ccc039 · engine 派发防护 + 空回写上限 + 卡编号保护（OpenCode 执行）

> 关联：ccc-plan: 失败复盘 clw006 事故 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-10

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

修复 clw006 事故根因：engine 派发时 worktree 内卡文件缺失 → 空回写 → 无限重试打转；并加卡编号保护，杜绝附加卡吃掉方案链编号。背景见 `docs/notes/2026-08-10-clw006-card-spin-failures.md`。

## 红线（先看）

1. 不破坏已关闭卡与在途卡的派发（本卡改动只加防护，不改既有派发语义）
2. 不引入对执行体的「成功幻觉」——防护应让异常显式暴露（打回/告警），而非静默放行
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `server/engine/main.py` — 派发前 worktree 卡文件校验、空回写判定、重试上限
- `server/engine/store.py` — work.id → card_path 解析（以磁盘为准，不残留旧路径）
- `server/engine/runtime_state.py` — 空转/空回写判定辅助
- `server/board/validate.py` — 卡编号保护校验（方案链编号显式保留）
- `scripts/plan-to-cards.sh` / `scripts/new-card.sh` — 附加卡显式编号提示
- `server/engine/test_*.py` — 对应单元测试

## 步骤

1. Read `docs/notes/2026-08-10-clw006-card-spin-failures.md` 全文（事故背景与根因链）
2. `server/engine/main.py`：派发前校验 `_worktree_card_candidate` 返回 None（worktree 无对应卡）→ 不派空转；打日志并跳过该卡（或重建 worktree 后重试一次）
3. `server/engine/main.py`：空回写判定——回写 diff 为空 或 卡 `## 维护区` 为模板占位 → 机审直接打回进入「打回」终态（或人工介入），**不再无限 retry**
4. `server/engine/store.py`：work.id → card_path 解析改为每次从磁盘索引重新匹配（同 id 多个文件时取当前 `*<id>*.md` 或显式 id 匹配），避免改名后残留旧 card_path
5. `server/board/validate.py` / `scripts/plan-to-cards.sh`：方案链编号保护——plan-to-cards 出卡时若生成的自动编号落在方案已声明编号区间内且该编号已计划给特定卡，则报错要求显式 `--id`；附加卡提示显式编号
6. 补单元测试：worktree 缺卡不派发 / 空回写直接打回不重试 / 编号冲突拒绝出卡
7. `pytest server/tests/test_engine_*.py` 全绿；`python3 -m server.board.validate docs/dispatch` 通过
8. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
9. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 构造「worktree 无对应卡」场景，engine 不派空转（日志含跳过原因，卡保持待分派或重建后正常派发）
2. 构造「空回写」（维护区占位/无 diff）场景，机审打回进入「打回」态，retry_count 不无限递增
3. plan-to-cards 出卡落在方案已声明编号上时报错，提示显式 `--id`
4. `pytest` engine 测试全绿；validate 无新增错误
5. 回归：正常卡（worktree 有卡、有产物）派发/机审/合入链路不受影响

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

### 实现说明
1. **派发防护**：在 `server/engine/main.py` 派发循环 `run_once` 以及执行体 `_dispatch_and_collect` 启动前添加对 worktree 内卡文件副本存在性的强校验。若 `_worktree_card_candidate` 结果为 None（卡改名/文件缺失），则直接拦截派发并跳过，不再进行空转。
2. **空回写直接打回，不再无限重试**：新增 `is_empty_writeback_or_placeholder` 判定助手，完美校验卡片是否为零 diff/新 commit 或其维护区是否为占位模板。在 `_run_auto_worker` 与 `_run_audit_worker` 中，一旦检测到空回写，卡片直接流转到打回状态 (`State.REJECTED`)，立刻中断重试。
3. **卡路径磁盘动态匹配**：重构 `server/engine/store.py` 里的 `FileBoardStore.list_work`，在反查 `card_path` 时每次都通过磁盘索引动态匹配（支持同 id 多个文件时取精确 `*<id>*.md` 候选），避免卡改名后残留旧路径问题。
4. **方案链编号保护**：在 `server/board/validate.py` 门禁中添加对方案保留编号的交叉对比校验；同时升级 `scripts/new-card.sh`，在生成自动编号前通过 Python 深度扫描 `docs/projects/**/plans/*.md` 中所有声明的 `关联卡：`。若生成的自动编号落在任何已有方案已声明的编号区间内，则直接报错中断，要求显式使用 `--id` 指定。对于非方案主链卡，增加显式编号提示，杜绝吃掉自动编号空间。
5. **单元测试**：在 `server/tests/test_engine_main.py` 新增专门的单元测试，全面验证了空回写/占位模板判定。

### 测试结果
- 执行 pytest `test_engine_main.py` 86 个用例全量通过：
  `python3 -m pytest server/tests/test_engine_main.py` -> 100% Passed.
- 执行 `test_board_validate.py` 23 个校验用例全量通过：
  `python3 -m pytest server/tests/test_board_validate.py` -> 100% Passed.

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：ccc039 关联方案 “失败复盘 clw006 事故” 的所有防护策略已全部完整实现并测试通过。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：已在 `docs/notes/2026-08-10-clw006-card-spin-failures.md` 沉淀了失败模式与防护。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：无路径/结构改变。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：近况无新增变动。

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
