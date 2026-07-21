# Hub API v1 — 编排契约（冻结草案）

> **版本**：v1 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) §7  
> **主机**：Mac2017 Hub `:7777`（Basic Auth，默认见 [`../ccc-hub-ports.md`](../ccc-hub-ports.md)）  
> **原则**：产品主对话热路径在 **M1 sidecar `:7788`**；Hub `:7777` **只做** transfer / flow / board / ops / 健康（编排口）。远程双口见 [`hub-remote-management.md`](hub-remote-management.md)。破坏性变更 → **v2**。

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
| `POST` | `/api/desktop/proactive-epic` | **Proactive** 外部信号 → backlog bug epic（CI / git hook；见 §3b） |
| `GET` | `/api/desktop/flow/snapshot` | 右栏首屏 / 重连兜底 |
| `GET` | `/api/desktop/flow/events` | SSE 进度 |
| `GET` | `/api/desktop/projects` | 项目树 |
| `GET` | `/api/desktop/version` | 只读：Hub `version` / `commit` / `hub_api_version`（双机对齐） |
| `GET/POST` | `/api/desktop/threads` … | 会话镜像（非对话权威；备份/运维） |
| `GET` | `/api/board/…` | 看板（经 Hub 反代） |
| `GET` | `/api/ops/overview` 等 | 运维只读 |
| `GET` | `/api/desktop/proposals` | inbox 待采纳提案 |
| `POST` | `/api/desktop/proposals/{id}/adopt` | 人审采纳 → 内部 transfer |

产品主对话：**直打 M1 `:7788`**，**不**经 Hub，**不**在 2017 跑第二套 Claude 槽。thread id 与 Desktop 相同（`{project}::…`）。  
Hub 上若仍残留 `/api/agent/*` 反代，**不是**产品主路径（运维探针而已）。  
inbox 契约：项目根 [`inbox/`](../../inbox/README.md)。

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

## 3b. `POST /api/desktop/proactive-epic`（F4-3）

**Proactive = 意图门外的自动意图**：外部信号（CI 失败 / git hook）直接进 backlog，**仍走既有 Engine 流水线**；不改 transfer 字段，不替代人审 transfer。鉴权同 Basic Auth。进队后 **不**主动 wake Engine（tick 自取）。

契约细则与 webhook 示例：[`proactive-triggers.md`](proactive-triggers.md)。

### 请求

| 字段 | 必填 | 说明 |
|------|------|------|
| `project_id` | 是 | 已登记且可下达的业务仓（非 orch） |
| `source` | 是 | `ci` \| `git_hook` \| `external` |
| `title` | 是 | 1–80 字标题 |
| `goal` | 是 | 失败摘要 / 修复目标 |
| `acceptance` | 否 | 验收意图（缺省由 goal 合成一条） |
| `payload` | 否 | 原始 CI/hook JSON；参与幂等哈希 |

幂等：`client_request_id = proactive:{source}:{sha256(payload)[:24]}`（无 payload 时对 `{title,goal}` 哈希）。同一键重复 → 返回已有 `epic_id`，不新建。

落盘标记：`executor_intent` 记为 **`bug`**（tags 含 `proactive` / `bug` / `source:<…>` / `exec:bug`）；复用 `epic_created` flow 事件。

### 成功 `200`

```json
{
  "ok": true,
  "epic_id": "…",
  "queued": true,
  "idempotent_replay": false
}
```

### 失败

- `401`：未鉴权 / 错密  
- `400`：缺字段、非法 `source`、项目不可下达  

---

## 4. Flow

- 事件与阶段：[`flow-events.md`](flow-events.md)  
- 客户端重连：先 `snapshot`，再订 SSE；以本机 `boundEpicId` 为右栏焦点 SSOT。

---

## 5. 兼容与探测

- 客户端应容忍响应多字段。  
- 可用 `GET /api/desktop/projects` 或 ops overview 探测 Hub 可达。  
- 对话口探测：`GET http://<M1>:7788/health`（与 Hub 分离；见 [`hub-remote-management.md`](hub-remote-management.md)）。  
- `GET /api/ops/router-usage`：退役 stub，勿作用量权威。  
- **双机版本对齐**：`GET /api/desktop/version`（只读）→ `{ok, version, commit, hub_api_version}`；一键核对见 [`../deploy/dual-host-version-check.md`](../deploy/dual-host-version-check.md)。客户端支持集当前硬编码 `["v1"]`。

### `GET /api/desktop/version`（只读）

成功 `200`：

```json
{
  "ok": true,
  "version": "v0.52.2",
  "commit": "<full git sha>",
  "hub_api_version": "v1"
}
```

- `version`：仓库根 `VERSION` 文件内容（缺文件则为空串）。  
- `commit`：Hub 进程所在仓 `git rev-parse HEAD`（失败则为空串）。  
- `hub_api_version`：契约大版本，当前固定 `"v1"`；破坏性变更升 `"v2"`。  
- 无写副作用；需 Basic Auth（与其它 `/api/desktop/*` 相同）。

---

## 附录 A — 非产品：Hub `/api/agent` 反代（遗留）

> **产品主路径**：客户端直连 M1 sidecar。双口口径：[`hub-remote-management.md`](hub-remote-management.md)。  
> Hub `/api/agent/*` **默认不挂载**；仅环境变量 `CCC_AGENT_PROXY=1` 启用作运维探针。

---

## 6. 验收（`ccc-demo`）

1. transfer → epic 进 backlog → 自动扇出至 released（无人批）— **已勾选**：`scripts/smoke-ccc-demo-released.sh`  
2. 同一 `client_request_id` 连点两次 → 仅一张 epic  
3. Hub 断开：对话仍可；outbox 排队；恢复后投递成功 — **已勾选**：`scripts/smoke-hub-outage-outbox.sh`  
4. 空 body / 空 `epic_id`：Desktop 同 CRID 内联重试后入 outbox — **已勾选**：`scripts/smoke-hub-empty-transfer-retry.sh`  
5. 双口：`scripts/smoke-dual-port-remote.sh`（M1 health + 2017 transfer；勿以 2017 为 chat origin）  
6. 文档与实现字段一致（本文件 + transfer-gate）

---

*冻结日期：2026-07-20 · 双口纠偏：2026-07-21 · 实现 PR 须引用 `hub-api-v1`。*
