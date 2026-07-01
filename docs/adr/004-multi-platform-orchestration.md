# ADR-004 — Multi-Platform Orchestration

## 状态

Proposed (2026-07-02, 修订: Mavis/刘伟思等抽象为"用户常用 agent")

## 决策

把 CCC v0.3.0-dev 从"单平台默认 + 多 adapter 备选"升级为"多平台原生编排":

1. phases.json schema 加 `platform` 字段 (每个 phase 可指定执行 platform, 允许任意用户自定义 agent name)
2. plan 模板加 "Platform Routing" 段 (按用户 LLM 偏好主动路由每个 phase)
3. Report 加 "Platform Actual" 段 (记录实际 platform + cost)
4. Verifier 跨平台一致性 (同一 Verdict 可调用不同用户 agent 确认)

## 背景 (修订 2026-07-02: Mavis/刘伟思等是代号, 应抽象)

"用户常用 agent"指用户日常调度工作的 LLM agent 工具集, 是抽象类, 不是某个具体平台. 不同用户常用 agent 不同 (按 LLM 偏好 / 工作流 / 协作方式). 例子 (仅举例, 不是固定 4 平台):
- 偏好 minimax 的用户常用 agent (Mavis 性质) — 不可信, 红线 9
- 偏好 GLM 的用户常用 agent (ZCode 性质)
- 偏好 Claude 的用户常用 agent (Claude Code 性质)
- 偏好 GPT 的用户常用 agent (Codex 性质)
- 偏好 Claude + GLM 混用的用户常用 agent

每种"用户常用 agent"都锁定单一 LLM. 用户痛点: 想"用 Claude 写代码 + GLM 写中文 + GPT 写英文文档" → 单平台必须二选一.

CCC 在这些"用户常用 agent"之上做整合层 (multi-platform LLM orchestration framework), 不替代任何.

## 设计

### phases.json v0.4.0 schema

```json
{
  "phase": 1,
  "status": "pending",
  "platform": "claude-code",
  "platform_rationale": "Anthropic Claude 工程能力最强, audit-frontend 这类代码深度任务首选",
  "subtasks": {...},
  "commit": null,
  "notes": ""
}
```

`platform` 可选值: `claude-code` | `zcode` | `codex` | `mavis` | `default` (= claude-p) | `<custom-agent-name>` (v0.4.0+ 自由配置)

注: 未来支持任意用户自定义 agent name, 不绑定特定平台.

### plan 模板 Platform Routing 段

```markdown
## Platform Routing

| Phase | Platform | Rationale | 预算 USD |
|-------|----------|-----------|---------|
| 1 | claude-code | 代码深度审计 (用户常用 agent 偏好 Claude) | 200 |
| 2 | zcode | 中文 UI 文案 (用户常用 agent 偏好 GLM) | 50 |
| 3 | codex | 英文 README (用户常用 agent 偏好 GPT) | 30 |
```

### 跨平台 Report 格式

```markdown
## Phase X Actual Platform

- Plan: claude-code
- Actual: claude-p (default fallback due to mavis session new bug)
- Cost: $15
- Tokens: 150k in / 80k out
```

## 后果

**正面**:
- 真正跨用户常用 agent 调度: 用最优模型做最优任务
- 用户 killer use case (用户常用 agent + CCC 两层架构) 落地
- 摆脱 minimax 锁定 (按用户 LLM 偏好而非单一平台)
- 抽象化避免平台绑定, 任何新 agent (用户/企业/未来) 都可加入 CCC 调度

**负面**:
- Plan 模板复杂度增加
- 跨平台 Verdict 一致性需要新机制
- Cost tracking 复杂度提升

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Plan 复杂度爆炸 | v0.4.0 加 platform 字段为可选; 不指定则用 default (= claude-p) |
| 跨平台 Verdict 不一致 | Verifier 仍用 default (claude-p) 跑, 跨平台一致性作为 Info 项记录 |
| Cost 失控 | Plan 阶段 Planner 估算每 phase 预算, 超过阈值 FAIL |
| 用户绕过 platform 字段直接手动调 | install 脚本加 chmod 检查, 确保 platform 字段生效 |
| 用户常用 agent 命名差异 | v0.4.0+ 引入 `<custom-agent-name>` 自由配置, 不绑定 4 平台 |

## 实施路径

- v0.4.0 (2-3 月): phases.json platform 字段 + plan template routing 段
- v0.5.0 (3-6 月): 动态 platform selector (按 task type 自动匹配用户偏好)
- v1.0.0 (6-12 月): 跨平台 cost/quality dashboard + 自动优化
