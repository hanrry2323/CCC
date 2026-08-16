# CCC 治理债登记（延后处理 · 2026-08-16）

> 性质：只读登记，**全部延后**，暂不合并/不修复。来源：2026-08-16 两轮第三方审计核验后，确认属实的制度/文档层不一致。
> 处理节奏：等攒量或专门排期统一收敛；其中 G2 需老板拍板方向。

## 架构级（本轮审计确认属实 · 触制度地基）

### G1 · 状态机机审位置冲突 + 五态/六态 doc-sync
- **冲突**：PRIME-DIRECTIVE `docs/CCC-PRIME-DIRECTIVE.md:80` 图示为 `执行中 → 机审 → 已回写 → 已关闭`（机审在回写**前**）；代码 `server/engine/task.py:31` 六态枚举、机审在状态机**外**（DONE→CLOSED 触发，失败 `已回写→待分派`）；`docs/architecture.md:172` 五态、机审在回写后。机审位置三种说法。
- **实质**：文档 vs 文档冲突；代码自洽且是运行时权威。属「契约自洽债」。
- **修复方向（后置）**：统一机审位置表述（建议 `已回写→机审→已关闭`，机审非状态、是状态间触发）；`architecture.md:172`、`task.py:3` 注释 五态→六态（作废 8-14 已加）。

### G2 · 异席隔离 vs 自验收 制度冲突（需老板决策方向）
- **冲突**：ENGINEERING-CANON `docs/ENGINEERING-CANON.md:59`「异席机审（硬）写的人不审自己」+ 全局 CLAUDE.md 红线「执行席/验收席分离」；DOC-PROTOCOL `docs/DOC-PROTOCOL.md:83` 现行却是「自验收：谁开发谁验收」。validate 甚至把跨工具验收（OpenCode 开发+Claude 验收，更符合异席）标为「验收不匹配」。
- **实质**：安全红线与现行流程矛盾，二选一。
- **修复方向（后置 · 老板拍板）**：要么红线让步改「同工具异角色」为现行口径；要么流程拉回异席隔离。

## 存量/门禁（前轮审计 · 延后）

### G3 · 59 张 ccc 卡违反前缀禁令未豁免
- validate 常年报 59 error（`前缀 'ccc' 禁止走 CCC`），均为 8-06~8-10 存量已闭环卡。
- 修复方向（后置）：豁免名单或迁 `docs/archive/`。

### G4 · 全量 validate 未接入 approve-merge
- `scripts/approve-merge.sh` 只跑 Doc-Gate 维护区校验（`verify_maintenance`），不跑全量 `server.board.validate` → 红灯可合入。
- 修复方向（后置）：approve-merge 对目标卡挂全量 validate（error 阻断）。

### G5 · test_real_dispatch_cards 状态白名单缺「作废」态（2026-08-17 新增）
- **现象**：`server/tests/test_board_loader.py:175` 断言 `base_state(item.state) in {待分派,执行中,已回写,已关闭,打回,未知}`，缺 `作废`；hp009 卡状态「作废（任务本身高风险…）」触发失败（8-16 卡作废，括号变体归并后为 `作废`）。
- **根因**：`base_state()` 归并逻辑正确（括号前基础态），是**测试白名单过时**——「作废」是卡合法终态，08-02 验收记录 `docs/acceptance-full-2026-08-02.md` P1-1 已提「状态断言未按基础态」同源线索，未修。
- **修复方向（后置）**：白名单补 `作废`（与卡状态机六态一致），或断言改读 `VALID_STATES` 常量。

---
**关联**：`docs/notes/2026-08-16-clw-lessons.md`（封板收尾清单教训）
