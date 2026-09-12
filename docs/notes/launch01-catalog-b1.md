# CCC 盘点目录（catalog）

> 生成：2026-09-13 · 只读分析席盘点（CCC 文档仓部分检出）
> 检出口径：`docs/projects/<前缀>/README.md`、`plans/*.md`、`roadmap.md`、`deliveries/*.md`；定级证据=`meta/last-commits.txt`（每文件最后 git 提交时间与说明）+ 文件正文对照；本检出根非 git 仓库，未执行 git 命令（业务仓 git 状态按第七条判为「检出内不可核 → 待核」）。
> 定级含义：现行=仍在推进/未闭环的活方案；史实=已完成/已归档，仅作历史记录；待核=证据不足以判定。
> 红线声明：本盘点仅新增/覆写本文件 catalog.md，未修改任何检出文件，未执行任何写操作。

---

## 一、项目 qb

### 1) 项目目标一句话
CCC 自动化开发测试用业务仓（挂 Engine 出卡）；本机 M1 无代码，业务仓在 Mac2017（`/Users/fan/program/apps/qb`），一切以看板/方案池为入口。—— 出处：`docs/projects/qb/README.md`

### 2) plans/ 逐篇定级

| 方案文件 | 定级 | 最后实质改动（meta 证据） | 判定依据 |
|---|---|---|---|
| `docs/projects/qb/plans/001-refactor.md` | **史实** | 2026-09-03 02:22:29（chore：清理 74 个已完成/作废方案的悬空旧卡引用并标注已归档） | 方案自标「状态：已完成 · 进度 6/6 (100%)」；关联卡 qb001-006 已随 8-24 治理归档；9-03 清理提交即归档标记。与 README「近况见看板未关闭卡」无冲突。 |
| `docs/projects/qb/plans/002-strategy-core-unify.md` | **现行（待验收，未闭环）** | 2026-08-19 22:30:05（plans: update） | 方案自标「状态：待验收 · 进度 1/1 (100%)」、验收标准 4 项全未勾选；关联卡 qb008 无合入/关闭证据；roadmap（2026-08-26 更新，晚于方案）仍标 1.1「待验收」、M1「待启动」。自 8-19 起无实质更新。 |
| `docs/projects/qb/plans/003-backtest-triconverge.md` | **现行（待验收，未闭环）** | 2026-08-19 23:25:15（plans: update） | 方案自标「状态：待验收 · 进度 1/1 (100%)」、验收标准 4 项全未勾选；关联卡 qb007 无合入/关闭证据；roadmap 8-26 仍标 1.2「待验收」。⚠️ 见未闭环事项编号错位。 |

注：roadmap 引用 qb-plan-004~015（M1 子项 1.3/1.4、M2、M3）不在本次检出内，无法定级，均以 roadmap「待启动/待立项」为准。—— 出处：`docs/projects/qb/roadmap.md`

### 3) 未闭环事项

- 验收标准 4 项全未勾选（unified_arb 真实数据跑通 BacktestRunner、R14 同代码、既有策略不回归、pytest 全绿）；关联卡 qb008 待验收。—— 出处：`docs/projects/qb/plans/002-strategy-core-unify.md`
- M1.2「真实数据回测通路」依赖 1.1（qb-plan-002）完成后才能接真实数据；当前 M1 整体「待启动」但 1.1/1.2 已挂「待验收」，状态链有待核实。—— 出处：`docs/projects/qb/plans/002-strategy-core-unify.md`（备注）、`docs/projects/qb/roadmap.md`（M1 章节）
- 验收标准 4 项全未勾选（回测入口单一、无循环弃用、legacy 加废弃头注、pytest 全绿）；关联卡 qb007 待验收。—— 出处：`docs/projects/qb/plans/003-backtest-triconverge.md`
- backtest/data.db 为空（4096 字节无 ohlcv 表）属 M1.2 范围，本方案只收敛入口不补数据——遗留待 M1.2 处理。—— 出处：`docs/projects/qb/plans/003-backtest-triconverge.md`（备注）
- **编号错位（待核）**：roadmap M1 把「1.2 真实数据回测通路」挂 qb-plan-003、把「1.3 回测三套收敛」挂 qb-plan-004；但文件 003 自标编号 qb-plan-003、子项目 1.3「回测三套收敛」，且检出内不存在 qb-plan-004。方案文件与 roadmap 的编号归属互相矛盾，需人工核对。—— 出处：`docs/projects/qb/roadmap.md`（M1 章节）vs `docs/projects/qb/plans/003-backtest-triconverge.md`（头部）
- 草案池冻结项：跨机扩展（2.0.0 cluster）与组合 ML/高维因子均冻结，门槛未满足前不激活（属冻结决策，非待办）。—— 出处：`docs/projects/qb/roadmap.md`（草案池）

