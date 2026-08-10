# 任务卡 ccc055 · validate-plans.sh 方案级收尾校验（OpenCode 执行）

> 关联：ccc-plan-017 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-10

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

validate-plans.sh 方案级收尾校验（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `scripts/validate-plans.sh`
- `server/tests/**`
- `docs/projects/**/plans/*`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. validate-plans.sh 增加方案级收尾校验：方案关联卡全部关闭但方案状态仍为草案/已确认/部分执行（未推进）→ 报错
2. 方案「已完成」但验收未勾选 → 报错
3. 现有方案库跑一遍：列出所有「卡全关未收尾」方案供后续收尾
4. validate-plans.sh 测试覆盖新校验

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

### 实现说明
1. **方案级收尾校验**：升级了 `scripts/validate-plans.sh`。对于每一个方案文件，提取状态与关联卡信息：
   - 提取方案下的 `## 验收标准` 段落。若方案状态为 `已完成`，且发现任何未勾选的项（如 `- [ ]`），则报错并显示未勾选的具体项目数量。
   - 提取方案头部的 `关联卡`。若方案状态为 `草案`、`已确认` 或 `部分执行`，且所关联的所有卡在 `docs/dispatch/` 中的状态均已置为 `已关闭`，则报错，提示方案应当已经推进。
2. **测试覆盖**：在 `server/tests/test_plans.py` 中新增 `TestValidatePlansScript` 测试类，使用真实的 `validate-plans.sh` 脚本和模拟环境覆盖了包含合法方案、已完成但未勾选验收方案、已完成且全勾选方案，以及卡全关但方案未收尾方案，测试全部顺利通过。

### 测试结果
- 本地运行 `python3 -m pytest server/tests/test_plans.py`，全部 48 个测试（含 4 个新测试）完美通过：
  ```
  48 passed in 1.49s
  ```
- 静态分析及文档门禁全绿：
  - `python3 scripts/check-entry-docs.py` -> `[OK] 入口文档门禁通过（零硬编码 + 必需指针齐全）`
  - `python3 -m ruff check server/tests/test_plans.py` -> `All checks passed!`

### push 证据
- Branch: `codex/ccc055-validate-plans-delivery-gate`
- Commit Hash: 189276f7671631cdecb12388b841989c7e6c4622

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]
   - 说明：关联方案 `docs/projects/ccc/plans/017-delivery-gate.md` 的状态已从「已确认」推进至「部分执行」。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：无，纯门禁脚本升级与质量工具收尾。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：未改变任何项目结构或技术栈。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：未发生变化，路线图及项目近况完全吻合。

## 机审区

> 验收：2017 · 日期：2026-08-10

**机审：通过**

审查摘要：
- **范围**：改动仅限卡声明的 `scripts/validate-plans.sh`、`server/tests/test_plans.py`、`docs/projects/ccc/plans/017-delivery-gate.md` 及卡文件本体，无越界。
- **功能落位**：§8.1「方案已完成但验收未勾选→报错」与 §8.2「关联卡全关但状态未推进→报错」均按验收标准落地；全量跑现有方案库，8 个「卡全关未收尾/已完成未勾选」方案被正确列出（015/016/009/011/012/013/hp001/mx001），与验收标准 3 预期一致。
- **验证**：`python3 -m pytest server/tests/test_plans.py` 48 passed；`./scripts/validate-plans.sh` 行为符合预期。
- **可修项已就地修复**：清除「关联卡校验」中未使用的死变量 `has_cards` / `open_cards`（不影响逻辑，跑后同 8 个 FAIL，48 测试全绿）。
- **维护区四问**均已逐项勾选并填实质说明；[是] 声明（方案 017 已推进至「部分执行」）经核对与真实文件一致，无声明不实。

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 关联方案摘要：目标：补齐「项目交付收尾 SOP」——从单卡级完成钩子升级到**方案级交付门禁（Delivery Gate）**，并给 validate-plans.sh 加方案级收尾校验。验收标准：§7 落地：onboarding 含交付收尾章节 + delivery-template，交付物清单可勾选。 validate-plans.sh 方案级校验生效：构造「卡全关未标完成」方案 → 报错。 现有 13 个「卡全关未收尾」方案在 §7 定稿后逐一收尾（或由 §7 执行流程覆盖）。

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
