# qb 定卡反模式（Agent 培养 · 非用户说明书）

> 注入：`project_brain`（`project_id=qb`）或权威仓 `.ccc/agent-mind/transfer_playbook.md`  
> 细则：`references/intent-card-sop.md` · `transfer_gate` · `post-exhaust-epic-optimize-sop`

| 反模式 | 正模式 | 真实失败 |
|--------|--------|----------|
| Step1–6 / 多 phase 一把梭 | 1 work + 1 phase + ≤5 文件 scope | hang |
| goal 要 CLOSE，plan「交给上层」 | plan 写清 CLOSE_* + 仓位 | `plan_goal_conflict` |
| `test -f` / 散文验收 | 本卡 pytest / `python3 -c` assert | `acceptance_weak` |
| **unit 改码卡顺带 `paper_intent_probe` / 60s e2e** | 探针另开 L1 卡；本卡只留 fees/corner pytest | `…5f90684d` salvage/`acceptance_cmd_failed`/hang |
| acceptance 塞满 5～10 条重复命令 | **1～2** 条强探针 | 门禁噪 + salvage 拒 |
| 脏树=.ccc/lessons 当业务失败 | `ccc_hygiene`；禁卫生 epic | 脏计数吓人 |
| `## 验收清单` 当验收 | 精确 `## 验收` + 白名单命令 | 假绿 |
| 验收已绿仍重构 | 立即 commit（含 `task_id`）并停 | revert↔restore 噪音 |
| 耗尽后原样重下 | 读 `optimize_hint` 缩小/修探针再 `ccc-transfer` | 死循环 |
| id/标题像戳记·冒烟当主业 | 只下产品意图 epic | 垃圾板 |
