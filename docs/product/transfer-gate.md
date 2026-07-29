# 转任务聊透门禁（Transfer Gate）

> **对话面 → 编排面** 的过桥正门（信息流唯一下达通道）。  
> 边界基线：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> 方案 Agent（本机）写入 **epic（待办大卡）** 前的硬门禁。失败必须 4xx + 机器可读原因。

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

### 定稿后二级卡可改边界（硬 · 2026-07-23）

| 来源 `source` | 人可改 | 只读（须退回对话重定稿才能改） |
|---------------|--------|--------------------------------|
| `ccc-transfer`（正式定稿） | **title**、**human_note**（备注/定时说明） | goal、acceptance、plan_md、pipeline、executor_intent、complexity、feasibility、bump_version |
| `heuristic`（无正式定稿） | 意图与执行偏好可改（建议先点「定稿」锁方案） | — |

改方案 = 退回对话 → 再点「定稿」出新契约；禁止在二级卡改已锁 `plan_md`/验收后假装「只改了标题」。

---

## 必填字段（Gate）

| 字段 | 说明 |
|------|------|
| `project_id` | 已登记且 `engine_eligible` 的 app（非 orch） |
| `title` | 可执行中文标题，1–80 字 |
| `goal` | 目标：做什么、完成长什么样 |
| `acceptance` | 验收意图（至少一条，可含命令） |
| `pipeline` | 产线/执行意图：如 `dev` / `video` / `ops` 或自由文本。**`ops` 不跳过 Engine 扇出**（仍 epic→product→work） |
| `feasibility` | `ok` \| `blocked`；`blocked` 时必须有 `feasibility_reason` |
| `executor_intent` | 偏好执行面：`opencode`（默认）\| `python` \| `ollama` \| `cli` \| `auto`。**看板/产物卫生**（pipeline=`ops`/`hygiene`/`board*` 或标题含归档/回收 abnormal 等）若填 `opencode`/`auto`，Hub **强制归一为 `python`**，避免假 committer + OpenCode 半提交 |
| `skills_hint` | 可选 string[]，软偏好供 Engine 扇出参考 |
| `plan_md` | 方案正文（Markdown） |
| `complexity` | 可选；`small`/`medium`/`large`（仅规模提示，**不**跳过审测）。**Hub 会抬升**：多步回归/三件套冒烟（acceptance 可执行条 ≥3，或命中 startup_check+pytest+三件套等）若填 `small` → **强制 `medium`**，避免扇出锁死单卡 |
| `bump_version` | 可选 bool；默认 false。true 时 kb 才升 VERSION |
| `human_note` | 可选；人工备注写入 epic note |
| `thread_id` | **必填（Desktop）**：真实会话 id（如 `{project}::UUID`）；Hub 未传时默认 `{project}::main` |
| `client_request_id` | 可选；Hub API v1 幂等键，重复提交返回已有 epic |

见 [`hub-api-v1.md`](hub-api-v1.md)。

`feasibility != ok` → **拒绝转任务**。

### 验收写作（防门禁误杀 · 防下游跑不动）

细则：[`references/finalize-transfer-sop.md`](../../references/finalize-transfer-sop.md)。

- **预算**：acceptance **1～3 条（优先 1～2）** 强探针，只证明**本卡**意图。
- 验收 bullets：**可执行命令**（`.venv/bin/python -m pytest …` / `DRY_RUN=true .venv/bin/python …` / 短 assert）。
- **禁止**：`test -f`、散文假绿、同命令重复、把 **paper/e2e/下一张 L1** 探针塞进本卡。
- **排除/勿入**路径写在 `plan_md`「禁止」节，**不要**写进 `acceptance`。
- 不存在 committer 角色；**板面残卡优先 Hub `board-repair`**。偶发卫生卡用 `executor_intent: python`。
- `plan_md` 必有 `## 验收`（与 acceptance 同向）；默认 1 phase / 少数文件。

---

## 错误码（`error` / `errors[].code` · 均带 `fix_hint`）

| code | 含义 |
|------|------|
| `missing_title` | 无标题 |
| `missing_goal` | 无目标 |
| `missing_acceptance` | 无验收 |
| `missing_pipeline` | 无产线/项目意图 |
| `feasibility_blocked` | Agent 评估不可执行 |
| `project_not_dispatchable` | 项目不可下达（orch / 未登记） |
| `invalid_executor_intent` | 未知执行面 |
| `missing_intent_probe` | 无 pytest/python3/DRY_RUN 类强探针 |
| `acceptance_weak` | 仅 `test -f` / 存在性假绿 |
| `acceptance_too_wide` | 探针 >3 条（须压到 1～2） |
| `acceptance_mixed_intent` | 本卡同时 unit + paper/e2e |
| `plan_acceptance_weak` | plan 缺 `## 验收` 或弱探针 |
| `plan_scope_too_wide` | phase/顶层目录过多 → hang |
| `plan_goal_conflict` | goal 与 plan 方向冲突 |
| `intent_not_stable` | 未对齐/未 supersede L1 未完意图 |
| `role_lock_violation` | Desktop 禁直接写 work |

完整 `fix_hint` 以 `transfer_gate.py` `_default_fix_hint` 为准。

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
