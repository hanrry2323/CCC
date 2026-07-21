# 网页 Hub 降级与远程管理口

> 2026-07-19 · 产品主入口 = **CCC Desktop（SwiftUI）**。  
> 2026-07-21 · 网页 Hub 明确为 **远程管理口**（会话分区），见 [`hub-remote-management.md`](hub-remote-management.md)。

---

## 主入口

| 面 | 状态 |
|----|------|
| [`desktop/`](../../desktop/) SwiftUI | **主产品**（本机会话 + sidecar） |
| 网页 Hub `:7777/` | **远程管理口**：看板 / 运维 / 远程对话 / 下达 |
| Tauri WebView 壳 | 非主线；可用但不再作为产品叙事 |

远程对话与 Desktop **会话分区**（`hub::` thread），不对账、不续同一条会话。

---

## 废弃（勿再对外宣传）

| 项 | 说明 |
|----|------|
| **双对话分屏** | `dualPane.js` / `?desktop=1` 分屏 — 实验功能，产品上废弃 |
| **Hub / Claude 双源历史当产品主会话** | Desktop 本机 SSOT；Hub `CHAT_DIR` 仅远程管理会话 |
| **网页当最终产品 / 唯一聊天入口** | VISION / topology 已改口 |
| **旧 `/api/chat`** | 已删；远程管理用 `/api/remote-chat/*` |

---

## Desktop 打包基线

见 [`desktop/README.md`](../../desktop/README.md)：

```bash
cd desktop && swift build -c release
# 产物 .build/release/CCCDesktop；.app 签名 / notarize 后置
```

---

## 远程管理口用法

- `#/board` 看板、`#/ops` 运维、`#/console` 控制台、`#/chat` 远程对话
- Basic Auth 同 Desktop
- 下达：`POST /api/desktop/transfer`（远程页与 Desktop 同契约）
- 顶栏提示：远程会话与 Desktop 本机会话相互独立
