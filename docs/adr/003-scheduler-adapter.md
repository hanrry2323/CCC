# ADR-003 — Scheduler Adapter Pattern

## 状态

Accepted (2026-07-01)

## 决策

Scheduler Adapter Pattern — `SchedulerAdapter` interface + 多个实现:

```typescript
interface SchedulerAdapter {
  cron(name: string, schedule: string, prompt: string): Promise<void>
  cancel(name: string): Promise<void>
  list(): Promise<CronSpec[]>
  fireImmediate(name: string): Promise<void>
}
```

**当前实现**:
- `MavisSchedulerAdapter` (基于 mavis cron, 当前默认)

**未来实现** (planned):
- `OsCronAdapter` (`crontab` 系统调用)
- `GithubActionsAdapter` (`.github/workflows/*.yml` 生成)
- `AirflowAdapter` (DAG API)

## 理由

当前调度层 = mavis cron + nohup & 后台, 锁定到 Mavis 桌面端:
- 部署到 CI 环境 (GitHub Actions) 无法用
- 想用更专业的调度 (Airflow) 需要重写

Adapter Pattern 抽象后:
- 本地开发: 用 OsCronAdapter
- CI 环境: 用 GithubActionsAdapter
- 大型项目: 用 AirflowAdapter

## 后果

**正面**:
- 部署场景多样化
- 调度后端可独立测试
- 与 Runtime Adapter 互补 (Runtime = 怎么跑, Scheduler = 何时跑)

**负面**:
- 多 adapter 实现需维护
- 不同调度语义差异 (cron/事件触发/工作流)
