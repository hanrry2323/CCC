# 网页 Hub：Remote Desktop 壳

> 2026-07-19 · 产品主入口 = **CCC Desktop（SwiftUI）**。  
> 2026-07-21 · 纠偏：网页 Hub = **远程 Desktop 壳（约 90%）**，见 [`hub-remote-management.md`](hub-remote-management.md)。

---

## 主入口

| 面 | 状态 |
|----|------|
| [`desktop/`](../../desktop/) SwiftUI | **主产品**（本机会话 + sidecar） |
| 网页 Hub `:7777/` | **Remote Desktop Shell**：同 sidecar 对话 + 同 Hub 编排 |
| Tauri WebView 壳 | 非主线 |

HTTP 对话经 `/api/agent/*` 反代到 **M1 sidecar**；thread 与 Desktop 相同。**不是** 2017 第二套聊天。

---

## 废弃（勿再对外宣传）

| 项 | 说明 |
|----|------|
| **双对话分屏** | `dualPane.js` — 产品废弃 |
| **2017 独立远程会话 / `hub::` / `/api/remote-chat`** | 已纠偏删除 |
| **旧 `/api/chat` 在 Hub 本机跑 Claude** | 已删；Remote Shell 走 Agent 反代 |
| **网页当唯一产品入口** | Desktop 仍是主力 |

---

## 运维用法

- `#/chat` 远程对话（M1 sidecar）、`#/board` 看板、`#/ops` 运维
- Basic Auth：`ccc` / `ccc`
- 下达：`POST /api/desktop/transfer`