### 4) 重新纳入判定建议（移植令口径·门槛五查）

| 门槛 | 判定 | 证据 / 说明 |
|---|---|---|
| ① 项目真实存续（近 30 天有实质动静或 owner 明示在做） | ✅（文档层） | 近 30 天内有 `qb/roadmap.md` 2026-08-26 更新（方案进度级联回写，属进度信号）；09-03 批量 chore 为归档治理触碰，非实质动静。README 称「以看板/方案池为入口、近况见看板未关闭卡」，owner 明示动作未在检出内直接出现。→ 判定 ✅（证据偏文档层，业务仓动静见②） |
| ② 业务仓可达且有有效 git 状态 | 待核 | 业务仓在 Mac2017（`/Users/fan/program/apps/qb`），本检出根非 git 仓库且 M1 无代码（README 明示），检出内无从核 git 状态 → 按口径标待核，需迁移席/外核在 2017 核 `git status`/HEAD。 |
| ③ 目标一句话与现状对得上 | ✅ | README 目标「自动化开发测试仓、看板为入口、近况见未关闭卡」与现实一致：plans 002/003 正处「待验收」未关闭，与 roadmap M1「待启动/待验收」吻合，无冲突。—— 出处：`docs/projects/qb/README.md`、`docs/projects/qb/plans/002|003`、`docs/projects/qb/roadmap.md` |
| ④ plans 完成度与 roadmap/看板声称一致 | ⚠️ 待核 | 已完成段一致（plan-001 已完成）。但 1.2/1.3 编号错位（见未闭环事项）、plan-002/003 自标进度 100% 却验收零勾选、roadmap M1 整体「待启动」vs 子项目「待验收」——口径部分一致、部分待核。→ 待核 |
| ⑤ 卡头规范兼容（六态口径） | ✅（方案层）／待核（卡头） | plans 头部使用「已完成 / 待验收 / 待排期」等状态词与六态口径词汇兼容，关联卡以编号引用（qb007/qb008）；卡头实态在 `docs/dispatch/qb/`（未检出），需外核。→ 方案层 ✅，卡头待核 |

**综合建议：🔧 整改后可入**（差：② 业务仓 git 可达性独立核证；④ 编号错位人工核清 + 验收未勾选项闭环；① 补 owner 近况明示以强化存续证据）。本项目非僵尸（有 8-26 级联回写活证 + 两张待验收卡在板），但业务仓证据全部依赖外核，核清前不得视为全合格。

---

## 二、项目 xianyu（xy）

### 1) 项目目标一句话
2017 上的独立业务仓（`/Users/fan/program/apps/xianyu`），经 CCC 出卡驱动；当前双线运行——开发线（Build）只出代码与可运行版本，生产线（Produce）只消费已验收版本做文章/配图/视频本地产出，M7 发布线因 Cookie 前置冻结。—— 出处：`docs/projects/xy/README.md`

### 2) plans/ 逐篇定级

