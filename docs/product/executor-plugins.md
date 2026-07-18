# 执行器插件契约（多执行面）

> 自由编排的出口。Engine 扇出每张 work 时指定 `executor`。

---

## 类型

| id | 说明 | MVP |
|----|------|-----|
| `opencode` | OpenCode CLI（默认写码/改仓） | **必达** |
| `python` | 运行指定 Python 入口 / 产线脚本 | **必达（桩或真跑）** |
| `ollama` | 本地 Ollama HTTP 生成 | 接口先定义 |
| `cli` | 通用 argv CLI | 接口先定义 |
| `auto` | 由 Engine 按 epic.pipeline 推断（默认→opencode） | 扇出时解析 |

---

## Work 卡字段（扇出写入）

```json
{
  "executor": "opencode",
  "executor_spec": {
    "cwd": ".",
    "entrypoint": null,
    "model": "loop/code",
    "args": []
  }
}
```

- `opencode`：走现有 OpenCodeExecutor  
- `python`：`executor_spec.entrypoint` 为相对项目根的 `.py` 或模块；超时与日志进 report  
- 未知 `executor` → work 标 abnormal，原因 `unknown_executor`

---

## 注册表（Server）

逻辑位置：`scripts/executors/registry.py`

```text
resolve(executor_id) -> ExecutorPlugin
plugin.run(work_ctx) -> ExecResult
```

持续优化对象：**编排时如何选 executor + 如何生成 prompt/skill**，不是固定角色菜单。

---

## 与方案 Agent

转任务门禁的 `executor_intent` 仅为**软偏好**；Engine 扇出可覆盖，但应写入 work 供右栏展示。
