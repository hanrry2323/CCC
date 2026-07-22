# Brief: stress-mx 效率 — 止损后快照 + 方案落地摘录

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-22-stress-efficiency-closeout` |
| 关联 | [`2026-07-22-stress-efficiency-eval.md`](2026-07-22-stress-efficiency-eval.md) · [`2026-07-22-opencode-lifecycle-stall.md`](2026-07-22-opencode-lifecycle-stall.md) |
| 状态 | **方案已落地平台**；终稿数字等缩小压测复跑 |

## P0 止损后（2026-07-23 ~00:31）

- qb：`git revert --abort` 成功，无 `REVERT_HEAD`
- FAIL testing 三件套 → planned；Engine kickstart 后重新取卡
- 效率快照仍显示历史排队（queue_wait p95≈7319s）——属**方案前**累积，不代表 P1–P5 后效果

本地副本：`docs/briefs/2026-07-22-stress-efficiency-post-p0.md`

## P1–P5 勾选

| 项 | 状态 |
|----|------|
| 槽终态必释 / 死 pid+.done 不挡 | ✅ |
| result 纯 JSON + exec.log + 防御解析 | ✅ |
| FAIL revert 必 abort | ✅ |
| testing 限预算 + 先 launch | ✅ |
| 短路径硬门 + path 埋点 | ✅ |
| 忙时≥30 再谈并发+1 | ✅（host summarize） |

## 下一步（验收总闸）

2017 已热更代码并 kickstart Engine 后：每仓 3–4 张缩小压测 → 再跑

```bash
python3 scripts/ccc-stress-efficiency-report.py --run <tag>
```

期望：queue_wait p95 降到分钟级；无半截 revert；`dev_path` 可见；`duration_s` fill_rate >90%。
