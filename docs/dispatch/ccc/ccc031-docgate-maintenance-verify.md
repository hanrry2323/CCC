# 任务卡 ccc031 · 维护区四问交叉核对：docgate门禁升级（OpenCode 执行）

> 关联：ccc-plan-011 卡9 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

实现维护区四问真实性交叉核对：新建 `server/board/docgate.py`，把 `approve-merge.sh` 的机械校验（只查非空）升级为「引用工件真实存在且与卡改动一致」，拦截「维护区填假」。依据：ccc-plan-011 阶段三 3.2 + 探查 E 三层接线建议。

## 红线（先看）

1. **只改 `server/board/docgate.py`（新建）+ `scripts/approve-merge.sh`（check_maintenance 调 docgate）+ `server/board/prompt_inject.py`（审计指令升级）+ `server/tests/`**。**禁止改** validate.py 出卡门禁逻辑、registry、卡正文。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
3. **存量 189 张已关闭卡缺维护区不回填不追责**（历史原因）；本卡只对新卡生效，避免一次性全量打回淹没主线。

## 范围

- 新建 `server/board/docgate.py`：`verify_maintenance(card_path, repo_root) -> (ok, problems[])`，解析维护区四问并交叉核对：
  - Q1 方案同步[是] → 卡「关联」含方案编号 → 方案「关联卡」含本卡 ID 或状态∈{部分执行,已完成}
  - Q2 教训沉淀[有] → 说明引用的 docs/notes/*.md / lessons.md 文件存在
  - Q3 档案/README[是] → 引用的项目档案存在且本分支相对 origin/main 有 diff
  - Q4 线路图[是] → roadmap.md 或档案「线路/近况」本分支有改动
  - 机械可判的缺失/对不上 → `ok=False`；语义级（文件在但内容对不上）→ 标 `needs_llm` 待审计席复核
- `scripts/approve-merge.sh` `check_maintenance`（L130-158）改为调用 `docgate.verify_maintenance`，`ok=False` → 拒绝合入（打回执行体）。
- `server/board/prompt_inject.py` `build_auditor_hint()`（L337-341）审计指令升级：核对 [是]/[有] 声明引用工件真实存在且与卡改动一致 → 不实输出「机审：不通过（维护区声明不实）」。
- 补测试：构造「填假」样本（声明引用不存在文件/声明同步但方案无本卡）断言拦截。

## 步骤

1. 读 `scripts/approve-merge.sh:130-158` check_maintenance 现状 + 探查 E 的三层接线建议。
2. 新建 `server/board/docgate.py` 实现 verify_maintenance（复用 check_maintenance 同款 regex 解析维护区）。
3. `approve-merge.sh` check_maintenance 接线 docgate（保留非空基线，叠加交叉核对）。
4. `prompt_inject.py` 审计指令升级。
5. 补测试；`pytest server/tests/test_writeback_gate.py server/tests/` 相关全绿。
6. 用真实卡验证：对 clw001（真实填）应通过；构造一张「教训引用不存在文件」的卡应被拦。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
8. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `docgate.verify_maintenance` 对真实填写的卡（clw001 样本）返回 ok=True。
2. 构造「填假」样本（Q1 声明[是]但方案无本卡关联 / Q2 引用不存在文件）返回 ok=False 且 problems 注明缺失项。
3. `approve-merge.sh` 接线后，填假卡被拒绝合入（打回原因含「维护区声明不实」）。
4. `pytest server/tests/` 全绿。

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
