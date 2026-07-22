# Brief: OpenCode 生命周期卡死 — 综合方案（待做）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-22-opencode-lifecycle-stall` |
| 状态 | **登记 / 待综合方案**（局部止血已合 main `f859f8e`） |
| 权威 | [`../product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「OpenCode 生命周期 · 待综合方案」 |
| 触发 | stress-matrix 10×2 + 清槽续跑（2026-07-22） |
| 负责人 | Cursor（平台）；老板拍板加并行前必须先过本 brief 验收 |

## 一句话

同仓 1 路 OpenCode 是设计；**真堵的是「任务结束了槽不放 / done 没收口 / reviewer 挂死堵 Engine」**，不是倒 20 张卡。

## 已观测症状（A–F）

见权威表。摘要：

1. **幽灵同仓互斥**：无 opencode 进程，仍「同仓已有 active opencode」。
2. **脏 result.json**：exec 日志混进 result → JSON 坏 → `.done` 却不进 testing。
3. **卫生卡走长跑**：`executor=python` 仍可能进 opencode。
4. **testing 同步堵 tick**：`claude -p` 0% CPU 时 planned 全停。
5. **列双文件 / revert 冲突**：recover 与门禁竞态。
6. **并行容量**：须看 `host-resources` p95，且须先治 1–5。

## 局部已做（非完整方案）

- `_opencode_reap` + runner/exec/hang/check_complete 收尸
- `opencode_start` / `opencode_done` 耗时埋点
- `host-resources.jsonl` + `ccc-host-resources.py` + Ops history API
- 人工清槽续跑（dbf935cd / locks / hung claude）

## 综合方案须交付（下一轮）

请 Cursor **一次给出可落地的综合设计 + 实现**，至少包括：

1. **槽生命周期状态机**：launch → running → done/fail → release；任何终态必须释 `active_tasks` + opencode slot；与进程存活解耦校验。
2. **产物契约**：`result.json` 纯 JSON；日志 → `*.exec.log`；check_complete 防御性解析。
3. **短路径硬门**：board_ops/script_seed 失败不得静默 opencode；可观测。
4. **门禁与调度解耦**：testing/reviewer 超时与低 CPU 止损；不阻塞跨仓/同仓排队的 launch 环。
5. **看板不变量**：单卡单列；FAIL 回滚与 `.ccc` 脏隔离策略。
6. **并行决策**：基于 host-resources + 卡死率的调参 runbook（先稳后加）。

## 验收

同仓连续多卡压测：无幽灵延后、无脏 result 卡死、卫生卡不进 opencode、reviewer 挂不死 Engine、`opencode_done.wall_min` 可汇总。

## 非目标

- 取消同仓 1 路互斥（`opencode.db` lock 仍在）
- 用「加大 MAX_CONCURRENT」代替修生命周期
