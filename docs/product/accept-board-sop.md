# 合入批准（旧称「验收看板」）

> **人工兜底通道 · 2026-09-04**：默认合入链已由 phase2 自动取代；本文件保留为人工兜底/老板否决的别名入口。权威流程见 [`north-star-slice.md`](north-star-slice.md)。  
> 质量门 = 机械门禁 + CI + 机审 exit code（绿静默）。人只审 **diff** 后说 **「合入批准」**。

## 触发语

**首选**：`合入批准`  
**别名（同动作）**：`验收看板` · `验收回写` · `终验看板` · `验收已回写` · `验收已回写卡片`

听到任一 → **不要**做 31 分钟验收考古；执行：

```bash
# 1) ready 队列（端点见 docs/deploy/topology.md，不写死机器名/端口）
curl -s "$CCC_BOARD_URL/board/ready_for_merge"   # CCC_BOARD_URL 见 scripts/card-evidence.sh 默认值

# 2) 取证（禁 /tmp merge）
scripts/card-evidence.sh <card-id>

# 3) 合入 + 关卡
scripts/approve-merge.sh <card-id>
# 或批处理：scripts/approve-merge.sh --ready
```

## 可合入条件

`board_column=已回写` 且 `machine_audit_passed=true`（= ready 队列）。  
仍在「机审」列 → 报卡号后停手，不代写 `## 机审区`。

## 禁止

- 自认 2017 机审席 / 改写 `## 机审区`
- `/tmp` merge 考古、满仓 grep 当进度真值
- 把「流程口令」当质量门（质量已由机审判定）
- 为教 Agent 再堆同义句/席位 SOP（见 INDEX §0 反目标）

机审流程仍见 [`machine-audit-flow.md`](machine-audit-flow.md)。
