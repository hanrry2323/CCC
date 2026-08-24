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

审查方式：v4 对抗式独立复现，不采信执行体自述；以下每条均附可复现命令/位置。

### 范围核对
- 分支 `codex/ccc072-validator-closed-card-approval-exempt`，工作树干净、与远端同步。代码 commit `741ca5b1d` 仅触 `server/board/validate.py`（+8/-2）与新增 `server/tests/test_validator_closed_card_approval.py`（+73）；回写 commit `57548df1a` 仅触本卡文件（+12/-3）。`git show --numstat` 实测白名单外零触碰。
- 未写验收区、未置已关闭（回写 commit diff 逐行核过）。

### 独立复现
1. 门禁：`python3 -m pytest server/tests/test_validator_closed_card_approval.py -q` → `.. [100%]`，退出码 0。
2. 回归：四套件 `test_board_validate/test_docgate_q1/test_card_dispatch_gate/test_card_header` → 35 passed，退出码 0。
3. 设计前提核实：`scripts/approve-merge.sh` L309-315 确在 close 时盖「> 批准：老板合入批准」章——「平台有意设计」属实。
4. 「全仓唯一校验门」声明核实：拒绝逻辑仅 validate.py L350 FORBIDDEN_HEADER_KEYS 一处；`card_header.py` L31 为 schema 登记表、`plans.py` 为方案侧读写方，均非任务卡校验方。声明属实。
5. 端到端实效（本席加测）：对 `docs/dispatch` 全量跑 `validate_cards`，与 origin/main 对照——main 上「批准」违禁错误 **87 个**（tst004/ccc068/xy059 毒化实证），本分支归 **0**；其余 error 类别逐类对照（ccc 前缀历史错 67↔66、缺回写区 1↔1、状态值非法 1↔1）零增零减，证明豁免精确、无过度豁免亦无新副作用。

### 对抗式检查（未发现 P0/P1）
- 豁免边界：经 `base_state` 归一，含括号变体（`已关闭（x）`→`已关闭`）；空状态/未知态不豁免；`审批/review/approval` 全态报错且有守卫用例锁定防扩大。
- 自盖章风险：豁免信任卡头「状态」自述，理论可自标已关闭骗豁免——但关闭动作仅人审 approve-merge 在 main 发生，且批准真值权威在账本（approve_merge ledger · 033 M6）非卡头行，出卡校验通道非安全边界；判为设计内可接受风险，非缺陷。
- 测试夹具为合成卡（clw905-907）而非真实中毒卡——已由上节第 5 条端到端扫描补证真实实效。

### severity 判定
影响面 1（单函数语义收窄+测试覆盖）/ 改动深度 1（约 10 行+新测试）/ 红线邻近 1（触校验门组件但不涉安全面/运行面/main，白名单严守）；合计 3 → 轻，无高危维度。

### 维护区核对
四问均单选实填（[否]/[无]×4，无模板占位），说明行均为一句实情；Q2 抽查属实：`docs/notes/2026-08-24-tst-lessons.md` 与 `docs/notes/2026-08-24-ccc-locale-sed-byteslice.md` 存在且内容确为 tst004 worktree / ccc068 sed 教训、非本机制。卡头=已回写。

### 备注
审查期间 origin/main 前移至 `1e22a443e`（ccc075 投递），本分支基于较早 main——正常流水节奏，合入时由管理席按流程处理，不影响本卡结论。

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
