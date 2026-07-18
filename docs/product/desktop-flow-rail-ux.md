# Desktop 右栏 · 活动流程图 SSOT

> 2026-07-19 · 右栏不是卡片列表，而是 **带动画边的 DAG 流程图**。  
> 事件契约：[`flow-events.md`](flow-events.md)

---

## 用户要看见什么

站在「盯进度」而非「盯列名」：

| 阶段 | 主文案 | 次要 |
|------|--------|------|
| 空态 | 三步：聊透 → 转任务 → 这里展开 | — |
| pending | 待拆解 + 目标一句 | pipeline / 执行面 |
| planned | 已拆 N 步；可跑/被挡 | 依赖用**标题** |
| running | 置顶「正在：{标题}」 | 执行面白话（写码/脚本） |
| testing | 验收中 | note 摘要 |
| done | 已完成 | 子节点可弱化 |
| failed | 卡住：{标题} + 原因 | 开 Hub 运维 |

Snapshot 增强字段：`headline`、`user_stage`、`goal_summary`、`user_status`、`executor_label`、`depends_on_titles`、`failure_note`。

---

## 视觉与动效

- Epic / Work 节点：毛玻璃圆角块 + 状态色点
- 边：贝塞尔曲线；活动边虚线流动（dash phase）
- 执行中：节点光晕呼吸
- 布局：无依赖并排；`depends_on` 分层

实现：`desktop/Sources/CCCDesktop/FlowCanvasView.swift` + `FlowLayout.swift`  
驱动：SSE `/api/desktop/flow/events` + snapshot 首屏/断线兜底

---

## 后续

- 真多列力导向布局 / 缩放
- 点击节点预览 plan/report
- 历史 epic 切换
