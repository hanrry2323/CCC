# 转意图卡门禁（Transfer Gate）

> **对话面 → 编排面** 的过桥正门（信息流唯一下达通道）。  
> 边界基线：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> SOP：[`../../references/intent-card-sop.md`](../../references/intent-card-sop.md)。  
> Agent 写入 **epic（代办）** 前的硬门禁。失败必须 4xx + 机器可读原因 + `fix_hint`。

---

## 流程

```text
IDE 写方案文件 → Hub API → 业务仓 `.ccc/intent-proposals/`
  → Claude 后台程序消费方案 → 拆卡 → 产出 `ccc-transfer`（多卡链）
  → POST /api/desktop/transfer/validate（dry-run）
  → 绿：POST /api/desktop/transfer → 仅创建 epic（backlog）+ wake
  → 红：不写 backlog，卡留意图层，返回 errors[] / fix_hint
```

Engine **之后**才扇出 work；transfer 接口禁止直接写 planned work。**无**「转意图卡」按钮——发起方 = IDE 写方案文件 → Claude 后台程序拆卡投递。

## 定稿协议（`ccc-transfer`）

定稿主体 = 方案文件（IDE 写）；`ccc-transfer` 块由 Claude 后台程序消费方案后产出：

````markdown
```ccc-transfer
{
  "title": "…",
  "goal": "…",
  "acceptance": ["…"],
  "pipeline": "dev",
  "feasibility": "ok",
  "feasibility_reason": "",
  "skill_ref": "skills/code-review",
  "prompt_ref": "prompts/code-review-prompt",
  "plan_md": "# Plan …"
}
```
````

Desktop 解析后展示一键确认条；无块时仍可启发式预填 + 表单编辑。

### 定稿后二级卡可改边界（硬 · 2026-07-23）

| 来源 `source` | 人可改 | 只读（须退回对话重定稿才能改） |
|---------------|--------|--------------------------------|
| `ccc-transfer`（正式定稿） | **title**、**human_note**（备注/定时说明）、`prompt_inline` | goal、acceptance、plan_md、pipeline、`skill_ref`、`prompt_ref`、complexity、feasibility、bump_version |
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
| `skill_ref` | 必填 string，Skill 库路径引用（如 `skills/code-review`），相对 `references/` |
| `prompt_ref` | 必填 string，Prompt 库路径引用（如 `prompts/code-review-prompt`），相对 `references/` |
| `skills_hint` | 可选 string[]，与 `skill_ref`/`prompt_ref` 软链接库对齐的辅助提示，供 Engine 扇出参考 |
| `prompt_inline` | 可选 string；Claude 后台程序组装时内联补充本卡特定上下文 |
| `plan_md` | 方案正文（Markdown） |
| `complexity` | 可选；`small`/`medium`/`large`（仅规模提示，**不**跳过审测）。**Hub 会抬升**：多步回归/三件套冒烟（acceptance 可执行条 ≥3，或命中 startup_check+pytest+三件套等）若填 `small` → **强制 `medium`**，避免扇出锁死单卡 |
| `bump_version` | 可选 bool；默认 false。true 时 kb 才升 VERSION |
| `human_note` | 可选；人工备注写入 epic note |
| `thread_id` | **必填（Desktop）**：真实会话 id（如 `{project}::UUID`）；Hub 未传时默认 `{project}::main` |
| `client_request_id` | 可选；Hub API v1 幂等键，重复提交返回已有 epic |

见 [`hub-api-v1.md`](hub-api-v1.md)。

`feasibility != ok` → **拒绝转任务**。

### 验收写作（防门禁误杀 · 防下游跑不动）

细则：[`references/intent-card-sop.md`](../../references/intent-card-sop.md)。

- **最小可跑通 v1（默认）**：长意图 epic 须 `goal` + ≥1 条可执行探针；**不**用 scope≤5 / phase≤2 挡用户级长意图。内部 work oversized 由 fanout 拦。
- **史径**（`CCC_MIN_PIPELINE=0`）：acceptance 1～3 条；scope≤5；phase≤2。
- 验收 bullets：**可执行命令**（pytest / DRY_RUN / assert）。
- **禁止**：`test -f`、散文假绿、本卡混装 unit+paper/e2e。
- 纯文案/脑包 → `text_task_agent_track`（对话 Agent 自轨，勿进 OpenCode）。

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
| `missing_skill_ref` | 缺少 `skill_ref`；fix_hint="需要指定 Skill 库路径引用（如 skills/code-review）" |
| `invalid_skill_ref` | `skill_ref` 路径不存在；fix_hint="Skill 库中未找到该路径，检查 references/skills/ 目录" |
| `missing_prompt_ref` | 缺少 `prompt_ref`；fix_hint="需要指定 Prompt 库路径引用" |
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

## 失败回流（硬 · 2026-07-29）

Gate 红**禁止静默丢弃**：

1. **HTTP**：`errors[]` + 顶层 `fix_hint`（`/transfer` → 4xx；`/transfer/validate` → 200 + `ok:false`）
2. **L1**：业务仓 `.ccc/agent-mind/decided.json` → `transfer_lessons[]`（`source=gate_reject`）；digest「近期定卡教训」；Agent `hub_mind_get` 可读
3. **回执**：sidecar 冲刷遇永久 4xx → `transfer-receipts.json` 写 `status=rejected` + `fix_hint`（勿空转 8 次）；Desktop hydrate 徽章 `failed`

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
