# 实验 E18 · fork 中途上下文缺失

- **状态**：⚠️ 挂账（需在打开的 run_code 回合中途 fork）
- **批次**：B5 多代理
- **环境**：—
- **日期**：2026-08-16

## 结论

**「父会话 run_code 未闭合时 fork，子代理是否看不到当前回合内容」无法在 headless 单次会话内构造**（需要跨回合持久状态 + 中途 fork）。挂账。与 C8 的源码结论（fork 继承父上下文 + preset，dsh-subagent-fork-in-process:42 + composeFrom）同源，推断中途上下文是否可见取决于「未闭合回合是否已持久化」。

## 证据

- C8 已确认：fork `inheritsParentContext = true`（dsh-subagent-fork-in-process/lib/index.js:42）
- 未闭合回合的持久化时机：checkpoint 在 llm/stream、顶层 tool、pre-step 强制 flush（报告维度三）

## 结论细节

- 推断：fork 继承的是「已持久化的父上下文」；未闭合的当前回合若已 checkpoint 则可见，未 flush 则不可见。需要端到端验证（挂账）。

## 风险 / 对 CCC 借鉴的影响

- 与 C8 合并看：fork 的上下文继承边界 = 持久化边界。CCC 若用 fork 延续任务，需清楚「哪些已固化、哪些会丢」。
