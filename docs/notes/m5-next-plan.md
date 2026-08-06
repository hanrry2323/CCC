# M5 方案（待审批后执行）

> 北星不变。冻结心智补丁。

## 目标

现网 Engine 真机审闭环（少用 evidence 补录），并消化执行中积压（如 xy002）。

## 范围

1. **真机审狗粮**：对一张新小卡走 Engine `--audit`（或回写后自动机审），不经 `first-audit-evidence`。
2. **xy002**：看板「执行中」——取证后推进回写/机审/合入或打回挂账。
3. **close-only 降频**：统计近一周合入；若 close-only > ff，在出卡模板加一行 rebase 提醒（≤3 行，不写新 SOP）。
4. **回归**：既有 pytest 套件 + `new-card --project cd --dry-run`。

## 不做

新席位/同义句/Hub/Desktop。

## 验收

| 指标 | 门槛 |
|------|------|
| 老板调度 | ≤2 |
| 至少 1 次 Engine 真机审落盘 | 有 audit.log + 机审区 |
| 新 SOP | 0 |
