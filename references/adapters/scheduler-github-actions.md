# Scheduler: GitHub Actions (CI)

CI 环境下的 CCC 任务调度。通过 GitHub Actions cron 触发自动化执行。

---

## 何时使用

- 任务适合在 CI 环境运行（无交互、无 GUI、依赖可预装）
- 已有 CI 流水线的项目
- 不需要实时监控，只看结果

## 安装

在工作流根目录 `.github/workflows/ccc-<task>.yml`：

```yaml
name: CCC <task>
on:
  workflow_dispatch:       # 手动触发
  schedule:
    - cron: '0 */2 * * *'  # 每 2 小时（替代 IPC cron / launchd）

jobs:
  ccc-executor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run CCC Executor
        run: |
          cat ~/program/CCC/SKILL.md | claude -p "$(cat prompt.txt)"
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## 注意事项

| 注意点 | 说明 |
|--------|------|
| API key | 必须通过 GitHub Secrets 注入，不写死 |
| 交互 | GitHub Actions 无交互式输入，Executor prompt 必须自包含 |
| 超时 | GitHub Actions 默认 6h 超时，足够全部 type 任务 |
| 日志 | Actions 输出即为 Report，可下载 |
| Verifier | Verifier 可另建一个 workflow，依赖 Executor completed |
