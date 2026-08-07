# M4 方案（待审批后执行）

> 北星不变。冻结心智补丁。Done = 脚本/API/pytest。

## 目标

清掉「尚无机审 log」的真实待审卡，并让分叉分支的合入批准可常规化（少用人工 `--close-only`）。

## 范围

1. **首跑机审**：对 `ccc005`/`ccc006`（及同类）触发 Engine 机审或受控重放，使进入 ready（非假滞留补录）。
2. **ccc004 合入批准**：ready 队列余卡走 `approve-merge`（能 ff 则 ff；否则审 diff 后 close-only）。
3. **分支卫生**：文档约定「回写后定期 rebase origin/main」，减少分叉；可选 `approve-merge` 提示 rebase。
4. **回归**：沿用 `test_engine_audit_backfill` + `test_ccc_plan` + `test_project_registry` + loader audit 缓存测。

## 不做

新 SOP / 席位表 / Hub / Desktop 主路径。

## 验收

| 指标 | 门槛 |
|------|------|
| 老板调度 | ≤2 |
| ready 积压无「代码已在 main、只差关卡」超 48h | 0（或挂账一行） |
| 新 SOP | 0 |
