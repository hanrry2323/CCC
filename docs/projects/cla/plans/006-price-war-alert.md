# 方案 · 招采降价预警与 Jobs 自动化触发（M2-2.3）

> 项目：cla · 编号：cla-plan-006 · 状态：部分执行 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-18（红线修正：删 mock 假数据表述，预警判定改 gov 历史价对比）
> 关联卡：cla020
> 关联方案：cla-plan-005（gov 数据）、cla-plan-008（电商数据）
> 里程碑：M2 · 政府药械招采网价格监测
> 子项目：2.3 招采降价预警与 Jobs 自动化触发
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

打通「数据 → 预警 → 任务」链路：基于 `gov_prices` 历史批次价格差自动生成机会任务（Jobs 自动化触发），为 M4 话术生成提供输入。

## 背景

架构定稿：
- 机会判定逻辑（首期 gov 线）：同药品同规格同地区，新批次 `gov_price` < 历史批次价 → 降价预警（价格战机会）。电商价差判定（gov - ecommerce > 2元）依赖 M3 电商数据，**M3 未就绪前不启用、不 mock 假数据**，判定器留接口待 M3 接入。
- 任务经 `jobs` 表（SQLite 账本）入队，由 Scheduler 按 capability_tags 派发给对应 Worker。
- 本子项目只做「判定 + 入队」的自动触发机制，话术生成在 M4。

## 方案内容

### 1. 降价预警判定器
- `src/workflow/opportunity.py` 第一阶段：扫描 gov_prices 历史批次（同药品同规格同地区）价格下降，产出 `opportunity_type='price_war'` 的原始机会记录（原数据 ID 关联）。电商价差判定留接口（M3 就绪后接入，禁 mock）。

### 2. Jobs 自动化触发
- 定时巡检（launchd / Scheduler 触发）：发现新机会 → 生成 JobSpec（capability_tags 含 `decision`）→ `enqueue` 入 SQLite 账本 → Scheduler 自动派发。
- 幂等：同一 (generic_name, specification, region) 在机会未消费前不重复入队。

## 验收标准

- [ ] 新批次 gov_price < 历史批次价 → 触发生成机会记录（单测覆盖边界 = 不触发）
- [ ] 同机会幂等不重复入队
- [ ] 机会默认 `pending_review` 状态（不直接推送）
- [ ] 入队任务带 `decision` capability_tags
- [ ] 电商价差判定接口存在且未接入前不产出记录（红线：禁假数据）

## 功能卡

### 降价预警判定器 + Jobs 自动入队

目标：完成预警判定与自动入队链路，交付可验收产物。

实现：按「方案内容」两节落地——opportunity.py 判定器 + 定时巡检入队 + 幂等。

验收：验收标准四条款全过（边界单测 / 幂等 / 状态 / tags）。

颗粒度：子项目级（1 卡，约 1.5 天）。

依赖：cla-plan-005（gov 数据）

架构位置：`src/workflow/opportunity.py`、`src/scheduler/job.py`、`jobs` 表

## 转卡计划

降价预警判定器（1 卡，待出卡）

## 备注

- 电商价差判定（依赖 M3 ecommerce_prices）留接口，M3 就绪后接入真实数据，禁止用假数据验证链路。
- 机会的完整挖掘逻辑（库存窗口/差评转化）在 M4（cla-plan-010），本方案只做价格战判定。