# 方案 · 质量与真伪机械验证体系（L1-L3 三层质量评估 + 门禁硬化）

> 项目：ccc · 编号：ccc-plan-042 · 状态：已确定 · 作者：ox-alpha/DSH（外脑席·S140@M1）· 工具：DSH
> 创建：2026-08-22 · 更新：2026-08-22
> 关联卡：无（平台自研红线适用，M1 主窗口直接开发 + Claude Code 异席机审，不走 engine 派发）
> 关联方案：ccc-plan-040/041（断点修复前置）、ccc-plan-039（螺旋评审）、ccc-plan-035（机审区格式契约）
> 依据：2026-08-22 两轮硬化实测核实（cf4f2cac / 22e83b7f）+ 质量基线扫描（232bee30）+ hp049-052 空模板假关闭实锤
> 里程碑：标准化体系加固
> 子项目：无（独立方案，非里程碑子项目）
> 环境准备：radon/mypy 已装 ✅；2017 审计复跑环境（已有 exec 日志与 ledger）✅；Claude Code 异席通道 ✅

## 目标

把 CCC 流水线从「只评合规」升级为「评质量、验真伪」：每一张卡的交付物产出**可量化的质量分**，每一次「完成/通过」声明都经过**机械验证或独立复跑**，让伪造与空转在源头被机器拦截，而不是靠机审/人审事后兜底。

## 背景

2026-08-22 全天审计（Claude Code 两轮硬化 + DSH 独立复核）确认系统性根因：**平台到处信任声明，不做机械验证**。

已实锤的证据链：

| 证据 | 实测 | 性质 |
|------|------|------|
| hp049-052 空模板假关闭 | 卡 148 行纯占位（实现/验收一字未填）、代码不在 main、状态已关闭 | 声明即通过 |
| 测试空转 | 平均断言/测试 2.3；22 个测试文件 <2；高 mock 低断言组合（test_engine_task 0.8）| pytest 全绿但零拦截力（xy056/057 教训同源）|
| 机审内容盲区 | P0-3 后 flag 真值来自 ledger，但「机审本身判得准不准」无任何度量 | 谁来审机审？ |
| 假回滚缺陷（22e83b7f 引入）| approve_one 先 merge（L135 ff-only）后写账本；账本失败仅 checkout 卡文件——代码已在 main 撤不回，索引仍记已关闭 | 新改动的次生洞 |
| 双机台账滞后窗口 | 机审判定读本机 ledger；engine 落账在 2017、approve-merge 在 M1，仅在合入瞬间同步一次 | 同卡两机判定可能不一致 |
| 异席机审缺位 | cf4f2cac + 22e83b7f 两轮平台大改未经 Claude Code 复核直接上生产 2017 | 自审自证复发 |

质量基线已建（`docs/notes/2026-08-22-code-quality-baseline.md`）：server/ 核心 47 文件 2.4 万行——11 个 D/E/F 高复杂度热点（8 个集中在 `_APIHandler` 上帝对象）、mypy 273 错/25 文件、266 组重复块。「增量不可劣化」门禁自此有了参照系。

## 方案内容（四个里程碑，串行推进）

### M0 · 止血：堵掉本轮新引入的三个洞（0.5 天）

1. **修真回滚**：`approve_one` 动作顺序改为 `写账本 → merge → close_card → 刷索引`；任一步失败即 `git reset --hard ORIG_HEAD` 撤销 merge + 还原工作树，保证「要么全成、要么全无」。补失败重现用例（mock record_action 抛错 → 断言 main 无 merge 提交）。
2. **双机台账一致性**：`sync-audit-ledger.py` 从「合入时拉取」升级为双向对齐（M1↔2017 并集互同步），并在 engine 每次 `machine_audit_pass` 落账后异步触发一次同步（失败静默，下次补偿）；看板 API 读账本前若 mtime 距今 >10min 先尝试同步。
3. **异席机审硬约束**：approve-merge.sh 增加检查——本次待合入 diff 若触及 `server/engine|board|scripts` 平台自研路径，要求 ledger 存在本卡 `cross_review_pass` 记录（Claude Code 交叉复核后落账），缺失=拒绝。把红线从文档变成机器门禁。

### M1 · L1 机械指标层：每卡自动出分（2 天）

新增 `scripts/quality-score.py`：对单卡 diff 自动计算五项指标，写入 ledger（action=`quality_score`），看板卡片详情展示。

| 指标 | 工具 | 判读 |
|------|------|------|
| 断言密度 | AST 统计 assert/expect vs mock 数 | <2 = 空转嫌疑 |
| mock 占比 | AST 统计 | >50% = 自说自话嫌疑 |
| 圈复杂度增量 | radon 对 diff 函数 | 新增 D/E/F = 打回 |
| mypy 增量错误 | mypy 对 diff 文件 | 净增 = 打回 |
| 重复块增量 | 指纹法（基线脚本已有） | 净增 = WARN |

