# 方案 · 医药合规 AI 初审与三级安全卡关系统 (M5)
> 项目：cla · 编号：cla-plan-009 · 状态：草案 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：待出卡
> 关联方案：cla-plan-008（话术输入）
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

## 转卡计划

### cla013 | 三级合规卡关状态机 + AI 初审
* 颗粒度：2.0 天（4 文件）
* 依赖：--depends cla012（话术输入）、cla010（LLM 通道）
* 架构位置：`src/workflow/push_agent.py`、`data/compliance_blacklist.json`、`review_log` 表
* 验收：L1 双检单测（敏感词命中/LLM 评分）；状态机全路径流转测试；未过审机会不可推送（有测试断言）。

### cla014 | 审核 API（列表/详情/动作）
* 颗粒度：1.0 天（2 文件）
* 依赖：--depends cla013
* 架构位置：`src/api/review.py`（FastAPI 路由）
* 验收：三组 API 功能测试；审核动作正确流转状态并留痕。

## 备注

- 敏感词库种子数据需老板/业务确认初版（医药广告法边界）。
- 人工审核入口 = 5.3 前端控制台；后端 API 先行，前端到位前可用 curl/测试验证。