# Desktop 右栏 · 项目态势 SSOT

> 2026-07-29 · v0.64 · 右栏跟**左侧项目**绑定（同项目任意会话同一份），不是单会话时间线。  
> 事件契约：[`flow-events.md`](flow-events.md)  
> 意图卡供给：[`loop-engineer-authority.md`](loop-engineer-authority.md)「意图卡供给闭环」· [`../../references/intent-card-sop.md`](../../references/intent-card-sop.md)

---

## 用户要看见什么

| 区块 | 内容 |
|------|------|
| 顶栏 | 「本项目态势」+ 同步态；点「看板」进 Board |
| **看板条** | 待办 / 规划 / 进行 / 验收 / 异常 数量 + Δ — **老板判断板况的主信号** |
| **意图卡链** | L1 `planned`（及链上状态）；人点「讨论方案」/ 转意图卡后的主叙事 |
| 扇出 / 止损 | 超时无消费 / failed·abnormal：短人话 + 交给当前会话 Agent（SOP）；可忽略 |

**默认不展示**（v0.64+）：大卡栈 `taskStack`、扇出 work 竖轨 `FlowCanvasView` — 老板看不懂；状态靠看板计数即可。调试可留编译开关，生产默认关。

空态：转意图卡且 gate 绿进代办后，看板「待办」等计数变化；与中间栏对话故障无关。

---

## 绑定模型（硬）

```
左侧项目 ──► 右栏 projectFlow[projectId] + projectBoardCounts + mindGoals
任意会话 ──► 中间栏 threadMessages[threadId]（互不影响）
```

- `bindFlowToProject`：项目级计数与意图卡；切会话**不**重绑右栏。
- SSE 仍按 project；异常条用人话，不依赖点 work 节点。

---

## 视觉

- 意图卡：可读标题链；`planned` 可点讨论；`dispatched` 后链上收起或运维收口
- 看板条：列计数 + Δ
- 生产隐藏 LocatorCopy

实现：`FlowRail`（`ContentView.swift`）；看板条 `fetchBoardSummaries`；意图卡 `fetchMindDecided`

---

## 不做

- 右栏不是第二块完整看板（只摘要计数 + 意图卡链）
- Ops inbox / 采纳不搬进右栏
- 不把右栏再绑回单个对话
- 不把 work 拆解动画当老板主路径
