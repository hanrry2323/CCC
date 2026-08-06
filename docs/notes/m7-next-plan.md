# M7 方案（待审批后执行）

> 北星不变。冻结心智补丁。

## 目标

消化 ready 队列（xy002），并补齐「外仓业务卡」合入路径缺口（CCC 关卡 ≠ xianyu ff）。

## 范围

1. **xy002 合入批准**：听老板口令后 `approve-merge.sh xy002`（CCC 卡关闭）；同步确认 xianyu `codex/xy002-*` 是否 ff 入业务 main（脚本提示或一行外仓 merge helper，≤30 行，不写 SOP）。
2. **外仓合入提示**：`approve-merge` 在 `project=xy`（或 registry 标外仓）时打印 xianyu 分支/HEAD 一行，避免只关卡漏合业务码。
3. **静默绿抽查**：ready 空时抽查 `/board/ready_for_merge` count=0；有卡时 machine_audit_passed 全 true。
4. **回归**：既有 pytest。

## 不做

新席位/同义句/Hub/Desktop/Agent SOP。

## 验收

| 指标 | 门槛 |
|------|------|
| 老板调度 | ≤2 |
| xy002 已关闭或明确挂账 | 是 |
| 外仓合入提示或 helper | 有（若本批合入 xy） |
| 新 SOP | 0 |
