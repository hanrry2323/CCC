# qb 定卡反模式（Agent 培养 · 非用户说明书）

> 注入：`project_brain`（`project_id=qb`）或权威仓 `.ccc/agent-mind/transfer_playbook.md`  
> 关联：`transfer_gate` · `post-exhaust-epic-optimize-sop` · `abnormal-solve-sop`

| 反模式 | 正模式 |
|--------|--------|
| Step1–6 / 多 phase 一把梭 → hang | 1 work + 1 phase + 少数文件 scope |
| goal 要 CLOSE，plan「交给上层」 | plan 写清 CLOSE_* + 仓位；过 `plan_goal_conflict` |
| `test -f` / 散文验收 | pytest / `python3 -c` assert / `DRY_RUN=…` |
| 脏树=.ccc/lessons 当业务失败 | `ccc_hygiene`；禁卫生 epic |
| `## 验收清单` 当验收 | 精确 `## 验收` + 白名单命令 |
| 验收已绿仍重构 | 立即 commit（含 `task_id`）并停 |
| 耗尽后原样重下 | 读 `optimize_hint` 缩小/修探针再 `ccc-transfer` |
