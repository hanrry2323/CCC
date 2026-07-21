# 网页 Hub：编排口（看板 / 运维）

> 2026-07-19 · 产品主入口 = **CCC Desktop（SwiftUI）**。  
> 2026-07-21 · 二次纠偏：网页 Hub `:7777` = **编排口**（看板 / 运维 / transfer API）；**对话口在 M1**，见 [`hub-remote-management.md`](hub-remote-management.md)。

---

## 主入口

| 面 | 状态 |
|----|------|
| [`desktop/`](../../desktop/) SwiftUI | **主产品**（本机会话 + sidecar `:7788`） |
| **M1 对话口** `:7788` | 远程聊对齐 / 聊方案（与 Desktop 同热路径） |
| 网页 Hub `:7777/` | **编排口**：`#/board` / `#/ops` + Desktop API；**不是**对话主入口 |
| Tauri WebView 壳 | 非主线 |

---

## 废弃（勿再对外宣传）

| 项 | 说明 |
|----|------|
| **双对话分屏** | `dualPane.js` — 产品废弃 |
| **2017 独立远程会话 / `hub::` / `/api/remote-chat`** | 已删 |
| **旧 `/api/chat` 在 Hub 本机跑 Claude** | 已删 |
| **Hub SPA + `/api/agent` 反代当 Remote Desktop 主路径** | 口径已废；对话挂 M1 |
| **网页当唯一产品入口** | Desktop 仍是主力 |

---

## 运维用法

- `#/board` 看板、`#/ops` 运维（Basic Auth：`ccc` / `ccc`）
- 下达：`POST /api/desktop/transfer`（客户端仍是 Desktop 或 M1 对话壳配置的 Hub base）
- 远程聊天：**不要**开 `http://192.168.3.116:7777/#/chat` 当产品路径；打 M1 `:7788`
