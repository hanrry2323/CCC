# 对话面 / 编排面 / 运维面 边界契约（项目基线）

> **架构基线（过桥 + 三面职责）**。**事实权威（代码/看板/透镜/运维灯）以 [`loop-engineer-authority.md`](loop-engineer-authority.md) 为准**；冲突时改本文对齐它。  
> 相关：[`transfer-gate.md`](transfer-gate.md) · [`flow-events.md`](flow-events.md) · [`desktop-connection.md`](desktop-connection.md) · [`ccc-desktop-architecture.md`](ccc-desktop-architecture.md)

---

## 一句话

**对话、编排、运维必须分开。**  
M1 Desktop = 对话意图 + **运维健康灯**；Mac2017 = 编排引擎与远端开发 + 运维探针聚合。  
对话↔编排中间只交换结构化信息流；运维不替代下达，也不变成第二块派工看板。

---

## 三面职责

| 面 | 机器 | 负责 | 明确不负责 |
|----|------|------|------------|
| **对话面** | **M1**（Desktop + Sidecar + loop-code） | 聊透、意图识别、门禁字段、产出 **epic 大卡**、本机会话 SSOT；业务事实 = Hub baseline + **只读透镜 live**；**承接运维红灯复制包** | 不扇出 work、不跑 Engine、**不保留业务源码第二树**；默认 `tool_mode=discuss`；业务仓拒绝 engineer |
| **编排面** | **Mac2017**（Hub + Board + Engine + 业务仓） | 收 epic → 扇出 → 远端开发/验收/归档；右栏状态回传 | 不当主聊天窗口；不依赖 M1 本地 cwd |
| **运维面** | **Desktop OpsView + Hub Ops API**（探针在 2017 / 本机 sidecar） | **总灯绿/橙/红**；集群·端口·Agent·MCP；红灯一键复制交对话 Agent；旁路自愈/供弹/巡查/飞轮 | 不数卡当主叙事；不把老板当维修工；不 invent；不替代 transfer |

```text
M1 对话面 + 运维灯                         信息流（仅契约）                 Mac2017 编排面 + 运维探针
┌──────────────────────┐                                              ┌─────────────────────────┐
│ Desktop UI / OpsView │── POST /api/desktop/transfer（门禁 JSON）───►│ Hub :7777 + Ops API     │
│ Sidecar :7788        │──（可选）thread 绑定 / 消息镜像备份 ─────────►│ Board :7775             │
│ loop-code → MiniMax  │◄─ SSE flow: epic_created / fanout / … ────│ Engine + 业务仓写码      │
│ 本机 sessions 落盘    │◄─ 运维总灯 / 红灯 copy_payload ────────────│ 旁路：日审·patrol·reap  │
└──────────────────────┘                                              └─────────────────────────┘
```

---

## 信息流（过桥唯一允许）

### M1 → 2017（下达）

过桥正门：**`POST /api/desktop/transfer`**（字段对齐 [`transfer-gate.md`](transfer-gate.md)）。

| 字段 | 用途 |
|------|------|
| `project_id` | 业务仓（非 orch） |
| `thread_id` | 对话会话键（如 `{project}::UUID` 或 `{project}::main`）；**原样**写入 flow-events / note；未传时默认 `{project}::main`。右栏焦点以本机 `boundEpicId` 为准 |
| `title` / `goal` / `acceptance` / `pipeline` | 大卡正文 |
| `feasibility` / `feasibility_reason` | 门禁 |
| `executor_intent` / `skills_hint` / `plan_md` | 供扇出参考 |

产出：仅 **backlog epic**。禁止 transfer 直接写 planned work。

可选镜像：`PUT .../threads/{id}/messages` —— **备份/运维**，**不得**被 Engine 当编排输入；**不得**用 Hub GET 覆盖非空本机会话。

### 2017 → M1（可视）

| 通道 | 内容 |
|------|------|
| `epic_created` | 大卡已建 |
| `fanout` / `work_status` / `executor` | 拆分与进度（[`flow-events.md`](flow-events.md)） |
| snapshot | 右栏首屏/断线兜底 |

