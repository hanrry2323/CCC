# 任务卡 ccc072 · 卡头校验器语义修复——已关闭卡豁免「批准」章（DSH 执行）

> 关联：无方案（2026-08-24 债务清偿 · 老板指令直派） · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

消除平台组件自相矛盾：approve-merge 人审节点③在每张卡关闭时盖「> 批准：老板合入批准」于卡头（close_card 有意设计），而 server/board/validate.py L343-348 无条件将「批准」列为违禁卡头字段 → 每张新合并卡瞬间毒化所属项目出卡校验通道（tst004/ccc068/xy059 实证）。修复=对「已关闭」卡豁免「批准」键检查；未关闭卡仍严格报错；其余违禁键不变。

## 实现

白名单：server/board/validate.py、server/tests/test_validator_closed_card_approval.py（新增）。

1. validate.py：FORBIDDEN_HEADER_KEYS 循环前取卡头状态，base_state 为「已关闭」时跳过「批准」键检查（「审批/review/approval」仍全态报错）；注释引用人审节点③设计（scripts/approve-merge.sh close_card）与本卡。
2. 新增测试两张 tmp 卡夹具（唯一差异=状态 已关闭 vs 待分派，均含该行）：断言前者零 issue、后者含对应 issue。
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 仅按实现节条件豁免，禁止扩大豁免范围。
3. 禁写机审区/验收区/置已关闭。

## 步骤

1. Read 本卡全文与相关代码/文件现状。
2. 按实现节修改；自测运行下方门禁命令，退出码必须=0。
3. commit+push 到本分支（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区；维护区四问——勾选符落在问题行方括号内，说明行一句实情。
5. 停手等机审。

## 验收标准

1. 门禁命令真实退出码=0（wrapper 证据日志为准）。
2. 白名单外零触碰。
3. 卡头=已回写；维护区四问非占位。

## 门禁

测试：cd /Users/fan/program/CCC-wt/ccc072 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_validator_closed_card_approval.py -q

## 回写区

**实现说明**（执行体：DSH · 2026-08-24）：
1. `server/board/validate.py`：FORBIDDEN_HEADER_KEYS 循环前新增 `approval_exempt = base_state(meta.get("状态", "")) == "已关闭"`；「批准」键仅在已关闭卡豁免，`审批/review/approval` 全态报错、未关闭卡仍严格报错；注释引用人审节点③设计（`scripts/approve-merge.sh close_card`）与本卡 ccc072。豁免条件未超出实现节范围。
2. 新增 `server/tests/test_validator_closed_card_approval.py`：两张 tmp 卡夹具（clw 子目录新规则卡 clw905/clw906，内容同构、唯一差异=状态 已关闭 vs 待分派，均含 `> … · 批准：老板合入批准` 行）——断言已关闭卡零 issue、待分派卡恰一条「批准」违禁字段 error；另加守卫用例锁定已关闭卡的 `审批/review` 仍报错（防扩大豁免）。

**自测结果**：
- 门禁命令：`cd /Users/fan/program/CCC-wt/ccc072 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_validator_closed_card_approval.py -q` → 输出 `.. [100%]`，真实退出码=0。
- 回归面：`python3 -m pytest server/tests/test_board_validate.py server/tests/test_docgate_q1.py server/tests/test_card_dispatch_gate.py server/tests/test_card_header.py -q` → 35 passed，退出码=0。
- 全仓唯一违禁键校验门即 validate.py FORBIDDEN_HEADER_KEYS（grep 证实 card_header/plans 中「批准」均为读写方非校验方），无第二处需同步修改。

**push 证据**：分支 `codex/ccc072-validator-closed-card-approval-exempt`；代码 commit `741ca5b1d`（fetch+rebase origin/main 后 up to date，push 成功新建远端分支，PUSH_EXIT=0）；回写 commit 见本分支下一条。

## 机审区

（验收席专用——执行体禁止写入）

**DSH 机审席 · 2026-08-24 · severity：轻**

审查方式：v4 对抗式独立复现（本卡第 3 次独立派发机审），不采信执行体自述亦不采信前席记录；结论仅基于本席亲跑命令与实测数字。

> 溯源：本分支机审区此前已有多条记录（并发写入 `84b8a3f9` 后被 `9d23d9de5` 取代，另有 `3d8f0da5c`/`d8d00f288`），结论均为通过。本席对其全部实质主张逐条重验为真后，以本节取代之，保证卡内仅一条机审结论行；同卡多派发竞态报引擎核查（见流程事件记录）。

### 范围核对（白名单外零触碰）
- 分支独有提交恰 5 条（`git log origin/main..HEAD`）：开发提交 `536dc04ca` 仅触白名单两文件——`server/board/validate.py`（+8/-2）+ 新增 `server/tests/test_validator_closed_card_approval.py`（+73）；回写提交 `41b2f5a81` 仅触本卡文件（+12/-3）；其余 3 条为机审记录提交，numstat 均仅触本卡文件。
- 卡内无「## 验收区」（grep 计数=0）、卡头状态仍=已回写、未置已关闭；工作树干净（`git status --short` 空）。

