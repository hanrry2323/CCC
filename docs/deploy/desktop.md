# CCC Desktop 客户端（SwiftUI）

> **主产品入口**。网页 Hub 为运维/兼容。服务端见 [`topology.md`](topology.md)。  
> 架构 SSOT：[`../product/ccc-desktop-architecture.md`](../product/ccc-desktop-architecture.md)  
> 降级说明：[`../product/deprecate-web-hub.md`](../product/deprecate-web-hub.md)

## 连接服务端

默认 `CCC_SERVER`：

```text
http://192.168.3.116:7777
```

应用内 Settings 可改；Basic Auth 默认 `ccc` / `ccc`。

## 三栏

| 栏 | 作用 |
|----|------|
| 左 | 项目文件夹 + 统一 Thread 列表 |
| 中 | 方案 Agent 对话；转任务（仅 epic） |
| 右 | 编排流程（flow events / snapshot） |

## 运行与打包

源码：[`../../desktop/`](../../desktop/)

```bash
cd desktop
swift run CCCDesktop
swift build -c release   # 打包基线
```

## 废弃

- **双对话分屏**（旧 Tauri / `dualPane.js`）— 不再作为产品能力
- **嵌网页 Hub SPA** — Desktop 不嵌 SPA
- Tauri WebView 壳 — 非主线

## API

| 路径 | 说明 |
|------|------|
| `GET /api/desktop/projects` | 项目树 |
| `GET/POST /api/desktop/threads` | 统一会话 |
| `POST /api/desktop/transfer` | 聊透门禁 → epic |
| `GET /api/desktop/flow/events` | SSE |
| `GET /api/desktop/flow/snapshot` | 右栏快照 |

端到端冒烟：`bash scripts/smoke-desktop-e2e.sh`
