# 任务卡 ccc066 · 机审钉commit与resolve唯一性（OpenCode 执行）

> 关联：phase-3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-10
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

（一句话，可验收。）

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

（明确本卡改动范围，白名单式列出。）

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. （可执行的验收点，附命令/可观察结果）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

**完成情况**：V6+V7 全部落地，测试全绿。

- **V6 机审钉 commit**：engine 机审启动前记录分支 tip（被审 commit），通过后把「机审：通过」改写为「机审：通过（被审 <sha12>）」进信封（幂等）；approve-merge 合入前解析信封「被审 sha」，校验 `被审 sha..origin/<branch>` 之间除 docs/dispatch/** 外无任何改动——机审后漂移 → 拒绝合入须重新机审。老信封（无被审行）不强制，兼容存量。
- **V7 resolve_card 唯一性**：抽到 `scripts/lib/card-resolve.sh` 共享库，多命中直接报错列出全部候选（禁止 head -1 猜）；新增 `scripts/tests/test-card-resolve.sh` 覆盖唯一命中/找不到/二义性三场景。
- 新增 `server/tests/test_engine_v2v3_gate.py::TestV6AuditCommitPin` 4 用例（钉 sha/幂等/无 sha/无机审通过不改写）。

**验收自测**：engine 全部测试 + V6 单测 + V7 bash 测试 + bash -n/py_compile 全过。



## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：ccc-plan-019 范围内子项，方案状态待 ccc059-064 全关后统一推进
2. **教训沉淀**：本卡是否产出可复用教训？[有]
   - 说明：教训已沉淀 docs/notes/2026-08-10-ccc-lessons.md（机审钉 commit / resolve_card 唯一性 / 分支名与卡文件名一致）
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是]
   - 说明：新增 scripts/lib/card-resolve.sh 共享函数库与 scripts/tests/ 测试目录，已同步 docs/projects/ccc/README.md（新增「共享库」行）
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：线路图无变化

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

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

- 审查清单：
  - [domains::plans::ccc::003-flow-fix-plan::二_修复计划] 二、修复计划 卡片 ccc019：门禁命令适配 worktree 环境（P0） **目标**：修改所有打回卡的门禁命令，使其在 worktree 环境中可执行。 **方案**： 1. 门禁只做「编译检查」和「范围检查」，不做重体力测试 - Python 项目：（无需 pytest） - Rust 项...

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

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。

## 机审区

**机审：通过（被审 2af68af5）**（2017 机审席 · 2026-08-10）

审查摘要：
- **范围**：本卡核心改动仅 5 文件（scripts/approve-merge.sh、scripts/lib/card-resolve.sh、scripts/tests/test-card-resolve.sh、server/engine/main.py、server/tests/test_engine_v2v3_gate.py），V6+V7 落地与回写区声明一致；未触碰 qb/hp 业务仓、运行面、密钥或无关文件。
- **架构合理性（V6 机审钉 commit）**：机审启动前读 worktree 分支远端 tip 记录被审 sha，通过后把信封「机审：通过」改写为「机审：通过（被审 <sha12>）」（幂等，老信封无被审行不强制，兼容存量）；approve-merge 合入前解析被审 sha 并校验 `被审 sha..origin/<branch>` 间除 docs/dispatch/** 外无改动——机审后漂移即拒绝合入须重审。把验收从「验文本」升级为「钉不可变 commit」，原则正确。
- **架构合理性（V7 resolve_card 唯一性）**：抽 `scripts/lib/card-resolve.sh` 共享库，多命中直接报错列全部候选（弃 head -1 猜），被 approve-merge.sh 复用，防实现漂移；test 覆盖唯一/找不到/二义性三态。正确。
- **边界安全**：`_pin_audit_commit` 无 sha / 无「机审：通过」行均 no-op；`_worktree_branch_tip` 对 worktree 缺失/命令异常吞异常返回 None；approve 侧 sha 不可解析回显报错拒绝，不静默放过。安全性达标。
- **维护区四问**：逐项勾选并填实质说明（[否]/[有]/[是]/[否]）；其中「[有] 教训沉淀」与「[是] 档案/README 同步（新增 scripts/lib、scripts/tests）」声明真实成立——新增工件均已在工作树存在且被 commit。
- **可修问题（已就地修复并 commit+push）**：`scripts/tests/test-card-resolve.sh:11` 硬编码 `source /Users/apple/program/CCC/...` 绝对路径——该路径在本机(fan)不存在、且直接违背本卡所属 ccc019 P0「门禁适配 worktree」目标；已改为按 `BASH_SOURCE` 相对定位 `../lib/card-resolve.sh`，本机实跑 `bash scripts/tests/test-card-resolve.sh` 全过（exit 0），bash -n 两文件语法 OK，push 为分支 tag `2af68af5`。
- **修复后自验通过**：机审判据非 pytest/编译/范围等机械指标（由机械门禁已裁决），仅作原则性 Code Review + 修正上述可修缺陷，均落地修复并推回。