| 方案文件 | 定级 | 最后实质改动（meta 证据） | 判定依据 |
|---|---|---|---|
| `docs/projects/xy/plans/001-video-milestone.md` | **史实** | 2026-09-03 02:22:29（chore：清理已完成/作废方案并标注已归档） | 状态「已完成 · 进度 31/31 (100%)」；关联卡 xy001-032 已归档；交付报告 xy-delivery-001（2026-08-19）确认 M1 交付、方案置已完成；roadmap M1「已完成（已闭环挂账）」 |
| `docs/projects/xy/plans/002-test-baseline-green.md` | **史实** | 2026-09-03 02:22:29（chore 清理） | 状态「已完成 · 进度 4/4 (100%)」，验收标准 4/4 全勾选；roadmap M2-2.1「已完成」；曾记治理债「声明 3/4 实际 4/4」已随文件更新为 4/4 一致 |
| `docs/projects/xy/plans/003-breakage-fixes.md` | **史实** | 2026-09-03 02:22:29（chore 清理） | 状态「已完成 · 进度 3/3 (100%)」，验收 3/3 勾选；roadmap M2-2.2「已完成」；曾记治理债「声明 2/3 实际 3/3」已一致 |
| `docs/projects/xy/plans/004-runtime-rebuild.md` | **史实** | 2026-09-03 02:22:29（chore 清理） | 状态「已完成 · 进度 3/3 (100%)」，验收 4/4 勾选；roadmap M2-2.3「已完成」；曾记治理债已一致 |
| `docs/projects/xy/plans/005-visual-template-library.md` | **史实** | 2026-09-03 02:22:29（chore 清理） | 状态「已完成 · 进度 3/3 (100%)」，验收 4/4 勾选；roadmap M3-3.1「已完成」；曾记治理债已一致 |
| `docs/projects/xy/plans/006-quality-quantification.md` | **史实** | 2026-09-03 02:22:29（chore 清理） | 状态「已完成 · 进度 3/3 (100%)」，验收 4/4 勾选；roadmap M3-3.2「已完成」；曾记治理债已一致 |
| `docs/projects/xy/plans/007-render-engine-upgrade.md` | **史实** | 2026-09-03 02:22:29（chore 清理） | 状态「已完成 · 进度 3/3 (100%)」，验收 4/4 勾选；roadmap M3-3.3「已完成」；曾记治理债已一致 |
| `docs/projects/xy/plans/008-high-expression-v2.md` | **现行（部分执行）** | 2026-09-10 19:03:03（docs(xy): plan-008 关联卡登记 xy069） | 状态「部分执行」、更新至 09-10 仍在动（登记 xy069）；roadmap 09-10「下一轮优化」xy068/xy069 已批准执行，plan-008 已列 xy059/064/067/065/066/068/069 为关联卡。⚠️ 头部「进度：2/2 (100%)」与状态「部分执行」不一致，见未闭环事项 |
| `docs/projects/xy/plans/009-frontend-showcase.md` | **现行（部分执行）** | 2026-09-08 23:44:19（docs(xy): plan-008/009 关联卡登记 xy064） | 状态「部分执行」；依赖链已记 xy052 ✅ 合入、草案池 08-21 记 xy054 已合入（进度不一致已解决）；roadmap M6「执行中」。⚠️ roadmap 子项目 6.1-6.4 仍全标「计划中」，疑似滞后，见未闭环事项 |
| `docs/projects/xy/plans/010-publish-closure.md` | **现行（待排期·冻结，非作废）** | 2026-08-22 11:39:40（hardening(ccc) 提交，非内容实质改动；头部自标更新 08-20） | 状态「待排期」、关联卡「待出，等前置」；README「发布线（M7）仍因 Cookie 前置冻结」；delivery-001「发布闭环本次不含（依赖 Cookie，另行立项）」；roadmap M7「起草（等 Cookie 前置）」。属外部队列前置的挂起方案，非废弃 |

### 3) 未闭环事项

**方案级（M5/M6/M7 主体未闭环）**

- M5（xy-plan-008）验收标准 4 项全未勾选：帧渲染器出片达标、Playwright 降级、≥3 新模板 + html-preview CLI、A/B 结构化报告。—— 出处：`docs/projects/xy/plans/008-high-expression-v2.md`
- **口径矛盾（待核）**：xy-plan-008 头部「进度：2/2 (100%)」却「状态：部分执行」，且子项目 5.1-5.3 全部「计划中」——进度与状态口径需人工核对（roadmap 曾多次记录同类「进度不一致」治理债，如 002-007、009）。—— 出处：`docs/projects/xy/plans/008-high-expression-v2.md`（头部）、`docs/projects/xy/roadmap.md`（M5 章节）
- M5「其余功能卡待出」：plan-008 转卡计划中 Playwright 帧渲染器 / 模板规模化 / A-B 评估的功能卡未全部出卡；且 M5 启动排在「M6 全部卡验收后」之后。—— 出处：`docs/projects/xy/plans/008-high-expression-v2.md`（功能卡·转卡计划、依赖链）
- Playwright 环境前置未完成验证：plan-008 要求 2017 上 `pip install playwright` + chromium，属卡内前置自验证项。—— 出处：`docs/projects/xy/plans/008-high-expression-v2.md`（备注）
- M6（xy-plan-009）验收标准 5 项全未勾选（首页今日产出可播、图文可读、工作流节点实时 ≤10s 刷新、失败标红跳日志、只读不碰生产代码）。—— 出处：`docs/projects/xy/plans/009-frontend-showcase.md`
- **roadmap 状态滞后（待核）**：roadmap 09-09 把 M6 子项目 6.1-6.4 全标「计划中」，但 plan-009 依赖链记 xy052 已合入、草案池记 08-21 xy054 已合入（实际 3/4 与声明一致）——roadmap 子项目状态未随合入回写，需人工核对实际进度。—— 出处：`docs/projects/xy/roadmap.md`（M6 章节、草案池）vs `docs/projects/xy/plans/009-frontend-showcase.md`（依赖链、本次激活子项目）
- plan-009「本次激活子项目」段称仅激活 6.1「内容库 API」、6.2/6.3/6.4 均未激活，与依赖链中 xy053-055 的合入表述并存，两处口径需核对。—— 出处：`docs/projects/xy/plans/009-frontend-showcase.md`
- M7（xy-plan-010）验收标准 4 项全未勾选（≥2 平台真发布、Cookie 失效检测告警、排期自动发布+重试告警、效果数据入展示台）；关联卡全部待出，等「平台 Cookie 就绪」前置信号。—— 出处：`docs/projects/xy/plans/010-publish-closure.md`、`docs/projects/xy/README.md`

