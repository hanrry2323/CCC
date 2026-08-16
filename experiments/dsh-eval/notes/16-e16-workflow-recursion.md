# 实验 E16 · workflow 无限递归

- **状态**：⚠️ 挂账（不宜实测到 cap）
- **批次**：B5 多代理
- **环境**：— 
- **日期**：2026-08-16

## 结论

**源码确认无 `maxDepth` 约束，仅 `maxTotalAgents=1000` 兜底**（dsh-workflow-worker-thread/lib/index.js:479-495, 846-856）。**不建议实测到 1000 个 agent 的 cap**（会烧大量模型调用），此实验挂账。

## 证据（源码）

- 报告维度五：「workflow 递归深度不受 maxDepth=3 约束：startChild 请求里没有 maxDepth 字段，只受 workflow 自身 maxTotalAgents=1000 兜底」
- `dsh-workflow-worker-thread/lib/index.js:479-495`（startChild）、`:846-856`（cap 检查）

## 结论细节

- 设计上允许子代理内再起子代理递归，没有深度护栏，只有总量 cap。
- 实测风险：递归到 1000 agent 会耗尽预算。若要测，需设极低 maxTotalAgents 的测试 profile + 预算护栏。

## 风险 / 对 CCC 借鉴的影响

- **无深度护栏 = 模型可写脚本触发资源耗尽**（DoS 型风险）。CCC 若吸收 workflow 编排，必须自己加深度/总量护栏。
- 与 A3 的 vm 逃逸叠加：workflow 脚本可逃逸到宿主 process，配合递归可构成资源耗尽攻击面。
