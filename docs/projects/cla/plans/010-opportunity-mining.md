# 方案 · 销售机会挖掘逻辑与多格式营销话术自动生成（M4-4.2）

> 项目：cla · 编号：cla-plan-010 · 状态：部分执行 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：cla022
> 关联方案：cla-plan-006（价格战机会）、cla-plan-008（库存/补货窗口）、cla-plan-009（LLM 通道）
> 里程碑：M4 · 双轨决策与话术自动生成
> 子项目：4.2 销售机会挖掘逻辑与多格式营销话术自动生成
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

落地机会挖掘与话术生成核心：从 gov/电商价格差、库存变化、差评舆情中挖掘销售机会（价格战/补货窗口/差评转化），经 LLM 生成多格式营销话术（微信/短信/社媒），写入 `sales_opportunities` 表，交 M5 合规审核。

## 背景

架构定稿：
- `src/workflow/opportunity.py`：三类机会判定——price_war（gov-电商价差 >2 元）、restock_window（竞品 out_of_stock）、negative_review（舆情差评，media 线暂缓则先留接口）。
- `sales_opportunities` 表：generic_name/specification/opportunity_type/confidence/summary/raw_data_id/generated_at/status。
- 话术生成：`src/workflow/planner.py` 负责话术规划（渠道适配），LLM 生成多格式（微信话术 500 字内/短信 70 字内/社媒短帖），复用 4.1 通道。
- 机会入库 status 默认 `pending_review`（未过合规不得推送）。

## 方案内容

### 1. 机会挖掘
- `opportunity.py`：三类机会判定器（规则驱动，确定性逻辑优先，LLM 仅用于文案生成），机会去重幂等（同 raw_data 不重复生成）。

### 2. 话术生成
- `planner.py`：渠道模板（微信/短信/社媒）+ LLM 生成（prompt 模板化，含药品合规约束提示）。
- 输出多格式并存，`sales_opportunities` 一行 = 一个机会 + 多格式话术 JSON 字段。

## 验收标准

- [ ] 三类机会判定单测（边界：=2 元不触发、库存正常不触发）
- [ ] 机会幂等去重（同 raw_data 不重复）
- [ ] 微信/短信/社媒三格式生成成功（mock LLM + 真实 ollama 各一）
- [ ] 机会默认 pending_review 不直接推送
- [ ] prompt 含合规约束提示

## 功能卡

### 机会挖掘判定器（三类机会）

目标：完成三类机会判定与去重，交付可验收产物。

实现：按「方案内容」1 节落地——opportunity.py 判定器 + 幂等去重。

验收：验收标准条款 1-2（边界单测 / 幂等）。

颗粒度：子项目内功能卡（约 1.5 天）。

依赖：cla-plan-006（价格战机会）、cla-plan-008（库存数据）

架构位置：`src/workflow/opportunity.py`、`sales_opportunities` 表

### 多格式话术生成 + 入库

目标：完成渠道话术生成与机会入库，交付可验收产物。

实现：按「方案内容」2 节落地——planner.py + LLM 多格式生成 + pending_review 入库。

验收：验收标准条款 3-5（三格式 / pending_review / 合规提示）。

颗粒度：子项目内功能卡（约 2 天）。

依赖：机会挖掘判定器、cla-plan-009（LLM 通道）

架构位置：`src/workflow/planner.py`、`src/workflow/opportunity.py`（扩展）

## 转卡计划

机会挖掘判定器（1 卡）/ 多格式话术生成（1 卡）

## 备注

- 差评转化（negative_review）依赖 media 舆情线（草案池），本里程碑只留判定接口，不实现数据源。
- 话术内容合规约束在生成层做首道提示，正式把关由 M5-5.1 三级卡关执行。