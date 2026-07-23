# Desktop 右栏 · 项目态势 SSOT

> 2026-07-24 · 右栏跟**左侧项目**绑定（同项目任意会话同一份），不是单会话时间线。  
> 事件契约：[`flow-events.md`](flow-events.md)

---

## 用户要看见什么

| 区块 | 内容 |
|------|------|
| 顶栏 | 「本项目态势」+ 同步态；点「看板」进 Board |
| **看板条** | 待办 / 规划 / 进行 / 验收 / 异常 数量 + Δ（相对上一拍轮询） |
| **大卡栈** | 项目级活跃 epic（Hub `project_single`）；点切换焦点 |
| 扇出 / 止损 | 超时无 works / failed·abnormal 红条 → 运维或看板 |
| 竖轨 | 当前焦点 epic 的扇出 works（依赖分层） |

空态：定稿下达后出现编排；与中间栏对话故障无关。

---

## 绑定模型（硬）

```
左侧项目 ──► 右栏 projectFlow[projectId] + projectBoardCounts
任意会话 ──► 中间栏 threadMessages[threadId]（互不影响）
```

- `bindFlowToProject`：`fetchRecentEpics(threadId: nil)` → 项目全部活跃大卡。  
- 切会话**不**重绑右栏；切项目才 `.task(id: paneProjectId)` 刷新。  
- SSE 仍按 project；过滤焦点 epic 来自 `projectFlow`。

---

## 视觉与动效

- Epic / Work：圆角块 + 状态色；执行中呼吸脉冲  
- 竖轨 `orderedWorks`；层间短连接  
- 点击节点：sheet 看目标/状态/失败原因  
- 生产隐藏 LocatorCopy（调试用）

实现：`FlowRail`（`ContentView.swift`）+ `FlowCanvasView.swift`  
驱动：SSE `/api/desktop/flow/events` + snapshot；看板条来自 `fetchBoardSummaries`

---

## 不做

- 右栏不是第二块完整看板（只摘要计数 + 活跃编排）  
- Ops inbox / 采纳不搬进右栏  
- 不把右栏再绑回单个对话
