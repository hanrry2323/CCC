# Desktop 右栏 · 活动流程图 SSOT

> 2026-07-20 · 右栏是 **本对话绑定的竖轨时间线**（按依赖分层展开），不是全局看板列表。  
> 事件契约：[`flow-events.md`](flow-events.md)  
> 可用性冲刺：[`desktop-usability-9.5-plan.md`](desktop-usability-9.5-plan.md)

---

## 用户要看见什么

站在「盯进度」而非「盯列名」：

| 阶段 | 主文案 | 次要 |
|------|--------|------|
| 空态 | 转任务后流程出现在这里；可补一句「与对话故障无关」 | 时间线按依赖分层 |
| pending | 待拆解 + 目标一句 | pipeline / 执行面 |
| planned | 已拆 N 步；可跑/被挡 | 依赖用**标题** |
| running | 置顶「正在：{标题}」 | 执行面白话（写码/脚本） |
| testing | 验收中 | note 摘要 |
| done | 已完成 | 子节点可弱化 |
| failed | 卡住：{标题} + 原因 | 开运维 |

Snapshot 增强字段：`headline`、`user_stage`、`goal_summary`、`user_status`、`executor_label`、`depends_on_titles`、`failure_note`。

---

## 视觉与动效（已实现）

- Epic / Work 节点：圆角块 + 状态色点；执行中呼吸脉冲
- **布局**：竖轨时间线；`depends_on` 分层顺序展开（reveal 动画）
- 层间用短竖轨连接；活动段用强调色
- 点击节点：sheet 看目标/状态/失败原因
- 历史 epic 切换：本对话多任务时右栏菜单

实现：`desktop/Sources/CCCDesktop/FlowCanvasView.swift` + `FlowLayout.swift`  
驱动：SSE `/api/desktop/flow/events` + snapshot 首屏/断线兜底

> **说明**：`FlowLayout.layout` 仍保留分层坐标算法，供将来多列 DAG；**当前 UI 消费的是竖轨 `orderedWorks` 路径**，产品预期以本文件为准。

---

## 已落地（功能主线）

- 点击节点：详情 sheet
- 历史 epic 切换：`GET /api/desktop/flow/epics` + 右栏菜单
- 失败态：跳转运维
- 空态与扇出超时 hint（人话）
- **Phase15**：UX 阶段表全档主文案；`goal_summary` 副行；work 卡 `executor_label` / `depends_on_titles` / `failure_note` / testing·running `note` 上卡；reveal 仅新 id stagger；running/failed 强调、done 弱化

## 后续（非本冲刺）

- 真多列力导向 / 缩放画布（可选差异化）
- 节点预览接完整 plan/report 文件
- Phase16：Desktop 本地优先冷启动（**已落地** · [`hub-shell-phase16-cold-start.md`](hub-shell-phase16-cold-start.md)）