**执行链级待办（roadmap 09-09「下一步计划」+ 09-10「下一轮优化」）**

- 修 CCC 编排闭环（前置项）：锁定「执行已完成但卡状态回待分派/打回」状态链、修 phase2 机审打回落盘 CAS 竞态、作废卡防重派，用一张最小测试卡验证。—— 出处：`docs/projects/xy/roadmap.md`（下一步计划 1）
- 重开 xy064（或 xy067）开发卡：承接 HyperFrames 真入口验收闭环（业务代码已在 main，仅需机审 PASS→关闭）；⚠️ 同一 roadmap「现状」段称 xy064「业务成果保留、不重开」，与「下一步计划」重开口径并存，待核。—— 出处：`docs/projects/xy/roadmap.md`（现状与下一步计划）
- 出 xy065 文案垂类化卡（3456 通道 Code/flash + 垂类模板）、xy066 配图语义选图卡（按段落关键词真实选图）。—— 出处：`docs/projects/xy/roadmap.md`（下一步计划 3/4）
- 生产线复跑：消费已验收版本产出对比页（旧 5fps PIL vs 新 30fps 真动效）供老板验收。—— 出处：`docs/projects/xy/roadmap.md`（下一步计划 5）
- 下一轮优化卡序：xy068（生产 video worker 接 HyperFrames 30fps + rewriter 标签修正 + publish 前落盘 final.mp4）、xy069（writer 字数自校正 3456→350±50）、生产复跑验证 route 真注册、对比验收页。—— 出处：`docs/projects/xy/roadmap.md`（下一轮优化，2026-09-10 批准执行）
- 当前待办缺口：文案 3456 通道落地、配图语义选图、端到端 30fps 真动效视频（老板已拍板 Code/flash）。—— 出处：`docs/projects/xy/roadmap.md`（现状）

**交付级遗留**

- xy-delivery-001：Git tag v0.0.9 落后 VERSION v0.0.22，「待补 tag」；发布闭环（D4 真发布）本次不含，依赖 Cookie 另行立项。—— 出处：`docs/projects/xy/deliveries/xy-delivery-001.md`
- 企微告警 webhook 真值依赖老板提供；验收已降级为「代码就绪 + 标注待配」（备注明确不阻塞 M2）。—— 出处：`docs/projects/xy/plans/003-breakage-fixes.md`（备注、功能卡）
- 运行方式重建遗留：launchd 化 worker 池正式调度由后续另行立项（方案内不引入新轮子）；roadmap 09-09 现状显示 12 个 launchd 守护 + worker 池 xy050 已全绿，说明已落地，但「正式调度」立项状态未见闭合记录。—— 出处：`docs/projects/xy/plans/004-runtime-rebuild.md`（备注）、`docs/projects/xy/plans/009-frontend-showcase.md`（背景）
- M1 遗留目标 M3 规模化（模板参数化、批量生产、SAU 分发）：「任务卡在 M2 验收后另行派发」——后续已由 M2/M3 系列方案（002-007）承接，本次盘点未见独立闭合记录，仅作史实备注。—— 出处：`docs/projects/xy/plans/001-video-milestone.md`（九、备注）
- README「下一程意向」称「最后接 M6 展示台」，但 roadmap 09-09/09-10 显示 M6 已「执行中」且「优先执行」——README 近况段疑似滞后于 roadmap，待核。—— 出处：`docs/projects/xy/README.md`（线路/近况）vs `docs/projects/xy/roadmap.md`

