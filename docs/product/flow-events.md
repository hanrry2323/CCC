# 编排流程事件（右栏可视化）

> Desktop 右栏订阅中心 Server 事件流。  
> **项目即对话**：默认跟随本机 `boundEpicId`；Hub 侧 `::main` 为项目会话视图（见 [`project-as-conversation.md`](project-as-conversation.md)）。

---

## 传输

- **SSE**：`GET /api/desktop/flow/events?project_id=…&epic_id=…`  
- **快照**：`GET /api/desktop/flow/snapshot?project_id=…&epic_id=…`  
- **历史 epic**：`GET /api/desktop/flow/epics?project_id=…&thread_id={project}::main`  
  - `thread_id` 以 `::main` 结尾 → **项目会话视图**（返回该项目全部近期 epic，含旧 UUID 绑定）  
  - 响应含 `bound_hint`（建议绑定的最近 epic）、`conversation_view`  
  - 其它 `thread_id` → 精确匹配（遗留）  
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
- 空态：尚未转任务时提示「定稿并转任务后显示执行流程」  
- **绑定权威**：本机会话 `flow.epicId`（boundEpicId）；Hub 空列表不得清空

---

## 实现备注（95+）

1. **推送优先**：`product` 扇出写 `~/.ccc/flow-events.jsonl`（含 `project_id`）；SSE 以 `after_ts` 追赶。
2. **看板轮询兜底**：约每 8s 合成一次（首屏/断线）；不再 2s 狂刷。
3. Desktop 右栏：`fanout` → 拆分出生动画；`work_status` → 节点态刷新。
