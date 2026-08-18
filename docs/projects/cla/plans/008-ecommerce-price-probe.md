# 方案 · 竞品批发价格与库存状态高频采样探针（M3-3.2）

> 项目：cla · 编号：cla-plan-008 · 状态：待排期 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：待出卡
> 关联方案：cla-plan-007（采集通道）
> 里程碑：M3 · 各大医药电商平台数据抓取
> 环境准备：Python >= 3.10, SQLite 3, 电商采集通道（同 007）
> 子项目：3.2 竞品批发价格与库存状态高频采样探针
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

基于 3.1 采集通道落地高频采样探针：定时抓取竞品批发价与库存状态，写入 `ecommerce_prices` 表，为 M2 降价预警与 M4 机会挖掘提供电商侧数据。

## 背景

架构定稿：
- `ecommerce_prices` 表：generic_name/specification/packaging/manufacturer/retail_price/stock_status/region/fetched_at；唯一约束 (generic_name, specification, manufacturer, region) 防重复。
- 高频采样：Scheduler 定时任务按平台队列轮询，复用 3.1 的限流熔断通道（不绕过 slots 硬卡）。
- 库存状态：枚举（in_stock / low_stock / out_of_stock），变化时记录（供 M4 补货窗口机会）。

## 方案内容

### 1. 采样探针
- `src/scheduler/tasks.py`（扩展）：注册高频采样任务（每平台 5 分钟轮询节奏，实际频率由配置控制），经 ecommerce 爬虫执行器抓取 → ETL 清洗（复用 cleaner）→ 写 `ecommerce_prices` upsert。

### 2. 库存变化记录
- stock_status 变更时写 audit 记录（同表 upsert + status_changed_at 字段），供 M4 补货窗口机会判定。

## 验收标准

- [ ] 定时轮询任务注册生效
- [ ] 采样数据 upsert 不重复
- [ ] 库存状态变化正确记录
- [ ] 限流熔断通道复用（不绕过 slots）

## 功能卡

### 高频采样探针 + ecommerce_prices 落库

目标：完成电商采样探针与落库链路，交付可验收产物。

实现：按「方案内容」两节落地——tasks.py 采样任务 + 库存变化记录。

验收：验收标准四条款全过（任务生效 / upsert / 库存记录 / 通道复用）。

颗粒度：子项目级（1 卡，约 2 天）。

依赖：cla-plan-007（采集通道）

架构位置：`src/scheduler/tasks.py`、`ecommerce_prices` 表

## 转卡计划

高频采样探针（1 卡，待出卡）

## 备注

- 采样频率以配置为准（env 控制），默认低频起步避免封号，验证稳定后调高。