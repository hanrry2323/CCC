# v10-automation Review

## Verdict: **FAIL**

## Size Class: **large** (250 行)

cluster-bus.py 5 个端点功能在 report 中 smoke pass，但存在 1 处 plan 偏差（sqlite3→JSON）、2 处死代码、diff 截断导致入口和 checkpoint 循环不可验证。按 plan 验收标准，未完全满足，判定 fail。

## Findings (6 条)

```json
{
  "verdict": "fail",
  "findings": [
    {
      "severity": "medium",
      "file": "scripts/cluster-bus.py",
      "line": 36,
      "issue": "Plan 要求 stdlib sqlite3 持久化 (5 min checkpoint)，但实现使用 JSON 文件 /tmp/ccc-cluster-bus.json，缺少 ACID 保障。报告用 'nodes self-recover via heartbeat' 解释，但 plan 的 sqlite3 要求未被满足",
      "suggestion": "替换为 sqlite3（stdlib），5 分钟 WAL checkpoint，或更新 plan 批准 JSON 方案"
    },
    {
      "severity": "low",
      "file": "scripts/cluster-bus.py",
      "line": 42,
      "issue": "Capabilities pydantic model (tags: list[str]) 定义了但未被任何端点或代码引用。RegisterRequest 直接使用 capabilities: list[str] 字段",
      "suggestion": "删除 Capabilities 类，或将其作为 RegisterRequest 的类型别名使用"
    },
    {
      "severity": "low",
      "file": "scripts/cluster-bus.py",
      "line": 54,
      "issue": "NodeRecord pydantic model 定义了但未作为端点响应模型使用。list_nodes 返回手动构造的 dict 而非 NodeRecord",
      "suggestion": "将 list_nodes 等端点的返回类型标注为 NodeRecord 或使用 response_model=NodeRecord，确保 schema 一致性"
    },
    {
      "severity": "low",
      "file": "scripts/cluster-bus.py",
      "line": 34,
      "issue": "变量名 HOSTBIND 是拼缀式 (host+bind)，Python 惯例用 BIND_HOST 或直接 HOST",
      "suggestion": "重命名为 BIND_HOST"
    },
    {
      "severity": "medium",
      "file": "scripts/cluster-bus.py",
      "line": 207,
      "issue": "diff 截断（仅显示 ~151/207 行），无法验证 __main__ 入口块、后台 checkpoint 循环 (60s)、GET /api/node/{node_id} 端点是否实现",
      "suggestion": "补充完整代码，确保 python3 scripts/cluster-bus.py 可直接启动 uvicorn，且 checkpoint 循环按 60s 间隔写入"
    },
    {
      "severity": "low",
      "file": ".ccc/phases/v1.0-automation.phases.json",
      "line": 1,
      "issue": "原 8 阶段 plan 被截断为 2 阶段，P1-1 至 P3-2（cluster-protocol.md、test、yaml、doctor.sh、abc report、dispatcher PoC）的 phases 记录消失，无阶段删除说明",
      "suggestion": "保留所有 8 阶段条目，只更新 status 字段，或按 plan 规划保留完整 8 阶段 JSONL（schema_version=1.1），避免阶段性进度丢失"
    }
  ],
  "summary": "cluster-bus.py 5 个端点功能在 report 中 smoke pass，但存在 1 处 plan 偏差（sqlite3→JSON）、2 处死代码、diff 截断导致入口和 checkpoint 循环不可验证。按 plan 验收标准，未完全满足，判定 fail。"
}
```
