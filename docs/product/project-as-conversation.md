# 项目即对话（Project-as-Conversation）

> 产品契约 SSOT（2026-07-19）。对齐 [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> Desktop 实现：`ConversationStore` + `LocalSessionStore.conversationThreadId` → `{projectId}::main`。

---

## 一句话

**一个项目恰好一个对话。** 项目卡 = 进入该对话；「重置对话」= 清空本机会话 + drop sidecar slot，**不是**新建 thread。

---

## 身份

| 概念 | 键 | 说明 |
|------|-----|------|
| 项目 | `project_id` | Hub projects / 侧栏卡片 |
| 会话 | `{project_id}::main` | Desktop 磁盘、sidecar `session_id`、transfer `thread_id` |
| 右栏绑定 | 本机 `boundEpicId`（落在会话 `flow.epicId`） | Hub epic 列表只作 enrichment |

Engine / Board **不读** `thread_id`（编排只认 epic/work）。

---

## 数据流（单向）

```text
本机磁盘 SSOT  ──hydrate──►  UI
     ▲                        │
     │                     transfer
     │                        ▼
     └── PUT 备份（可选）──  Hub session 镜像
                              │
                         epic_history
                              │
                         SSE / snapshot ──► 右栏（按 boundEpicId）
```

规则：

1. **消息 SSOT = M1 磁盘**；Hub `GET` **不得**覆盖非空本机会话（仅本机为空时可补种）。
2. **右栏 SSOT = 本机 `boundEpicId`**；Hub `list_epics` 空列表不得冲掉本地绑定。
3. transfer 必带 `thread_id={projectId}::main`（Hub 缺省也会钉死）。
4. `GET /flow/epics?thread_id=foo::main` = **项目会话视图**（不过滤旧 UUID epic），响应含 `bound_hint`。

---

## 用户动作

| 动作 | 行为 |
|------|------|
| 点项目卡 | 切项目 + 回对话面 + hydrate `{id}::main` |
| 侧栏「对话」 | 回对话面；从本机缓存恢复 |
| 重置对话 | 删本机会话文件 + sidecar drop |
| 转任务 | 写 epic + 本机 `boundEpicId` 落盘 + Hub flow 记录 |

---

## 迁移

旧 UUID 会话 / `epic_history.thread_id`：

```bash
python3 scripts/migrate-desktop-conversation-bind.py --dry-run
python3 scripts/migrate-desktop-conversation-bind.py --apply
```

不碰 Board 任务文件。

---

## Hub 配置标志

`GET /api/desktop/config` → `"conversation_model": "project_single"`。

---

## 手工验收清单

1. 选项目 A/B：磁盘仅 `sessions/<id>/<id>::main.json`；sidecar warm/chat 同 id  
2. 本机有消息时断 Hub：对话仍在；不闪空  
3. 转任务后杀 App 重开：右栏仍绑同一 epic  
4. 快切对话/看板/运维：消息与右栏不闪空  
5. （可选）`python3 scripts/migrate-desktop-conversation-bind.py --dry-run` 看旧 UUID 重绑
