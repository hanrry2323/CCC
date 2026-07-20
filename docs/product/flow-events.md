# 编排流程事件（右栏可视化）

> Desktop 右栏订阅中心 Server 事件流。  
> **项目即对话**：默认跟随本机 `boundEpicId`；Hub 侧 `::main` 为项目会话视图（见 [`project-as-conversation.md`](project-as-conversation.md)）。

---

## 同对话连续多任务

| 规则 | 说明 |
|------|------|
| 一次 transfer = 一张新 epic | 不复用旧卡；连续定稿可连投 N 笔 |
| `thread_id` 原样落盘 | 未传时才默认 `{project}::main`；**禁止**把 `project::UUID` 强改成 `::main` |
| 右栏焦点 | 本机 `boundEpicId` = **最新一笔未完成** epic；每次 transfer 替换焦点 |
| 完成即退场 | `user_stage=done` → 右栏清空时间线（保留 `recentEpics` 列表）；历史只在**看板** |
| 切换 | `recentEpics` Menu「切换本对话任务」可回看未完成编排；已 done 不展开时间线 |
| Engine | 同仓多 epic 进 backlog **排队**；同仓 opencode **单写码槽**（非并行多路） |

---

## 传输

- **SSE**：`GET /api/desktop/flow/events?project_id=…&epic_id=…`  
- **快照**：`GET /api/desktop/flow/snapshot?project_id=…&epic_id=…`  
- **历史 epic**：`GET /api/desktop/flow/epics?project_id=…&thread_id=…`  
  - `thread_id` 以 `::main` 结尾 → **项目会话视图**（返回该项目全部近期 epic）  
  - 其它 `thread_id` → **精确匹配**该对话下达过的 epic  
  - 响应含 `bound_hint`、`conversation_view`  
- `epic_id` 省略时：Server 解析该项目最近转任务 epic  
- 认证：与 Hub 相同 Basic Auth  
- 心跳：每 15s `event: ping`

---

## 事件类型

| event | data（JSON） | 何时 |
|-------|----------------|------|
| `epic_created` | `{epic_id,title,project_id,thread_id?}` | 转任务成功 |
| `fanout` | `{project_id,epic_id,works:[{id,title,executor,depends_on[],status?}]}` | 扇出完成/更新 |
| `work_status` | `{project_id,epic_id,work_id,status,executor,note?}` | 列迁移或执行态变 |
| `executor` | `{epic_id,work_id,executor,phase?,detail?}` | 执行器启动/结束 |
| `epic_done` | `{epic_id,split_status}` | epic done/failed |
| `error` | `{message}` | 订阅错误 |

`status` 对齐看板列：`backlog|planned|in_progress|testing|verified|released|abnormal`。

---

## 右栏渲染

- 节点 = work；边 = `depends_on`  
- 节点标注 `executor`  
- 颜色/进度随 `work_status`  
- 空态：「编排空闲 · 下一笔定稿后出现在这里」；已完成不在右栏堆时间线  
- Header：仅 `pending`/`planned` 且无 works 显示「待拆解」；`done` 不得误显「待拆解」  
- **绑定权威**：本机会话 `flow.epicId`（boundEpicId）；Hub 空列表不得清空

---

## 实现备注（95+）

1. **推送优先**：`product` 扇出写 `~/.ccc/flow-events.jsonl`（含 `project_id`）；SSE 以 `after_ts` 追赶。
2. **看板轮询兜底**：约每 8s 合成一次（首屏/断线）；不再 2s 狂刷。
3. Desktop 右栏：`fanout` → 拆分出生动画；`work_status` → 节点态刷新；`epic_done` → 清空焦点时间线。