### 独立复现（全部本席亲跑）
1. 门禁：`python3 -m pytest server/tests/test_validator_closed_card_approval.py -q` → `.. [100%]`，退出码=0。
2. 回归：test_board_validate / test_docgate_q1 / test_card_dispatch_gate / test_card_header 四套件 → 35 passed，退出码=0。
3. 业务前提：`scripts/approve-merge.sh` L309-310/L315（人审节点③）确在关闭时于卡头盖/更新「> 批准：老板合入批准 · 日期」章——「平台有意设计」属实，豁免方向正确。
4. 「全仓唯一校验门」声明核实：FORBIDDEN_HEADER_KEYS 全仓仅 validate.py L350 一处（grep）；card_header.py L31 为读写方 schema 登记、plans.py 的「批准」行为方案文档读写方、audit_ledger.py 为批准真值账本（033 M6），均非卡头校验方。出卡链路 new-card.sh L442 / plan-to-cards.sh L189 / validate.py CLI L577 同走 `validate_cards`，豁免全链路一致生效。
5. 端到端实效（`git archive origin/main` 导出完整旧树；models.py 两树 diff 一致，效果纯归因 validate.py 单文件）：同一份 main 卡树，main 版校验器报「批准」违禁 error **87** 条 → 换入分支版 validate.py 同输入实测 **0** 条，其余 error 类别逐条一致（ccc 前缀错 67↔67、缺回写区 1↔1、状态值非法 1↔1）；两树各跑各自卡树总 issue 数 224→137 差值恰=87；warn（执行体不可开发 1/2、验收不匹配 65）两树完全一致。豁免精确命中，无过度豁免、无新副作用。
6. 边界探针（本席合成卡亲测）：`已关闭（合并）` 括号变体→豁免生效零 issue；已关闭+审批/review/approval 三键并存→三键全数报错且不报「批准」（补齐测试未覆盖的 `approval` 键实证）；`已回写` 卡带批准章→仍报错；无状态键→默认严格报错。归一逻辑 `base_state` 见 models.py L52-63（空/未知→未知≠已关闭）。

### 对抗式检查（未发现 P0/P1）
- 自盖章风险论证：豁免信任卡头「状态」自述，理论可自标已关闭骗豁免——但置已关闭仅人审 approve-merge 在 main 发生，批准真值权威在 approve_merge/audit_ledger 账本而非卡头行，出卡校验通道非安全边界；判设计内可接受风险，非缺陷。
- 测试夹具为合成 tmp 卡（clw905-907）非真实中毒卡——由上第 5 条同输入对照补证真实实效。
- 非阻断小项：守卫用例未覆盖 `approval` 键变体（逻辑为集合成员判断，风险≈0，本席探针已补证其仍报错）；维护区 Q3/Q4 说明仅「[否]。」偏简但合规（见下）。

### severity 判定
影响面 1（单校验门语义收窄+新增测试）/ 改动深度 1（约 10 行改动+测试）/ 红线邻近 1（触校验门组件但白名单严守、门禁双绿复现、不涉安全面/运行面/main 直推）；合计 3 → 轻，无任一高危维度（强制重条件不触发）。

### 维护区核对（P1-b 机械判据）
四问问题行均单选实填（[否]/[无]；全文 grep `[是/否]`/`[有/无]` 占位仅命中原机审记录的引用性反例，维护区本体零占位），说明行非空非占位且抽查属实：Q1 与卡头「关联：无方案」一致；Q2 引用的 `docs/notes/2026-08-24-tst-lessons.md` 与 `docs/notes/2026-08-24-ccc-locale-sed-byteslice.md` 实测存在；Q3/Q4 经 numstat 证实未动项目结构/roadmap。卡头=已回写 ✓。

### 流程事件记录（不影响本卡代码结论 · 报引擎/管理席核查）
本卡今日被多次派发机审（`84b8a3f9` 并发写入、`3d8f0da5c`、`9d23d9de5`+`d8d00f288`、本次），属同卡多派发竞态，建议引擎侧派发去重。口径备注：前席记录 warn 写作四类 1/2/2/63，本席按 reason 前缀粗粒度实测为三类 1/2/65（合计同为 68、两树零增减），系分类粒度差异，不影响任何结论。

机审：通过

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：[否]。债务清偿直派卡无关联方案。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：[无]。机制与设计依据已固化于 validate.py 注释与本卡目标节；卡白名单未含 docs/notes，未新增笔记文件（实测同期 notes 记的是 tst004 worktree 与 ccc068 sed 教训，非本机制）。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：[否]。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：[否]。
