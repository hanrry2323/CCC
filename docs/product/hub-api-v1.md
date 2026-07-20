# Hub API v1 — 编排契约（冻结草案）

> **版本**：v1 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) §7  
> **主机**：Mac2017 Hub `:7777`（Basic Auth，默认见 [`../ccc-hub-ports.md`](../ccc-hub-ports.md)）  
> **原则**：聊天热路径不在 Hub；Hub 只做 transfer / flow / board / 健康。破坏性变更 → **v2**，本文件改标题并保留 v1 附录。

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

主对话：**不**走 Hub `/api/chat`（已删）。

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

1. transfer → epic 进 backlog → 自动扇出至 released（无人批）  
2. 同一 `client_request_id` 连点两次 → 仅一张 epic  
3. Hub 断开：对话仍可；outbox 排队；恢复后投递成功  
4. 文档与实现字段一致（本文件 + transfer-gate）

---

*冻结日期：2026-07-20 · 实现 PR 须引用 `hub-api-v1`。*
