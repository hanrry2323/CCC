# ADR-001 — Protocol Layer 抽象

## 状态

Accepted (2026-07-01)

## 决策

将 Planner / Executor / Verifier 三角色抽象为独立的 **Protocol Contract**:
- 每个角色有独立 spec 文件 (`.yml`/`.md`)
- spec 定义 inputs / outputs / rules
- spec 不绑定任何特定 LLM 实现

任何 LLM agent (Claude / GPT / 本地模型 / MCP agent) 实现同一 spec,
都可以扮演该角色.

## 背景

CCC 早期 (0.x 阶段) 三角色绑定到具体 LLM:
- Planner = Mavis (M2.7/M3)
- Executor = claude -p
- Verifier = claude -p

这限制了跨 LLM 协作的可能性. 一个用户切换到 GPT-4 后,
无法继续用 CCC 框架.

## 后果

**正面**:
- 跨 LLM 协作: 任何 LLM agent 都能实现三角色, 不绑定 anthropic
- 测试更容易: 可 mock adapter 跑 unit test
- 长期可演化: 框架与模型解耦, 模型升级不影响框架

**负面**:
- 短期工程量增加: 需要写 spec / interface / 多 adapter
- 学习曲线: 用户需理解 Protocol 概念

**已知风险**:
- 不同 LLM 实现 spec 时可能有微妙差异, 需要 conformance test 兜底
