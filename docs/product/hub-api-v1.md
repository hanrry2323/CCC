# Hub API v1 — 编排契约（冻结草案）

> **版本**：v1 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) §7  
> **主机**：Mac2017 Hub `:7777`（Basic Auth，默认见 [`../ccc-hub-ports.md`](../ccc-hub-ports.md)）  
> **原则**：产品主对话热路径在 Desktop（M1 sidecar）；Hub 做 transfer / flow / board / 健康，以及 **远程管理对话**（会话分区，见 [`hub-remote-management.md`](hub-remote-management.md)）。破坏性变更 → **v2**，本文件改标题并保留 v1 附录。

---

## 1. 客户端可见投递三态

| 态 | 含义 | Desktop |
|----|------|---------|
| `draft` | 本机已定稿/填表，未成功过桥 | 定稿条 / 转任务表单 |
| `delivered` | `POST /transfer` 成功，已有 `epic_id` | toast + 本机 boundEpicId |
| `accepted` | 编排面已看见（flow/snapshot 或 engine wake） | 右栏绑定；进队后**无人批** |

Hub 不可达时：允许本机 **`queued`**（outbox 落盘），恢复后重试 → 再进入 `delivered`。  
`queued` 是投递机状态，**不是**第四种产品人审态。

---

## 2. 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/desktop/transfer` | 意图门通过 → backlog epic |
| `GET` | `/api/desktop/flow/snapshot` | 右栏首屏 / 重连兜底 |
| `GET` | `/api/desktop/flow/events` | SSE 进度 |
| `GET` | `/api/desktop/projects` | 项目树 |
| `GET/POST` | `/api/desktop/threads` … | 会话镜像（非对话权威） |
| `GET` | `/api/board/…` | 看板（经 Hub 反代） |
| `GET` | `/api/ops/overview` 等 | 运维只读 |
| `GET` | `/api/desktop/proposals` | inbox 待采纳提案（默认仅 pending） |
| `POST` | `/api/desktop/proposals/{id}/adopt` | 人审采纳 → 内部 transfer |
| `POST` | `/api/remote-chat/stream` | Hub 远程管理对话 SSE（附录 A） |
| `POST` | `/api/remote-chat/stop` | 停止远程 turn / 释放槽 |
| `GET` | `/api/remote-chat/history` | Hub 远程会话历史 |

产品主对话：**不**走旧 `/api/chat`（已删）。远程管理对话走 `/api/remote-chat/*`，与 Desktop 本机会话 **分区**（`hub::` 前缀）。  
inbox 契约：项目根 [`inbox/`](../../inbox/README.md)（一级目录，禁止 `.ccc/inbox` 双轨）。

---

## 3. `POST /api/desktop/transfer`

### 请求（核心字段）

见 [`transfer-gate.md`](transfer-gate.md)。v1 增补：

| 字段 | 必填 | 说明 |
|------|------|------|
| `client_request_id` | 否 | 客户端幂等键（UUID）。同一键重复提交 → 返回已有 epic，不新建 |
| `thread_id` | 建议 | 原样写入 flow；缺省 `{project}::main` |

### 成功 `200`

```json
{
  "ok": true,
  "epic_id": "…",
  "workspace": "ccc-demo",
  "column": "backlog",
  "engine_wake": { "ok": true },
  "idempotent_replay": false
}
```

`idempotent_replay=true` 表示命中 `client_request_id` 或已存在同 id epic。

### 失败 `400`

```json
{
  "ok": false,
  "error": "<code>",
  "errors": [{ "code": "…", "message": "…" }]
}
```

错误码以 [`transfer-gate.md`](transfer-gate.md) 为准；另：`role_lock_violation`、`invalid_epic_id`。

### 人审边界（v1 语义）

- 本接口 = **意图门**通过后的唯一下达。  
- 成功后 Engine 自动编排；**无**逐步人批回调。  
- 旁路提案必须先经 Desktop 采纳再调本接口（见 roadmap §3）。

---

## 4. Flow

- 事件与阶段：[`flow-events.md`](flow-events.md)  
- 客户端重连：先 `snapshot`，再订 SSE；以本机 `boundEpicId` 为右栏焦点 SSOT。

---

## 5. 兼容与探测

- 客户端应容忍响应多字段。  
- 可用 `GET /api/desktop/projects` 或 ops overview 探测 Hub 可达（与 sidecar `/health` 分离）。  
- `GET /api/ops/router-usage`：退役 stub，勿作用量权威。

---

## 6. 验收（`ccc-demo`）

1. transfer → epic 进 backlog → 自动扇出至 released（无人批）— **已勾选**：`scripts/smoke-ccc-demo-released.sh`  
2. 同一 `client_request_id` 连点两次 → 仅一张 epic  
3. Hub 断开：对话仍可；outbox 排队；恢复后投递成功 — **已勾选**：`scripts/smoke-hub-outage-outbox.sh`  
4. 空 body / 空 `epic_id`：Desktop 同 CRID 内联重试后入 outbox — **已勾选**：`scripts/smoke-hub-empty-transfer-retry.sh`  
5. 文档与实现字段一致（本文件 + transfer-gate）

---

## 附录 A — Hub 远程管理对话（`hub-remote-chat`）

> 非 Desktop 会话权威。契约全文：[`hub-remote-management.md`](hub-remote-management.md)。

### `POST /api/remote-chat/stream`

请求 JSON：

| 字段 | 必填 | 说明 |
|------|------|------|
| `project` / `project_id` | 是 | 项目 id |
| `message` | 是 | 用户原文 |
| `thread_id` | 否 | 缺省 `hub::{project}::main`；若传必须已以 `hub::` 开头 |
| `tool_mode` | 否 | `discuss`（默认）\| `engineer` |
| `model` | 否 | 默认 `flash` |
| `claude_session_id` | 否 | resume |

响应：`text/event-stream`，事件 `delta` / `tool_use` / `tool_result` / `error` / `done` / `ping`。

### 分区硬规则

- `thread_id` **不以** `hub::` 开头 → `400` `invalid_thread_id`
- Desktop 本机 thread（如 `{project}::main`）**禁止**写入本接口

---

*冻结日期：2026-07-20 · 远程管理附录：2026-07-21 · 实现 PR 须引用 `hub-api-v1`。*