门禁规则：**新卡总分 ≥ 同模块基线分**（增量不可劣化）；分数进 ledger 单一事实源，卡文自写无效（复用 P0-3 的 `_machine_audit_ok` 同款机制）。基线 = 232bee30 报告的数字。

### M2 · L2 真跑验证层：关键卡强制独立复跑（2 天）

- 「验收标准」含可执行命令的卡，回写时必须附**产物证据**（命令输出 hash / 截图 / 文件 hash），由 engine 在 2017 审计环境**独立重放**该命令比对结果，不信执行体自报。
- 重放结果落 ledger（action=`replay_verify`）；重放失败自动打回，理由自动生成。
- 非确定性命令（时间/网络相关）允许声明豁免，豁免清单进方案备注、机审抽查。

### M3 · L3 rubric 评审层 + 上帝对象治理排期（1 天方案 + 排期）

- 机审席按固定评分表打分（架构一致性/错误处理/命名/测试有效性四维，各 1-5 分），每分必须附文件:行号证据；总分 <12 自动打回。评分表落 `docs/notes/review-rubric.md`。
- `_APIHandler` 拆分（8/11 个高复杂度热点所在）体量大，**不在本方案内实施**——单独立项排期，本方案只锁定其增量复杂度不得再涨（M1 门禁覆盖）。

## 功能卡（拆解规划；实际执行按平台自研红线走 M1 主窗口 + Claude Code 异席，不经 engine）

### M0-1 真回滚改造

目标：merge 与记账原子化，失败全量回滚。
实现：调整 approve_one 顺序为账本先行；失败路径 git reset --hard ORIG_HEAD。
验收：构造 record_action 失败场景，main 无残留 merge 提交、索引与卡文件一致。
颗粒度：approve-merge.sh 单文件 + 1 个测试。
依赖：无。
架构位置：scripts/approve-merge.sh 合入主路径。

### M0-2 台账双向对齐

目标：双机 ledger 最终一致，消除判定漂移窗口。
实现：sync 脚本改并集互同步；engine 落账后异步触发；看板读前新鲜度检查。
验收：两机各自落一条记录后 ≤1min 内双方均可读到对方记录。
颗粒度：sync-audit-ledger.py + engine main 一处钩子。
依赖：M0-1。
架构位置：data/audit/ledger.jsonl 同步链路。

### M0-3 异席门禁硬约束

目标：平台自研路径改动强制 Claude Code 交叉复核留账。
实现：approve-merge 按路径匹配触发 cross_review_pass 校验。
验收：构造触及 server/engine 的卡无 cross 记录 → 硬拒绝。
颗粒度：approve-merge.sh 一段 + 1 测试。
依赖：无。
架构位置：合入门禁链。

### M1-L1 每卡质量分

目标：五项机械指标自动出分入账，增量不可劣化。
实现：quality-score.py + ledger action=quality_score + 看板详情展示 + 门禁接入 approve-merge。
验收：对含低断言高 mock 测试的样例卡出低分并被门禁拦截；对正常卡出分放行。
颗粒度：新脚本 + loader/approve-merge 各一小段 + 看板一段。
依赖：M0-3。
架构位置：质量评分旁路（ledger 同源）。

### M2-L2 独立复跑

目标：验收命令由审计环境重放，证据不可自报。
实现：回写区解析「验收命令」→ engine 重放 → replay_verify 入账。
验收：伪造输出 hash 的卡被重放打回；真实卡重放一致放行。
颗粒度：engine 一个 verify 模块 + 回写区格式约定一段。
依赖：M1-L1。
架构位置：engine 执行体→审计链路。

### M3-L3 rubric 评审表

目标：机审从「过没过」到「好不好」，低分自动打回。
实现：评分表文档 + ledger action=review_rubric + 机审提示词注入评分要求。
验收：评分 <12 的样例被打回且理由带行号证据。
颗粒度：文档 + main.py 机审 prompt 段 + ledger 一行。
依赖：无（可与 M1 并行）。
架构位置：机审席工作流。

## 验收标准

- [ ] M0：构造账本写失败 → main 无 merge 残留、卡文件与索引一致（失败重现用例转绿）
- [ ] M0：双机各自落账后 1 分钟内互见（SSH 实测两条记录）
- [ ] M0：触及 server/engine 的合入缺 cross_review_pass → 退出码非零拒绝
- [ ] M1：样例低质卡（断言<2 且 mock>50%）被门禁打回，正常卡放行；分数可在看板详情看到
- [ ] M2：伪造产物 hash 的卡被独立重放识别并自动打回
- [ ] M3：rubric 低分样例自动打回且理由含文件:行号
- [ ] 全程 CI 绿 + ruff 零告警 + 覆盖率 ≥84% 不降
- [ ] 本方案自身经 Claude Code 异席机审通过后才开工（吃自己的狗粮）

## 备注

- 明确排除：27 方案拍板归老板；`_APIHandler` 拆分另立项；P3 架构遗留（sidecar/跨节点路由/role-skills）按 `2026-08-22-p3-architecture-schedule.md` 排期。
- mutation 抽检暂缓：成本高，待 M1 断言密度指标跑通后再评估是否引入。
