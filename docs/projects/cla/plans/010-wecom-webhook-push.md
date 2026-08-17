# 方案 · 企业微信 Webhook 销售机会秒级推送通道 (M5)
> 项目：cla · 编号：cla-plan-010 · 状态：草案 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：待出卡
> 关联方案：cla-plan-009（合规卡关前置）
> 里程碑：M5 · 前端控制台、合规审核与企微触达
> 子项目：5.2 企业微信 Webhook 销售机会秒级推送通道
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

落地企业微信触达通道：机会通过三级合规审核后，经企微 Webhook 秒级推送营销话术给客户，带失败重试与推送留痕。

## 背景

架构定稿：
- `src/workflow/push_agent.py`（扩展）：企微机器人 Webhook 推送（markdown 消息格式）。
- 触发条件：`sales_opportunities.status == manager_approved`（或 rep_approved 且非高危）→ 自动推送。
- 秒级：审核通过事件触发即推（事件驱动，不走长轮询）；失败重试 3 次（指数退避），仍失败标 failed 人工补推。

## 方案内容

### 1. 推送执行器
- push_agent 扩展：Webhook 客户端（requests），markdown 话术模板（渠道适配：企微消息体规范）。
- Webhook URL 走 `config/secure_keys.env`（`WECOM_WEBHOOK_URL`），不提交 Git。

### 2. 推送状态机与留痕
- 状态：pending_push → pushed / push_failed（重试 3 次后终态）。
- `push_log` 表：opportunity_id/webhook_channel/payload_hash/pushed_at/status/error。
- 幂等：payload_hash 防重复推送。

## 转卡计划

### cla015 | 企微 Webhook 推送通道 + 重试留痕
* 颗粒度：1.5 天（3 文件）
* 依赖：--depends cla013（合规状态机）
* 架构位置：`src/workflow/push_agent.py`（扩展）、`push_log` 表、`config/secure_keys.env`
* 验收：通过审核机会自动推送（mock Webhook）；失败重试 3 次生效；payload_hash 防重；push_log 留痕完整。

## 备注

- 真实企微 Webhook URL 由老板提供后填入 secure_keys.env。
- 推送消息格式先做 markdown 文本，后续如需要可加图片/文件类型。