Desktop 右栏投影 **本机 `boundEpicId`** 对应的 epic/works。同一对话可连续 transfer 多笔 epic（排队）；完成态从右栏退场，历史在看板。详见 [`flow-events.md`](flow-events.md)「同对话连续多任务」。

### 明确禁止过桥

- 把整段闲聊 / 工具轨逐步日志当作 Engine 上下文  
- 编排机上的「主方案 Agent 聊天」（Hub chat 回退不得作为常态）  
- M1 本机绝对路径作为 Engine cwd（Engine 只用 Server 上登记的业务仓）  
- 对 CCC orch 仓投 backlog / 自消费（R-15）

---

## 运行时落点（现网）

| 组件 | 落点 | 说明 |
|------|------|------|
| CCC Desktop | M1 `/Applications` + 仓 `desktop/` | 唯一产品入口 |
| Agent Sidecar | M1 `com.ccc.agent-sidecar` → `:7788` | 对话热路径；launchd KeepAlive |
| loop-code（方案） | M1 `vendor/loop-code/cli`（arm64） | 只服务对话面 |
| Hub / Board | Mac2017 `:7777` / `:7775` | 信息流枢纽 + 看板 API |
| Engine | Mac2017 `com.ccc.engine`（控制面 `enabled`） | 远端开发闭环；product=Claude→MiniMax，dev=OpenCode→讯飞 |
| 业务仓看板 | Mac2017 `apps/<id>/.ccc/board` | 编排权威状态 |
| 本机会话 | M1 `~/Library/Application Support/CCCDesktop/sessions/` | 对话权威；Hub 镜像为辅 |
| 模型出口 | MiniMax / 讯飞直连 | ~~ai-loop-router `:4000/:4002` 已退役~~ |

---

## 产品规则（硬）

1. **方案 Agent 只产 epic**；扇出与写码只在编排面。  
2. **对话面可离线聊**（sidecar 活着即可）；Hub 抖只影响转任务/右栏。  
3. **编排面不依赖 Desktop 进程**；epic 入 backlog 后 Engine 可无人值守跑（控制面允许时）。  
4. **网页 Hub** 仅运维/兼容（看板/ops），不是对话主路径。  
5. **远程 HTTP 对话入口亦在 M1**（`:7788`），与 Desktop 同机；编排 API 在 2017 `:7777`（见 [`hub-remote-management.md`](hub-remote-management.md)）。  
6. 默认 **禁止** 把「Hub 回退聊天 / Hub 反代 sidecar 当产品主路径」宣传。

---

## 验收口径（基线）

| # | 断言 |
|---|------|
| B1 | M1 断 Hub 10s：仍可本机聊；不能转任务时有白话 |
| B2 | 转任务成功：2017 backlog 出现 epic；M1 右栏 ≤45s 见拆分或失败白话（含 Engine 未跑 / 仓不可消费） |
| B3 | Engine 写码 cwd = 2017 业务仓，不是 M1 路径 |
| B4 | 闲聊全文不进入 product/dev prompt（仅 gate/plan_md 结构化字段） |
| B5 | 常态无「对话打到 Hub `/api/chat`」或依赖 Hub `/api/agent` 作产品热路径 |

---

## 文档索引

| 文档 | 角色 |
|------|------|
| **本文** | 对话/编排/运维三面边界基线 |
| [`project-as-conversation.md`](project-as-conversation.md) | 一项目一对话身份与 SSOT |
| [`transfer-gate.md`](transfer-gate.md) | 过桥字段与错误码 |
| [`flow-events.md`](flow-events.md) | 回程事件 |
| [`desktop-connection.md`](desktop-connection.md) | Client 连接硬规则 |
| [`ccc-desktop-architecture.md`](ccc-desktop-architecture.md) | Desktop 产品形态 |
| [`hub-shell-roadmap.md`](hub-shell-roadmap.md) | 下阶段北星：壳 + Hub API v1；意图门人审 / 进队后自动 |
| [`../VISION.md`](../VISION.md) | 对外叙事（须与本文一致） |
