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
        ▼
Center Server：Threads · Board · Engine · Relay · Executors
```

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

## 三栏 UI

| 栏 | 作用 |
|----|------|
| 左 | 项目（文件夹）→ 对话 Thread（不区分 Hub/Claude） |
| 中 | 方案对话；定稿；转任务 |
| 右 | 最近一次成功转任务的 epic 扇出图 + 实时状态 |

**废弃**：双对话分屏、侧栏 Hub/Claude 双源、固定角色超市。

右栏默认跟随「当前项目最近一次成功转任务的 epic」。

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
- Server API：Hub `:7777` 上扩展 Desktop 路由（见 P1）
- Desktop 源码：仓库 [`desktop/`](../../desktop/)（SwiftUI）
- 旧 Tauri WebView 壳：非主产品线
