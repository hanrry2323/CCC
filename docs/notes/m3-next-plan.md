# M3 方案（待审批后执行）

> 北星不变。冻结：不写 Agent 心智补丁。Done = 脚本/API/pytest。

## 目标

让 **ready_for_merge → 合入批准** 在现网可每周狗粮一次，且机审列不再积压「通过但未落盘」尸卡。

## 范围（竖切）

1. **滞留机审清账**：对看板「机审」列中 audit.log 已通过的卡，跑一次 Engine 补落盘或受控脚本（基于 ccc006），进入 ready。
2. **Console / 看板露出 ready**：控制台「已回写待合入」优先拉 `GET /board/ready_for_merge` 列表（短改 JS，无新 SOP）。
3. **合入批准狗粮**：对 ready 队列至少一张卡走 `scripts/approve-merge.sh`（人审 diff 后）。
4. **回归门**：`pytest server/tests/test_engine_audit_backfill.py` + `test_ccc_plan.py` + `test_project_registry.py` 进日常自检习惯（不扩 CI 哲学文）。

## 不做

- 新席位表 / 验收同义句 / Hub 复活
- Desktop 主对话面

## 验收数字

| 指标 | 门槛 |
|------|------|
| 老板调度 | ≤2（批 M3 + 合入批准） |
| 机审列「假滞留」（log 通过卡无区） | 0 |
| 新 SOP 文件 | 0 |