### 4) 重新纳入判定建议（移植令口径·门槛五查）

| 门槛 | 判定 | 证据 / 说明 |
|---|---|---|
| ① 项目真实存续（近 30 天有实质动静或 owner 明示在做） | ✅ | 近 30 天动静密集：roadmap 2026-09-10 批准执行 xy068/xy069、09-09 现状与下一步计划；plan-008 09-10 登记关联卡 xy069；plan-009 09-08 登记 xy064；README 09-08 更新双线执行规则。owner（老板）已拍板 Code/flash 方向。→ 明确存续。—— 出处：`meta/last-commits.txt`、`docs/projects/xy/roadmap.md` |
| ② 业务仓可达且有有效 git 状态 | 待核 | 业务仓在 Mac2017（`/Users/fan/program/apps/xianyu`），本检出根非 git 仓库且 M1 无代码，检出内无从核 git 状态。旁证：roadmap 记 xy064「业务代码已全部合入 xianyu main（f2ad113，含 F1-F8 修复）」「video-pipeline/tests/ 35 项测试通过」、12 个 launchd 守护 + worker 池 xy050 全绿——为转述证据，非本检出可核。→ 按口径标待核，需迁移席在 2017 核 `git status`/HEAD/f2ad113。 |
| ③ 目标一句话与现状对得上 | ✅（带备注） | README 目标「双线运行 + M7 冻结」与 roadmap 现状一致（开发线 xy064 业务成果、生产线已产出 80.6s 视频 + 449 字文章 + 真实配图；M7 仍等 Cookie）。备注：README「下一程意向」仍写「最后接 M6」，但 roadmap 已显示 M6 执行中——近况段滞后于 roadmap，目标主体对得上、局部待核。—— 出处：`docs/projects/xy/README.md`、`docs/projects/xy/roadmap.md` |
| ④ plans 完成度与 roadmap/看板声称一致 | ⚠️ 待核 | 已完成段一致（plan-001~007 已完成 = roadmap M1~M3 已完成）。不一致点：plan-008 进度 2/2 (100%) vs 状态「部分执行」、子项目 5.1-5.3 全「计划中」；plan-009 进度 5/5 (100%) vs 状态「部分执行」、roadmap 6.1-6.4 全「计划中」但依赖链已有 3/4 合入证据。→ 部分一致、M5/M6 口径矛盾需人工核清后闭合。 |
| ⑤ 卡头规范兼容（六态口径） | ✅（方案层）／待核（卡头） | plans 头部使用「部分执行 / 待排期 / 已完成」等状态词与六态口径兼容，关联卡以编号引用（xy052-069 等）；卡头实态在 `docs/dispatch/xy/`（未检出），需外核。→ 方案层 ✅，卡头待核 |

**综合建议：🔧 整改后可入**（差：② 业务仓 git/运行面独立核证；④ plan-008/009 进度口径矛盾人工核清并回写；③ README 近况与 ⑤ 卡头实态外核）。反面证据：README「当前」段称「xy062 已完成一次真实图文+视频首跑」、roadmap 09-10 有已批准执行的卡序——项目明显非僵尸、owner 明示在做（① ✅）。若②④由迁移席/老板外核通过即可转 ✅ 合格；卡头口径若与六态不符需先修正再入。

---

## 附：盘点方法备忘

- 定级主依据=方案头部「状态/进度/验收勾选」+ 关联卡合入证据 + roadmap 里程碑/子项目状态；时间证据统一取 `meta/last-commits.txt`，其中 2026-09-03 02:22:29 批量 chore 提交（清理 74 个方案悬空引用并标注已归档）仅说明该文件被归档治理触碰，非内容实质改动，不作为「现行」证据。
- 本检出根非 git 仓库（`git log` 不可执行于检出内），故门槛②一律标待核，不做硬判；证据层级区分「检出内可核（正文/时间戳）」与「转述旁证（commit hash、测试数字、launchd 状态）」。
- 拿不准处一律标「待核」，未做硬判：qb 方案编号错位、qb①/②存续与可达性、xy-plan-008/009 进度口径、M6 roadmap 子项目滞后、xy064 重开口径、README 近况滞后、两项目卡头六态实态。

CATALOG_DONE