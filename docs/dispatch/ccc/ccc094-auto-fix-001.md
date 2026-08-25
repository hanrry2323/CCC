# 任务卡 ccc094 · auto-fix-001：修复 auto-fix-plan-progress.py 生产subprocess调用import server必然失败的死障（DSH 执行）

> 关联：外脑清场收尾2026-08-26 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-26

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`

## 目标

scripts/auto-fix-plan-progress.py 被 observer 以 subprocess 方式调用（server/engine/observer.py:694，无 PYTHONPATH、子进程 sys.path[0]=scripts/）时，`from server.board.plans import sync_plan_progress` 必然 ModuleNotFoundError → rc=1。日志实证：该自动修复历史失败 196 次、成功 0 次（最早出现远早于 2026-08-26）。修复：脚本头部加 sys.path 引导（以仓根为基准），使 subprocess 调用可正常 import。

## 实现

（二级实现详情：功能背景 / 开发要求 / 关键代码思路。ccc-plan-027 功能卡「实现」段自动注入此区；无注入时执行体在实现前补齐。）

## 红线（先看）

1. 白名单：scripts/auto-fix-plan-progress.py（唯一允许改动文件）。
2. 只修 import 引导，不改业务逻辑与既有行为语义：sync_plan_progress / sync_milestone_progress 的调用方式、参数、退出码约定全部保持不变。
3. 保持既有 CCC_DATA_DIR setdefault 兜底口径不变（ccc088 既有防线，防回落双写陈旧索引）。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

仅 scripts/auto-fix-plan-progress.py 一个文件；不触碰 server/ 下任何模块。

## 步骤

1. 脚本头部 import 区之后加仓根 sys.path 引导（以脚本文件位置向上推仓根，或 Path(__file__).resolve().parents[1]），确保裸 subprocess 调用可导入 server 包。
2. 自测：模拟生产调用方式（subprocess 从非仓根 cwd 调起）验证 rc=0；对照触发一次 xy-plan 进度校验确认无 ModuleNotFoundError。

## 验收标准

1. 模拟生产调用方式（subprocess、非仓根 cwd）跑一次脚本，rc=0 且输出正常。
2. 手动触发一次 xy-plan-006~009 进度校验，无 ModuleNotFoundError。
3. 不改变脚本既有行为语义（只修 import，不动业务逻辑）；python3 -m py_compile 与语法检查通过，diff 中无业务逻辑行变更。

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试： python3 -m py_compile scripts/auto-fix-plan-progress.py
编译：
lint：
范围：true

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：DSH · 日期：2026-08-26

- **实现说明**：`scripts/auto-fix-plan-progress.py` 头部 import 区后（`CCC_DATA_DIR` setdefault 兜底行原样保留之后）新增仓根 sys.path 引导段：`_REPO_ROOT = Path(__file__).resolve().parents[1]`，不在 sys.path 则 `insert(0, …)`，共 8 行纯新增（4 行注释 + 3 行引导代码 + 1 行块后空行；机审席更正：原拆分漏计空行）；业务逻辑零改动，`sync_plan_progress`/`sync_milestone_progress` 调用方式、参数、退出码约定全部不变。仓根顶层无 `.py` 文件，前置插入无标准库遮蔽风险。
- **测试结果**：① 门禁 `python3 -m py_compile scripts/auto-fix-plan-progress.py` PASS；② 修前复现：`cd /tmp && env -u PYTHONPATH python3 <repo>/scripts/auto-fix-plan-progress.py <repo> docs/projects/xy/plans/006-quality-quantification.md xy` → `ModuleNotFoundError: No module named 'server'` rc=1（死障实证）；③ 修后同口径复测 → `进度已同步: 3/3 (100%)` rc=0；④ xy-plan-006~009 四方案全量触发均 rc=0、无 ModuleNotFoundError。自测产生的 roadmap/方案回写属脚本正常业务行为且在白名单外，已还原不随本卡提交。
- **push 证据**：分支 `codex/ccc094-auto-fix-001` → commit `27dd63041`（1 file changed, 8 insertions），已 push 至 origin 成功（rc=0）。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：本卡为外脑清场收尾指令直派单点修复（编号 auto-fix-001），非方案池转卡，无关联方案需同步。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：修复为 Python 导入机制既有知识级别的单行 sys.path 引导，未达新增 lessons 条目门槛；pattern 已留痕于卡面与 commit message。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：仅单文件内 import 路径引导，项目结构/技术栈/路径零变化。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：死障修复不改规划，项目近况与下一步无变化。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：ccc（CCC 平台自研主仓）

- 本卡由外脑清场收尾指令直派（编号 auto-fix-001）；因 new-card.sh 对 ccc 前缀设 FORBIDDEN_CARD_PREFIXES 护栏，本卡按 DOC-PROTOCOL 命名手工制卡并过同款 validate 门禁，外脑指令已授权。

- 代码工作区：直接在本仓 main 工作区修改（平台自研脚本卡，无需 worktree）；禁止直推 main 之外的分支操作

- 执行要求：先 Read 任务卡全文，按白名单范围改动；完成后 commit+push 到 main

- 禁止：改 server/ 代码、越出白名单、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：ccc（CCC 平台自研主仓）

- 审查重点：改动是否仅为 sys.path 引导一行；是否触碰业务逻辑；验收三条独立复现

- 处理原则：

  - 可修问题（命名/注释/小重构）→ 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

## 机审区

**DSH 机审席 · 2026-08-26 · severity：轻**

> 独立核验基础：`git show 27dd63041` / `cc3b543d4` 全文、origin 分支比对、生产口径探针复现、方案池与仓根结构扫描。不采信执行体自述，结论全部附可复现证据。

**范围核对（在白名单内）**

- fix commit `27dd63041`：仅触 `scripts/auto-fix-plan-progress.py`，numstat `1 file changed, 8 insertions(+)` 零删改；回写 commit `cc3b543d4`：仅触本卡文件。
- 分支 `codex/ccc094-auto-fix-001` 符合命名规范；本地 HEAD == `origin/codex/ccc094-auto-fix-001`（`cc3b543d4`），push 证据属实。

**对抗式核查（0 实质缺陷 · 风险论证）**

1. 业务语义零变更：diff 为纯新增 8 行，插于 CCC_DATA_DIR setdefault 兜底行（原样保留）与 `def main` 之间；`sync_plan_progress`/`sync_milestone_progress` 调用方式、参数、退出码约定逐行比对未变（红线 2/3 守住）。
2. 生产口径独立复现：`cd /tmp && env -u PYTHONPATH python3 <repo>/scripts/auto-fix-plan-progress.py <repo> docs/projects/__probe_nonexistent_094__.md ccc` → stderr 仅业务级「sync_plan_progress 失败: 方案文件不存在」rc=1，无 ModuleNotFoundError——裸 subprocess 死障确已解除；探针后 `git status --short` 干净，零污染。
3. 遮蔽风险排查：仓根顶层无 `.py` 文件（回写声明属实）；顶层目录 deploy/desktop/docs/inbox/knowledge/references/scripts/server/specs/vendor 与 server/ 全部顶层 import 名零交集（grep 扫描空集）；server 以 namespace package 经仓根入径，前置插入无新增遮蔽面。scripts/ 内模块名多为连字符不可导入，且其 sys.path 位次相对关系未被本次改动恶化。
4. 卡面引用核实：`server/engine/observer.py:694` 即 `script = project_root / "scripts" / "auto-fix-plan-progress.py"`，subprocess.run 无 env 定制——死障机理与卡描述一致。测试回归面干净：test_observer.py 仅 tmp_path 造脚本断言参数，不执行真脚本。
5. 维护区四问机械判据：四问均单选实填（[否]/[无]/[否]/[否]），说明非占位非模板；第 1 问抽查方案池——041-writeback-loop-fix 对本脚本仅历史背景引用（其 P1-2 断链当时已收口），并非本卡关联方案，「无关联方案需同步」声明成立；第 3/4 问与分支 diff 比对属实（结构/路径/roadmap 零变化）。
6. 「失败 196 次」计数为本机无法独立复核的日志值（本机无对应日志文件）；按机制推定成立：修前该脚本任何裸调用必 ModuleNotFoundError，成功 0 次与代码事实一致。

**发现项（均轻微，合计 severity=轻）**

- F1 回写区行数拆分口径不精确：「8 行纯新增（4 行注释 + 3 行引导代码）」漏计 1 行块后空行（4+3≠8；numstat「8 insertions」本身准确）。已按先例（ccc093 numstat 更正）就地更正，随本席 commit+push。
- F2 制卡模板残留矛盾（记录不改原文）：卡「执行提示」段写「直接在本仓 main 工作区修改…commit+push 到 main；禁止直推 main 之外的分支操作」，与硬红线「不直推 main」直接冲突。执行体实际走 codex/ 分支 push，为合规路线。本席不改制卡指令原文，留此记录供制卡模板修正——后续同型直派卡应删除该残留句。

**结论**：无 P0/P1，白名单/兜底口径/main 红线三向守住，维护区四问真实填写，验收标准第 1 条经独立同口径复现证实。F1 就地修复完毕，F2 记录备模板治理。

机审：通过（被审 cc3b543d482e）
