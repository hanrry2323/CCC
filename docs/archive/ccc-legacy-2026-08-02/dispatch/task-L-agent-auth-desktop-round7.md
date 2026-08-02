# 任务书 L · Desktop 联动 7788 账号密码登录（窗口 2）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 2 即可。  
> 前提：窗口 1 实现 sidecar 账号密码登录端点（契约以 `report-K` 为准；未回前先按下述契约设计，最终以实际契约为准）。

## 0. 先读

1. `CLAUDE.md`
2. `desktop/Sources/CCCDesktop/APIClient.swift` 现有 agent 认证路径（`applyAgentAuth` 侧车 Bearer 通道）、`AppModel.swift` 配置
3. `docs/dispatch/2026-08-01-http-chat-optimization-review.md`（§安全）

## 1. 任务目标

1. **Desktop 登录**：桌面端配置 Hub/Agent 账号密码（沿用现有配置机制，无默认弱口令），启动/必要时调 `POST /api/auth/agent-login` 换会话 token
2. **请求带 token**：Desktop → 7788 的对话/健康请求带 Bearer 会话 token；401 → 重取一次（有界）→ 仍失败报错引导重新配置
3. **兼容与降级**：token 获取失败 → 明确报错而非静默；服务端未配置凭证时给清晰提示
4. **测试**：token 换取/401 重取行为锁（沿用 `desktop/Tests` 基建）

## 2. 允许范围

- `desktop/`（Swift）全部相关文件、`desktop/Tests/`、构建/测试配置

## 3. 红线（禁止）

- **无默认弱口令入库**；凭据不入库、不 commit
- `scripts/`（归窗口 1）、Hub 服务端鉴权逻辑不动
- 4000/4100 relay 相关、DRY_RUN、产线启动
- release 构建必须通过；对话/转任务主链路不得破坏；提交 main 禁止

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「账号密码配置方式 + token 生命周期 + 失败降级 + 与窗口 1 契约对齐点」，**不写代码**。  
确认后实现，`swift test` 全绿 + release 构建通过再提交。

## 5. 验收标准

- 配置账号密码后 Desktop 对话链路正常（token 换取 → Bearer）
- 401 重取一次有界，不无限循环
- 未配置/服务端拒绝 → 清晰报错，不白屏
- `swift test` 全绿；release 构建通过；提交在 `codex/ws-6-desktop-agent-auth` 分支

## 6. 完成报告格式

发现 → 动作 → 证据 → 移交项
