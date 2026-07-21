# Scheduler: Mavis cron (默认)

CCC 默认任务调度器。通过 `mavis cron` 在 Mavis 桌面端持续轮询执行状态。

---

## 何时使用

- Executor/Verifier 是长任务（> 3 min 预期），需要 Mavis 桌面端自动跟踪进度
- 需要定时检查 phases.json 更新并通知用户

## 安装

Mavis cron 是 Mavis 桌面端内置功能，无需额外安装。

## 使用

```
# 启动自提醒（Executor/Verifier 启动后立即执行）
mavis cron self qxo-<task> --every 5m

# 完成时删除
mavis cron delete qxo-<task>

# 检查状态
mavis cron list
```

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `self` | 使用当前会话 prompt 作为 cron 回调 prompt | `mavis cron self qxo-audit --every 5m` |
| `--every` | 间隔（支持 s/m/h/d） | `--every 5m` / `--every 1h` |

## 跨平台

Mavis cron 仅支持 macOS Mavis 桌面端。若 cron 不触发，检查 `ps aux | grep mavis` 确保 Mavis daemon 在运行。若 Mavis cron 不可用，改用 `scheduler-launchd.md` (macOS) 或 `scheduler-github-actions.md` (CI)。
