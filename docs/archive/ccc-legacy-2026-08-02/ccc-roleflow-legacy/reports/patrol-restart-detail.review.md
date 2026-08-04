# patrol-restart-detail Review

## Verdict: **FAIL**

## Size Class: **large** (172 行)

核心功能（PID/uptime/看板快照写入 commit body）正确实现，但 plan 明确要求的 _log_engine_restart() 同步增强缺失，uptime 存在竞态条件。另有 docstring 描述错误、多进程 PID 模糊匹配、子串匹配精确度等次要问题。综合 verdict: fail，需补 _log_engine_restart 增强并解决 uptime 时序问题。

## Findings (5 条)

```json
{
  "verdict": "fail",
  "findings": [
    {
      "severity": "medium",
      "file": "scripts/ccc-patrol-v4.py",
      "line": 698,
      "issue": "Plan 明确要求 _log_engine_restart() 也记录 PID/uptime/board 字段，但该函数未被改动。entry dict 仍是 {ts, status, reason}，缺少这些有用信息。",
      "suggestion": "扩展 _log_engine_restart() 签名增加 pid/uptime/board 参数，写入 JSONL entry。或者新建一个增强版日志函数替代它。"
    },
    {
      "severity": "medium",
      "file": "scripts/ccc-patrol-v4.py",
      "line": 919,
      "issue": "_get_engine_uptime() 在 ensure_engine_healthy() 返回 RESTARTED 后才调用，此时新 Engine 已经启动（含 3s+ sleep）。新 Engine 可能在读之前就写入了心跳，导致 uptime 显示为几秒而非重启前时长。",
      "suggestion": "在 ensure_engine_healthy() 执行杀动作前就捕获心跳时间戳并保存到变量，重启后再计算 uptime。或者让 Engine 启动时不立即覆写心跳文件，留一段窗口期。"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-patrol-v4.py",
      "line": 776,
      "issue": "_get_engine_uptime() 的 docstring 写 \"在重启 Engine 前调用\"，但实际代码在 Engine 重启后才调用。与实际调用时序矛盾，且与上面的竞态条件问题直接相关。",
      "suggestion": "修复 docstring 以匹配实际调用时序，或按上述建议挪到 engine kill 之前调用。"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-patrol-v4.py",
      "line": 754,
      "issue": "_get_engine_pid() 返回 ps aux 中第一个匹配的 ccc-engine.py 进程 PID。如果有多进程残留（previous kill 未彻底），可能捕获到错误的 PID。",
      "suggestion": "可考虑用 launchctl list PID 或 Engine 自己的 PID file 获取更强的身份保证。当前方案对 commit log 场景精度够用，但值得记录。"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-patrol-v4.py",
      "line": 418,
      "issue": "_detect_crash_loop() 和 check_stuck_tasks() 中 PID 文件匹配使用 tid in pid_file.name 子串匹配，非精确匹配。例如 tid=\"task-1\" 会错误匹配 pid_file 名为 \"task-10-dead\".pid。",
      "suggestion": "改为更精确的匹配，例如 tid + '.' 前缀精确匹配，或使用固定分隔符后的格式校验。"
    }
  ],
  "summary": "核心功能（PID/uptime/看板快照写入 commit body）正确实现，但 plan 明确要求的 _log_engine_restart() 同步增强缺失，uptime 存在竞态条件。另有 docstring 描述错误、多进程 PID 模糊匹配、子串匹配精确度等次要问题。综合 verdict: fail，需补 _log_engine_restart 增强并解决 uptime 时序问题。"
}
```
