# 方案 · 医药合规 AI 初审与三级安全卡关系统（M5-5.1）

> 项目：cla · 编号：cla-plan-011 · 状态：部分执行 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：cla023, cla024
> 关联方案：cla-plan-010（话术输入）、cla-plan-009（LLM 通道）
> 里程碑：M5 · 前端控制台、合规审核与企微触达
> 子项目：5.1 医药合规 AI 初审与三级安全卡关系统
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

落地医药合规卡关：话术/机会在推送前必须过三级审核（AI 初审 → 代表复审 → 总管终审），未通过不得触达客户，保证医药营销合规红线。

## 背景

架构定稿：
- 三级卡关：L1 AI 初审（LLM + 敏感词库双检）→ L2 销售代表复审（人工确认）→ L3 总管终审（高危机会必审）。
- `src/workflow/push_agent.py`：审核状态机——pending_review → ai_reviewed → rep_approved / rep_rejected → manager_approved / manager_rejected。
- 敏感词库：`data/compliance_blacklist.json`（功效承诺/绝对化用语/处方药营销红线等）。
- 合规不通过的机会：标 rejected + 原因，可回流人工编辑后重审。

## 方案内容

### 1. AI 初审（L1）
- 双检：LLM 合规评分（复用 4.1 Provider）+ 敏感词库硬匹配；任一命中高风险 → 直接标 `rep_required`（强制人工）。

### 2. 人工复审/终审（L2/L3）
- 审核操作 API（FastAPI 路由，前端控制台调用）：approve/reject + 备注。
- 状态机流转完整落 `sales_opportunities.status` + `review_log` 表（审计留痕）。

### 3. 审核台数据接口
- 提供待审列表/单条详情/审核动作三组 API，供 5.3 前端控制台「合规审核面板」使用。

## 验收标准

- [ ] L1 双检单测（敏感词命中/LLM 评分）
- [ ] 状态机全路径流转测试（含 reject 回流）
- [ ] 未过审机会不可推送（有测试断言）
- [ ] 审核动作完整留痕（review_log）

## 功能卡

### 三级合规卡关状态机 + AI 初审

目标：完成合规状态机与 L1 初审，交付可验收产物。

实现：按「方案内容」1-2 节落地——push_agent.py 状态机 + 敏感词库 + L1 双检。

验收：验收标准条款 1-3（L1 单测 / 全路径流转 / 未过审不可推送）。

颗粒度：子项目内功能卡（约 2 天）。

依赖：cla-plan-010（话术输入）、cla-plan-009（LLM 通道）

架构位置：`src/workflow/push_agent.py`、`data/compliance_blacklist.json`、`review_log` 表

### 审核 API（列表/详情/动作）

目标：完成人工审核数据接口，交付可验收产物。

实现：按「方案内容」3 节落地——FastAPI 审核路由三组 API。

验收：验收标准条款 4（审核留痕）+ API 功能测试。

颗粒度：子项目内功能卡（约 1 天）。

依赖：三级合规卡关状态机

架构位置：`src/api/review.py`（FastAPI 路由）

## 转卡计划

三级合规卡关（1 卡）/ 审核 API（1 卡）

## 备注

- 敏感词库种子数据需老板/业务确认初版（医药广告法边界）。
- 人工审核入口 = 5.3 前端控制台；后端 API 先行，前端到位前可用 curl/测试验证。