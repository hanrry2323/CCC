# 实验 C8 · fork 子代 wire 工具集继承

- **状态**：✅ 完成（源码级；端到端缺口）
- **批次**：B3 模式
- **环境**：源码
- **日期**：2026-08-16

## 结论

**fork 子代继承父的 agent preset（含 code 模式 tools:sdk 投影）；spawn 子代不继承（`inheritsParentContext=false`，用默认预设）。** 即：code 模式父代理 fork 出的子代理，走 tools:sdk code 投影；spawn 出的子代理默认 native。

## 证据

- `dsh-subagent-fork-in-process/lib/index.js:42`：`inheritsParentContext = true;`
- `dsh-subagent-spawn-in-process/lib/index.js:29`：`inheritsParentContext = false;`
- `dsh-subagent/lib/index.js:571`：`childCtx.get("agentPresets")?.composeFrom(childCtx, parent.ctx)`（子代理 preset 从父上下文合成）
- `dsh-subagent/lib/index.js:532-535`：子代理创建时带 `agentPreset`（来自父或组合）

## 结论细节

- **fork**：继承父上下文 + 从父合成 preset → 继承父的 tools mode（code → 子代也是 code 投影）。
- **spawn**：全新上下文 + 默认 preset → 不继承父的 code 模式。
- 语义自洽：fork 是「接着父的已完成轮次干」，上下文/工具面一起继承；spawn 是「另起炉灶」。

## 未覆盖

- 端到端实测（headless 起 code 父代理 → fork/spawn 子代 → 各自 tools 面）未跑——subagent 机制本机未实战过（报告：7 会话无真实 subagent 调用），且 headless 驱动子代理链路复杂。列为可选增强。

## 风险 / 对 CCC 借鉴的影响

- fork 继承工具面 = 子代理能复用父的 code 编排能力；spawn 独立 = 隔离更干净但能力默认化。
- CCC 若做「临时 Worker」协同：fork=继承上下文快照做延续任务、spawn=干净隔离做独立任务，语义清晰。
