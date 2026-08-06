# M7 方案（待审批后执行）

> 北星不变。冻结心智补丁。  
> 前置已完成：xy002 CCC 关卡 + xianyu ff→main（`95e87d4` / `dbd1ef2`）。看板现空。

## 目标

补齐外仓合入提示缺口，并用一张小 `ccc-plan` 狗粮验证「确认方案 → 拆卡 → 静默 → 合入批准」整链（老板调度 ≤2）。

## 范围

1. **外仓合入提示**：`approve-merge.sh` 读卡头 `项目` + `docs/projects/registry.yaml` 路径；若有 `mac2017` 外仓路径，打印一行「业务仓分支/HEAD / 是否已在 main」（不自动 push 外仓，除非本批明确可 ff）。
2. **ccc-plan 狗粮**：写一份 ≤2 slice 的小 plan（平台侧、白名单窄）→ `plan-to-cards.sh` 入队 → 等 Engine 回写+自动机审 → ready 后停手等人审「合入批准」。
3. **回归**：既有 pytest + `approve-merge --help`/干跑提示抽查（无 ready 时不误关卡）。

## 不做

新席位/同义句/Hub/Desktop/Agent SOP；不扩大 xy 业务范围。

## 验收

| 指标 | 门槛 |
|------|------|
| 老板调度 | ≤2（批 M7 + 合入批准） |
| 外仓提示 | approve-merge 对 xy 类卡有一行外仓信息 |
| plan→ready 狗粮 | ≥1 卡进过 ready（或明确 RED/打回挂账） |
| 新 SOP | 0 |
