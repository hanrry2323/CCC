# 转任务聊透门禁（Transfer Gate）

> 方案 Agent 写入 **epic（待办大卡）** 前的硬门禁。失败必须 4xx + 机器可读原因。

---

## 流程

```text
对话 → 方案 Agent 输出 ```ccc-transfer``` JSON → Desktop「确认转任务」
  → POST /api/desktop/transfer
  → Gate 通过 → 仅创建 epic（backlog）
  → Gate 失败 → 不写看板，返回 errors[]
```

Engine **之后**才扇出 work；转任务接口禁止直接写 planned work。

## 定稿协议（`ccc-transfer`）

方案 Agent 在聊透后于回复末尾输出**恰好一个** fenced 块：

````markdown
```ccc-transfer
{
  "title": "…",
  "goal": "…",
  "acceptance": ["…"],
  "pipeline": "dev",
  "feasibility": "ok",
  "feasibility_reason": "",
  "executor_intent": "opencode",
  "plan_md": "# Plan …"
}
```
````

Desktop 解析后展示一键确认条；无块时仍可启发式预填 + 表单编辑。

---

## 必填字段（Gate）

| 字段 | 说明 |
|------|------|
| `project_id` | 已登记且 `engine_eligible` 的 app（非 orch） |
| `title` | 可执行中文标题，1–80 字 |
| `goal` | 目标：做什么、完成长什么样 |
| `acceptance` | 验收意图（至少一条，可含命令） |
| `pipeline` | 产线/执行意图：如 `dev` / `video` / `ops` 或自由文本 |
| `feasibility` | `ok` \| `blocked`；`blocked` 时必须有 `feasibility_reason` |
| `executor_intent` | 偏好执行面：`opencode`（默认）\| `python` \| `ollama` \| `cli` \| `auto` |
| `skills_hint` | 可选 string[]，软偏好供 Engine 扇出参考 |
| `plan_md` | 方案正文（Markdown） |
| `thread_id` | 可选，关联统一会话 |

`feasibility != ok` → **拒绝转任务**。

---

## 错误码（`error` 字段）

| code | 含义 |
|------|------|
| `missing_title` | 无标题 |
| `missing_goal` | 无目标 |
| `missing_acceptance` | 无验收 |
| `missing_pipeline` | 无产线/项目意图 |
| `feasibility_blocked` | Agent 评估不可执行 |
| `project_not_dispatchable` | 项目不可下达（orch / 未登记） |
| `invalid_executor_intent` | 未知执行面 |

---

## 成功响应

```json
{
  "ok": true,
  "epic_id": "…",
  "workspace": "ccc-demo",
  "column": "backlog"
}
```

仅创建 `card_kind=epic` 的 backlog 卡；`description`/`note` 含 plan 与 gate 快照。
