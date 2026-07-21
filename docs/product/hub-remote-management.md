# Hub 远程管理口（会话分区）

> **状态**：现行 · 2026-07-21  
> **对齐**：[`hub-api-v1.md`](hub-api-v1.md) 附录 · [`deprecate-web-hub.md`](deprecate-web-hub.md)  
> **原则**：最安全、最少开发量——**不做跨端续聊**。

---

## 一句话

**Hub HTTP（`:7777`）是 Mac2017 上的远程管理口**：看板 / 运维 / 远程对话（讨论·工程）/ 下达任务。  
**产品主对话仍在 Desktop（M1 sidecar）**。两端会话 **分区**，永不合并。

---

## 会话分区（冲突策略）

| 面 | 会话权威 | thread 形态 |
|----|----------|-------------|
| Desktop | M1 sidecar + 本机 store | `{projectId}::…`（无 `hub::` 前缀） |
| Hub HTTP | 2017 Hub `CHAT_DIR` + Claude 槽 | **必须** `hub::{projectId}::…` |
| 看板 / 运维 / transfer / Flow | Hub API | 两端共用，无会话冲突 |

**禁做**：跨端 live sync、lease、last-write-wins、Desktop 嵌 SPA、把主聊天迁成唯一入口。

页面固定提示：「本页为 Hub 远程会话，与 Desktop 本机会话相互独立；看板与下达任务共用。」

---

## 功能矩阵

| 能力 | Desktop | Hub HTTP |
|------|---------|----------|
| 看板 | 有 | `#/board` |
| 运维 / 控制台 | 有 | `#/ops` `#/console` |
| 讨论 / 工程模式 | 有 | `#/chat` + `tool_mode` |
| 聊任务 | 本机热路径 | Hub 远程（2017 runtime） |
| 下达 epic | transfer | 同 `POST /api/desktop/transfer` |
| Flow 右栏 | 有 | 不做完整右栏（看板 + transfer 结果即可） |

---

## 远程聊天端点（附录）

见 [`hub-api-v1.md`](hub-api-v1.md) §附录 A。摘要：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/remote-chat/stream` | SSE；`thread_id` 强制 `hub::` |
| `POST` | `/api/remote-chat/stop` | 释放该 thread 的 live 槽 |
| `GET` | `/api/remote-chat/history` | 仅 Hub 远程会话 |

---

## 烟测

```bash
CCC_SERVER=http://127.0.0.1:7777 bash scripts/smoke-hub-remote-management.sh
# 可选真聊一轮：CCC_REMOTE_CHAT_LIVE=1 …
```

---

## 成功标准

浏览器打开 Hub：能看板/运维、能 discuss/engineer 远程聊、能下达 epic；Desktop 同项目本机会话消息互不出现。
