# 方案 · 招采降价预警与 Jobs 自动化触发 (M2)
> 项目：cla · 编号：cla-plan-004 · 状态：草案 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：待出卡
> 关联方案：cla-plan-003（数据源）
> 里程碑：M2 · 政府药械招采网价格监测
> 子项目：2.3 招采降价预警与 Jobs 自动化触发
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

打通「数据 → 预警 → 任务」链路：基于 `gov_prices` 与 `ecommerce_prices` 的价格差自动生成机会任务（Jobs 自动化触发），为 M4 话术生成提供输入。

## 背景

架构定稿：
- 机会判定逻辑：`gov_prices.gov_price - ecommerce_prices.retail_price > 2元` → 自动触发生成跟进话术任务（价格战预警）。
- 任务经 `jobs` 表（SQLite 账本）入队，由 Scheduler 按 capability_tags 派发给对应 Worker。
- 本子项目只做「判定 + 入队」的自动触发机制，话术生成在 M4。

## 方案内容

### 1. 降价预警判定器
- `src/workflow/opportunity.py` 第一阶段：扫描 gov_prices 与 ecommerce_prices 价格差，产出 `opportunity_type='price_war'` 的原始机会记录（原数据 ID 关联）。

### 2. Jobs 自动化触发
- 定时巡检（scheduler TaskRegistry 风格 / launchd 触发）：发现新机会 → 生成 JobSpec（capability_tags 含 `decision`）→ `enqueue` 入 SQLite 账本 → Scheduler 自动派发。
- 幂等：同一 (generic_name, specification, region) 在机会未消费前不重复入队。

## 转卡计划

### cla006 | 降价预警判定器 + Jobs 自动入队
* 颗粒度：1.5 天（3 文件）
* 依赖：--depends cla005, cla007（ecommerce_prices 数据源，若 M3 未完成则先用 mock 数据）
* 架构位置：`src/workflow/opportunity.py`、`src/scheduler/job.py`、`jobs` 表
* 验收：价格差 >2 元触发生成机会记录；同机会幂等不重复入队；单测覆盖边界（=2 元不触发）。

## 备注

- 若 M3（电商数据）未就绪，本卡先以 mock ecommerce_prices 数据验证链路，M3 落地后替换真实数据源。