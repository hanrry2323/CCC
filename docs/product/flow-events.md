# 编排流程事件（右栏可视化）

> Desktop 右栏订阅中心 Server 事件流；默认跟随「项目最近一次成功转任务的 epic」。

---

## 传输

- **SSE**：`GET /api/desktop/flow/events?project_id=…&epic_id=…`  
- `epic_id` 省略时：Server 解析该项目最近转任务 epic  
- 认证：与 Hub 相同 Basic Auth  
- 心跳：每 15s `event: ping`

---

## 事件类型

| event | data（JSON） | 何时 |
|-------|----------------|------|
| `epic_created` | `{epic_id,title,project_id}` | 转任务成功 |
| `fanout` | `{epic_id,works:[{id,title,executor,depends_on[]}]}` | 扇出完成/更新 |
| `work_status` | `{epic_id,work_id,status,executor,note?}` | 列迁移或执行态变 |
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

---

## 实现备注

MVP 可用轮询板状态合成事件；生产可改为 Engine 写 event log + SSE 推送。  
事件日志建议：`~/.ccc/flow-events.jsonl`（Server 机）。
