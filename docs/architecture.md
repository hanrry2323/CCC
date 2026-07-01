# CCC 架构

## L4 User Interface

用户接入层: Mavis 桌面端, CLI, Web UI, Webhook 等用户触达点.
不直接接触 L3 以下任何层, 只触发 Planner.

## L3 Workflow Engine

任务流转引擎, 三个核心概念:
- **Plan**: 用户意图的结构化拆解
- **Phases**: 任务分阶段的执行计划 + 状态跟踪
- **State Machine**: 任务流转的状态机 (见下面)

## L2 Protocol Layer

三角色独立协议:
- **Planner Protocol**: inputs(user_intent, project_context) → outputs(plan.md, phases.json)
- **Executor Protocol**: inputs(plan.md, phases.json) → outputs(report.md, commits[])
- **Verifier Protocol**: inputs(plan.md, report.md) → outputs(verdict.md)

每个协议是 .yaml/.md spec + 文件级契约, 不绑定特定 LLM.

## L1 Runtime Adapter

执行后端可替换接口. 当前实现:
- ClaudeCodeAdapter (基于 claude -p, 当前默认)
- OpenCodeAdapter (planned, 基于 opencode exec)
- McpAdapter (planned, 基于 MCP server wrapper)
- NativeAdapter (planned, 直接调 Anthropic/OpenAI SDK)

配置: `./ccc.yaml` 选 adapter.

## L0 Scheduler Adapter

调度后端可替换接口. 当前实现:
- MavisSchedulerAdapter (基于 mavis cron)
- OsCronAdapter (planned)
- GithubActionsAdapter (planned)
- AirflowAdapter (planned)

## State Machine

```
draft → planned → in_progress (running) → reported → 
  → verified-pass → closed → archived
  → verified-fail → draft (next iteration)
  → verified-conditional → draft (next iteration)
```

每次状态转移写一行到 `.ccc/log/<task>.events.jsonl` (可观测性).

## Observability

- State Inspector: `ccc status <task>` 一行命令查 phases 状态
- Cron Registry: `ccc cron list` 列所有挂起的 cron
- Token/Cost Reporter: `ccc cost <task>` 每次执行费用报告
