> 🔴 **RETRACTED（2026-08-11 收敛）**：本文描述 Hub/Desktop 旧架构，已被现行架构（INDEX §0 薄驱动 Engine）取代。禁止引用；如需追溯见 docs/archive/ 或 git 历史。

# Desktop 右栏 · 项目态势 SSOT

> 2026-07-29 · v0.64.1 · 右栏跟**左侧项目**绑定（同项目任意会话同一份），不是单会话时间线。  
> 事件契约：[`flow-events.md`](flow-events.md)  
> 意图卡供给：[`loop-engineer-authority.md`](loop-engineer-authority.md)「意图卡供给闭环」· [`../../references/intent-card-sop.md`](../../references/intent-card-sop.md)

---

## 用户要看见什么

| 区块 | 内容 |
|------|------|
| 顶栏 | 「本项目态势」+ 同步态；点「看板」进 Board |
| **看板条** | 待办 / 规划 / 进行 / 验收 / 异常 数量 + Δ — **老板判断板况的主信号** |
| **意图卡** | 仅尚未进代办的 L1 `planned`（多卡 `1/N`）；态：待转 / 未过门；**无「讨论方案」按钮** |
| 扇出 / 止损 | 超时无消费 / failed·abnormal：短人话 + 交给当前会话 Agent（SOP）；可忽略 |

**默认不展示**（v0.64+）：大卡栈 `taskStack`、扇出 work 竖轨 `FlowCanvasView` — 老板看不懂；状态靠看板计数即可。生产删除死代码。

空态：「谈妥后点转意图卡」。gate 绿进代办后看板「待办」Δ 变化；卡从链移除（可短暂「已进代办」角标）。`dispatched`/`probed`/`stable` **不在右栏**（运维收口）。

---

## 绑定模型（硬）

```
左侧项目 ──► 右栏 projectFlow[projectId] + projectBoardCounts + mindGoals(planned)
任意会话 ──► 中间栏 threadMessages[threadId]（互不影响）
```

- `bindFlowToProject`：项目级计数与意图卡；切会话**不**重绑右栏。
- SSE 仍按 project；异常条用人话，不依赖点 work 节点。
- 讨论只在中间栏自然聊；右栏卡**默认无点击动作**（避免假按钮）。

---

## 视觉

- 意图卡：可读标题链 + `1/N`；小态「待转」/「未过门」
- 看板条：列计数 + Δ
- 生产隐藏 LocatorCopy
- 僵尸 `planned`（无 linked epic / 无活跃 backlog）→ `abandoned`，右栏不堆坟

实现：`FlowRail`（`ContentView.swift`）；看板条 `fetchBoardSummaries`；意图卡 `fetchMindDecided`

---

## 不做

- 右栏不是第二块完整看板（只摘要计数 + 意图卡链）
- Ops inbox / 采纳不搬进右栏
- 不把右栏再绑回单个对话
- 不把 work 拆解动画当老板主路径
- 不在右栏放「讨论方案」标签
