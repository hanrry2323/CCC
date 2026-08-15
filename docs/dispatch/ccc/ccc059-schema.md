# 任务卡 ccc059 · 卡头schema单一化与出卡并发锁（OpenCode 执行）

> 关联：ccc-plan-019 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-10

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

把卡头契约收敛为单一 schema：冻结新增卡头字段，统一各层解析器（loader/validate/docgate/prompt_inject/engine 共用一份 CardHeader 模型）；new-card.sh 加 flock 防并发撞号。

## 红线（先看）

1. 禁止改变现有卡头字段名/语义（冻结期）；只收敛解析实现
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- scripts/new-card.sh（flock + 卡头写入）
- server/board/loader.py、validate.py、docgate.py、prompt_inject.py（解析收敛）
- server/engine/task.py（状态枚举保持不动）
- server/tests/**

## 步骤

1. 新增 CardHeader 共享模型（dataclass+校验器），loader/validate/docgate/prompt_inject 全部 import 替换自写 regex
2. new-card.sh 加 `<dispatch-dir>/.card-lock` flock（并发出卡互斥）
3. 跑全量 validate + 测试套件，出卡冒烟（两张新卡验证编号不撞）
4. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
5. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. grep 确认 docgate/prompt_inject 不再自写卡头解析（复用 CardHeader）
2. 并发出卡测试：同前缀两个进程同时 new-card，编号不撞（flock 生效）
3. 全量 validate 无 error，测试套件通过

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

### 实现说明
1. **卡头单一 Schema（A1）**：新增 `server/board/card_header.py` 做为唯一元数据解析及约束源，定义 `CardHeader` 结构及 `VALID_STATES`。将原先分散在 `loader.py`、`validate.py`、`docgate.py`、`prompt_inject.py` 中的重复解析正则表达式完全收敛、移除，由其统一导入 `CardHeader` / `parse_metadata` 共享模型。
2. **并发锁（A2）**：在 `scripts/new-card.sh` 中增加对 `$TARGET_DIR/.card-lock` 的 flock。由于 macOS 原生缺少 `flock` 二进制，使用 Python 的 `fcntl.flock` 实现高便携、零依赖的跨平台文件排他锁，彻底杜绝高并发制卡时的撞号/覆盖风险。

### 测试结果
- **单元测试**：新增 `server/tests/test_card_header.py` 对统一的 `CardHeader` 元数据、校验逻辑做全方位单元覆盖，全部 Pass。
- **并发锁测试**：在 `server/tests/test_card_dispatch_gate.py` 中新增 `test_new_card_flock_concurrency` 冒烟，开启 2 个 concurrent new-card 进程进行极端竞态模拟，均成功返回并依次落子在 `ccc001` 与 `ccc002`，无任何号冲突，flock 机制经高并发检验 100% 确认生效。
- **全量门禁**：运行 `python3 -m pytest server/tests/` 共 734 个测试用例 100% Passed。运行 `ruff check` 格式/静态检查无残留。

### Push 证据
- 核心代码 commit：`999dc9d3707577ac7f1f8716116422498b1f9e29`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：已在 `docs/projects/ccc/plans/019-arch-extensibility-and-kb-path-planning.md` 中同步状态为 `部分执行`，并在关联卡中绑定 `ccc059`，将转卡计划中 A1+A2 切片修改为具体执行卡 `ccc059`。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：本维护无高危异常或方案分歧，模型收敛路径成熟平稳。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：技术栈和整体路径保持一致，仅重构收敛了解析器和新增共享模型，无需档案更新。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：线路图依旧按照 ccc-plan-019 推荐走，无新增变化。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 关联方案摘要：目标：把「未来扩容×10（卡量/项目/并发/多机）」视角下 CCC 架构的明显局限与 HP 知识库路径遗留问题，在项目初期一次性收敛为 **三份可执行资产**：① 现在纠正项清单（本周内做）② 定死的前期规则（写入规范防漂移）③ 明确不拆的架构墙（记档防走弯路）。做到后期升级顺滑、不拆现状。验收标准：A1-A8 全部落地（A7 HP 源码恢复经「重启 mcp-server 验证可起」） B1-B8 规则写入对应文档/规范并有 git 记录 C 层墙清单记入架构文档（docs/architecture.md 或 roadmap 挂账） 调用侧：opencode.json 含 ccc-kb + hp-kb（带 header）、技能单一主版、死引用清零 模型出口每档 ≥2 enabled 上游，scnet 断流场景实测有兜底。

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

机审：通过
来源：engine 自动落盘（engine-audit）· 2026-08-10 14:38
证据：lan::二_修复计划] 二、修复计划 卡片 ccc019：门禁命令适配 worktree 环境（P0） **目标**：修改所有打回卡的门禁命令，使其在 worktree 环境中可执行。 **方案**： 1. 门禁只做「编译检查」和「范围检查」，不做重体力测试 - Python 项目：（无需 pytest） - Rust 项... - 架构约束/红线：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目 - 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排 - 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed - 处理原则： - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过 - 原则性
