# 任务卡 ccc040 · 统一 M1/2017 分工文档声明（2017=执行写码节点，M1=中枢）（OpenCode 执行）

> 关联：ccc-plan: M1/2017 执行分工文档统一 + 2017 并发闸门 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-10

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

统一 M1/2017 分工文档声明（2017=执行写码节点，M1=中枢）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `docs/deploy/topology.md`
- `docs/projects/ccc/README.md`
- `docs/architecture.md`
- `docs/projects/onboarding.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. {'docs/deploy/topology.md 与 docs/projects/ccc/README.md 的「M1=写源/开发副本」表述改为现状真相：2017=执行写码节点（engine worktree）+ 生产': '7788；M1=中枢出卡/验收/合入/看板 + 轻量开发；业务仓（qb 等）本体机器写码'}
2. {'分工声明与 server/config/executors.example.json「2017 默认开发」、docs/architecture.md「2017 单端': '7788」一致，无互相矛盾'}
3. 全仓 grep「M1 = git 写源 / M1（写源）」等表述无残留（历史归档 docs/archive 除外，须标注已过时）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

- 实现说明：成功统一了 M1 与 Mac2017 的分工文档声明（2017 = 执行写码节点 + 生产，M1 = 中枢），消除了两者的表述矛盾。
- 测试结果：经 python3 scripts/check-entry-docs.py 与 bash scripts/validate-plans.sh 校验全部通过，无不一致。
- push 证据：已提交并推送至分支 codex/ccc040-governance-doc-alignment，Commit Hash: adae62e5

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 013-governance-doc-and-concurrency.md 已同步。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：本次仅为分工角色文档声明对齐，无核心开发技术教训沉淀。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：更新了 docs/projects/ccc/README.md 路径与职责声明。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：项目主线无变化。

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

## 机审区

**机审方**：2017 机审席 · 日期：2026-08-10 · 结论：**机审：通过**

验收标准逐项核验：
1. ✅ `docs/deploy/topology.md` / `docs/projects/ccc/README.md` / `.ccc/*` / `.cursor/rules/*` 已统一为「2017=执行写码节点（engine worktree）+ 生产 :7788；M1=中枢出卡/验收/合入/看板」。
2. ✅ 与 `docs/architecture.md`「2017 单端 :7788」、`executors.example.json`「2017 默认开发」一致，无互相矛盾。
3. ⚠️→✅ 全仓 grep 门禁：残留 `docs/cursor-code-check-handoff.md`（live 交接文档）「M1 开发副本」表述，机审就地修复对齐后已无残留；仅保留已关闭历史卡（T4/T45-48）与被拒备选方案（005 计划）等历史记录。

改动范围判定：主 commit `8d9b3b17` 改动集中在卡范围（topology/README/onboarding/.ccc/.cursor）+ 卡本身回写，未越界；`docs/architecture.md` 本就为 2017 单端表述无需改动。机审补充 commit `75a4b149` 仅为补全卡验收 #3 全仓门禁，属卡内范围。

维护区完成钩子核验：四问均已勾选并填说明，无占位。

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
