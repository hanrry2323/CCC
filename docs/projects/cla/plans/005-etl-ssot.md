# 方案 · 数据清洗与 SSOT 药名归一（M2-2.2）

> 项目：cla · 编号：cla-plan-005 · 状态：部分执行 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：cla019
> 关联方案：cla-plan-004（原始数据源）
> 里程碑：M2 · 政府药械招采网价格监测
> 子项目：2.2 数据清洗与 SSOT 药名归一
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

把 gov 抓取的原始异构数据清洗为标准字段，经 Levenshtein 模糊匹配归一至企业级 SSOT 药名大辞典，upsert 写入 `gov_prices` 表。

## 背景

架构定稿：
- 数据清洗：Levenshtein 模糊距离把「西格列汀片」与「磷酸西格列汀片」类差异归一到企业级 SSOT 通用药名大辞典。
- `gov_prices` 表：generic_name/specification/packaging/manufacturer/gov_price/region/announcement_url/fetched_at，唯一约束 (generic_name, specification, manufacturer, region) 防重复。

## 方案内容

### 1. 数据清洗管线
- `src/etl/cleaner.py`：字段标准化（名称/规格/包装/厂商/价格/省份/来源 URL）+ fetched_at 注入。

### 2. SSOT 药名归一
- `data/ssot_dict.json`（药名大辞典种子库）：Levenshtein 匹配归一；未命中打「待人工确认」标记。

### 3. 落库
- `gov_prices` upsert 语义（价格变化更新），唯一约束防重复。

## 验收标准

- [ ] 同一药品不同写法归一成功（单测覆盖 Levenshtein）
- [ ] 重复抓取不产生重复行
- [ ] 价格变化正确 upsert
- [ ] 未命中 SSOT 的药名有「待人工确认」标记

## 功能卡

### 数据清洗管线 + SSOT 药名归一 + 落库

目标：完成 gov 数据清洗与落库链路，交付可验收产物。

实现：按「方案内容」三节落地——cleaner.py + ssot_dict.json + gov_prices upsert。

验收：验收标准四条款全过（归一单测 / 防重 / upsert / 待确认标记）。

颗粒度：子项目级（1-2 卡，约 1.5 天）。

依赖：cla-plan-004（gov 原始数据）

架构位置：`src/etl/cleaner.py`、`data/ssot_dict.json`、`gov_prices` 表

## 转卡计划

数据清洗管线（1-2 卡，待出卡）

## 备注

- 从原 cla-plan-003 拆出（原方案混杂 2.1+2.2 两子项目，按 xy/hp 范式拆为独立方案）。
- 电商侧清洗复用本方案 cleaner（M3 数据同管线处理）。