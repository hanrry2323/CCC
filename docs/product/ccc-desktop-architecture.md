# CCC Desktop 产品架构 SSOT

> 版本：2026-07-19 · 与 Cursor/Codex/WorkBuddy 同级的完整产品形态  
> 冲突时以本文 + [`transfer-gate.md`](transfer-gate.md) / [`executor-plugins.md`](executor-plugins.md) / [`flow-events.md`](flow-events.md) 为准。

---

## 一句话

**CCC Desktop** 是用户唯一产品面；**中心 Server**（现 Mac2017，后云 SaaS）跑会话、看板与自由编排引擎。  
差异化：**自由编排 + 多执行面**（扇出时生成角色/skill；执行器可插拔）。

---

## Client / Server / SaaS

| 阶段 | Server | Desktop |
|------|--------|---------|
| 现网 | Mac2017 `192.168.3.116` | SwiftUI 客户端连 Server |
| 未来 | 云上同一 API | 只改 `CCC_SERVER` 地址 |

```text
Desktop (SwiftUI)
  左：项目文件夹 → 统一对话列表
  中：方案 Agent（loop-code）聊透 → 转任务
  右：编排流程可视化（扇出后实时进度）
        │
        ├─ localhost → Agent Sidecar（对话热路径）
        └─ Hub → 线程落盘 / 转任务 / flow SSE
              │
              ▼
Center Server：Threads · Board · Engine · Relay · Executors
```

角色边界不变（方案 Agent 只产 epic）；部署上对话热路径在 Desktop 本机，Server 管编排。

网页 Hub：**运维/兼容过渡**，不是主产品入口。

---

## 两 Agent 边界

| | 方案 Agent（对话） | 编排 Engine |
|--|-------------------|-------------|
| 界面 | Desktop 中栏 | 后台；右栏可视化 |
| 运行时 | loop-code | 扇出后按卡选执行器 |
| 产出 | **仅**待办大卡 (epic) | work 小卡 + 执行 + 验收 |
| 门禁 | 聊透才能转任务 | 消费合格 epic |

方案 Agent **不**扇出、**不**当执行 agent。  
Engine 扇出时决定下一步身份 / prompt / skill / executor。

---

## 三栏 UI（+ 极左活动栏）

| 区 | 作用 |
|----|------|
| **左（对齐 Codex）** | 新对话 + 项目菜单 + **会话列表**；底栏 Hub / 运维（浏览器） |
| **中（对齐 Codex）** | 居中对话主舞台 + 底部 composer；转任务为次级 CTA |
| **右（CCC 差异化）** | epic **活动动画流程图**（DAG + SSE） |

**废弃**：双对话分屏、侧栏 Hub/Claude 双源、固定角色超市、项目/对话上下硬拆。

右栏 UX 方案：[`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md)。  
连接契约（1 chat + 1 flow SSE）：[`desktop-connection.md`](desktop-connection.md)。

---

## 数据实体

| 实体 | 说明 |
|------|------|
| Project | registry 中的 engine app（工作区） |
| Thread | 统一会话，挂 `project_id` |
| Message | Thread 内消息 |
| Epic | 待办大卡（转任务唯一写入） |
| Work | Engine 扇出小卡，含 `executor` |

---

## 与现有代码关系

- Board / epic-work：[`references/board-task-schema.md`](../../references/board-task-schema.md)
- Server API：Hub `:7777` 已提供 `/api/desktop/*`（projects / threads / transfer / flow）
- Desktop 源码：仓库 [`desktop/`](../../desktop/)（SwiftUI）
- LAN 上线卡：[`../ops/GO-LIVE-DESKTOP.md`](../ops/GO-LIVE-DESKTOP.md)
- 旧 Tauri WebView 壳：非主产品线
