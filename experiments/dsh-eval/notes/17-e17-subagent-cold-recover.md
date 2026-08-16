# 实验 E17 · 子代理冷恢复端到端

- **状态**：⚠️ 挂账（需进程重启 + 恢复链路，多模型轮次）
- **批次**：B5 多代理
- **环境**：—
- **日期**：2026-08-16

## 结论

**冷恢复链路（持久化 descriptor → 重启 → foldSubagentDescriptor → ctx.agents.resume）在源码完整，但本机无真实子代理调用记录，端到端未验证**。headless 单次会话无法直接模拟「进程重启后恢复子代理」，需专门测试 harness。

## 证据（源码）

- 报告维度五：「可续聊：SubagentContinuationManager 持久化 subagent/descriptor v2 事件，冷恢复用 foldSubagentDescriptor + ctx.agents.resume（dsh-subagent:1107-1140）；强制要求 sessionPersistence 后端否则 PERSISTENCE_UNAVAILABLE（:1500-1506）」
- 本机 7 会话无真实 subagent 调用（报告维度五）

## 结论细节

- 冷恢复依赖：会话持久化（jsonl）+ descriptor v2 事件 + resume 语义——机制都在。
- 端到端验证需：起一个带 subagent 的会话 → 进程重启 → resume 该会话 → 子代理上下文恢复。headless 无此编排。

## 风险 / 对 CCC 借鉴的影响

- 「会话 = 日志重放」的恢复模型（报告维度八已述）是 DSH 的持久化根基；子代理冷恢复是其延伸。CCC 若依赖长活子代理，需自行验证该链路的可靠性（挂账项）。
