# 异常任务：解决问题 SOP（非清障结案）

> **权威**：`docs/product/loop-engineer-authority.md`「编排自愈硬指标」  
> **硬口径**：**清障 ≠ 解决问题**。`clear_blockers` / reopen / 归档只是步骤里的清理；**结案必须是根因被改掉且意图再次可验收**。  
> **禁止**：把「已归档 / 已 reopen / 已藏卡」当向老板的完成话术；禁止只解释清障逻辑而不出优化定稿。

## 什么叫「解决了」

| 状态 | 算解决？ |
|------|----------|
| 只 `clear_blockers` / reopen | **否** |
| 归档进 quarantine 并口头解释「耗尽不可恢复」 | **否**（除非紧接着优化定稿且人确认入队） |
| 读证据 → 按失败桶改任务拆解 → 新 `ccc-transfer` 入队 → Engine 跑绿 | **是** |
| 盘上代码已绿但卡仍 abnormal：补门禁/结算到 testing→released（或合法 stamp commit） | **是** |

## 固定顺序（硬）

1. **取证**（勿先讲故事）  
   `hub_repair(status|failure_pack)` + 读 `review_fail` / `result.json` / quarantine / `git log --grep=<tid>`  
2. **定桶**（hang / acceptance_fail / dirty_block / phase_unresolvable / fail_loop …）  
3. **人话 ≤3 句**：失败因 + **意图是否仍成立** + 下一步是改卡还是结算已绿代码  
4. **分支**  
   - **盘上已满足验收**（有含 `task_id` 的 commit 或验收命令现跑全绿）→ **结算/salvage 进 testing**，禁止再「缩小重投」空转；缺 commit 则补合法 stamp，不重开巨型 OpenCode。  
   - **未满足** → 可恢复则 reopen；耗尽则 `clear_blockers` **之后必须**出优化 `ccc-transfer`（见 [`post-exhaust-epic-optimize-sop.md`](post-exhaust-epic-optimize-sop.md)）。  
5. **dirty_block / `.ccc`·`docs/lessons` 噪音** → 不当业务失败结案；先认噪音门禁，再让同卡过 commit-gate（详见 [`commit-folder-hygiene-sop.md`](commit-folder-hygiene-sop.md)）。  
6. 回报老板：用「根因 / 已改什么 / 现在板况」；**禁止**长篇辩护清障流程。

## 与清板 / L3b / 卫生的关系

- [`board-auto-repair-sop.md`](board-auto-repair-sop.md) = 板面卫生（reopen/归档）  
- [`post-exhaust-epic-optimize-sop.md`](post-exhaust-epic-optimize-sop.md) = 耗尽后**改大卡**  
- [`commit-folder-hygiene-sop.md`](commit-folder-hygiene-sop.md) = **commit 范围 + 文件夹/脏树怎么解释与处理**  
- **本文 = 异常总闸**：任何异常路径都必须落到「问题解决」定义上；其余文是手段不是终点。
