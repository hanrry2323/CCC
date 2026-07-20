# Engineer Flow — CCC 工程化交付流程（v0.7d-prime 配套）

> 目标：让所有 Executor 任务走"三件套 + 自动完成检测"路径，告别裸启动。

---

## 1. 为什么需要这个文档

v0.5–v0.7 期间 Executor 任务的常见痛点：

1. 启动后用户必须 `tmux capture-pane -t claude-code:N -p` 手动查进度（盲跑）
2. 完成判断靠肉眼观察 prompt 符，无标准信号
3. 失败兜底靠记忆，无脚本化 fallback

v0.7d-prime 沉淀 3 个脚本（`ccc-monitor.sh` / `ccc-poll.sh` / `ccc-exec-launcher.sh`）和 2 条红线（14/15），把上述痛点自动化。

---

## 2. 串行模式（同窗口顺序跑 N 个 phase）

**适用场景**：单项目多 phase 任务（如当前 v0.7d-prime plan 有 2 phase）。同一窗口顺序执行。

**操作步骤**：

```bash
# 1. 写好每个 phase 的 prompt 文件（.ccc/plans/*.txt）
# 2. 依次启动 launcher（注意：每起一次会拉起新 poll）
bash scripts/ccc-exec-launcher.sh 1 .ccc/plans/v0.7d-prime-phase1.txt
# 等 poll 完成（看 /tmp/poll-1.pid 是否还在）
bash scripts/ccc-exec-launcher.sh 1 .ccc/plans/v0.7d-prime-phase2.txt
```

**注意**：串行模式每次 launcher 会重新开 poll，但 monitor 窗口被复用（幂等）。

---

## 3. 并行模式（4 窗口各跑独立项目）

**适用场景**：多项目并行（如同时跑 4 个独立 plan）。每个窗口一个 Executor。

**操作步骤**：

```bash
# 1. 起 4 个窗口（手动 tmux）
tmux new-window -t claude-code -n proj-A
tmux new-window -t claude-code -n proj-B
tmux new-window -t claude-code -n proj-C
tmux new-window -t claude-code -n proj-D

# 2. 每个窗口分别启动 launcher
bash scripts/ccc-exec-launcher.sh 1 .ccc/plans/proj-A.txt &
bash scripts/ccc-exec-launcher.sh 2 .ccc/plans/proj-B.txt &
bash scripts/ccc-exec-launcher.sh 3 .ccc/plans/proj-C.txt &
bash scripts/ccc-exec-launcher.sh 4 .ccc/plans/proj-D.txt &

# 3. monitor 窗口会自动建（也可手动起），每 10s 刷新所有窗口尾部
```

**并行监控**：monitor 窗口同时打印 4 个窗口的最后 5 行，单人即可监督多任务。

---

## 4. ccc-exec-launcher.sh 三件套用法

### 4.1 完整接口

```bash
bash scripts/ccc-exec-launcher.sh <window> <prompt-file>
```

- `window`：tmux 窗口号（数字）
- `prompt-file`：包含 Executor 完整 prompt 的文件路径

### 4.2 三件套执行步骤

| 步骤 | 动作 | 幂等？ | 失败兜底 |
|------|------|--------|----------|
| 1 | `bash ccc-monitor.sh $SESSION` 开 monitor 窗口 | ✅ 已存在则跳过 | tmux 不可用 → 立刻 exit 非 0 |
| 2 | `tmux send-keys` 触发 `cat prompt | claude --bare --model deepseek-v4-flash` | ❌ 每次都发 | send-keys 失败 → launcher exit 非 0 |
| 3 | `nohup ccc-poll.sh $WINDOW $SESSION 300 &` 后台轮询 | ❌ 每次都起新 poll | poll 启动失败 → 仍视为成功（monitor 已开） |

### 4.3 poll 完成信号定义

```bash
# 同时满足：
# 1. pane 最后 5 行含 "❯"（prompt 符）
# 2. pane 最后 5 行无 "esc to interrupt"（无运行中提示）
```

满足后 → 写 `/tmp/poll-final-<ts>.txt` → break → 退出。

---

## 5. 失败兜底（poll 异常退出）

### 5.1 poll 异常退出场景

- tmux 进程崩溃 → capture-pane 失败 → poll 不写日志但进程存活（需手工 kill）
- 磁盘满 → `/tmp/poll-final-*.txt` 写失败 → break 仍执行但无产物
- 信号干扰 → SIGPIPE 等导致 sleep 中断 → 重新进入下次循环

### 5.2 手工兜底命令

```bash
# 1. 查看当前 poll PID
cat /tmp/poll-<WINDOW>.pid

# 2. 强制 kill
kill -9 $(cat /tmp/poll-<WINDOW>.pid)

# 3. 重启 poll（不带 monitor 和 Executor，纯轮询）
nohup bash scripts/ccc-poll.sh <WINDOW> claude-code 300 > /tmp/poll-<WINDOW>-restart.log 2>&1 &
echo $! > /tmp/poll-<WINDOW>.pid
```

### 5.3 launch 后没看到 monitor 的情况

```bash
# 1. 检查 monitor 窗口是否真的存在
tmux list-windows -t claude-code | grep monitor

# 2. 不存在则手动起（幂等）
bash scripts/ccc-monitor.sh

# 3. launcher 内部已调用 ccc-monitor.sh，无需重复起
```

---

## 6. 与红线的对应关系

| 红线 | 落地脚本 | 验证命令 |
|------|----------|----------|
| 红线 14 | `ccc-monitor.sh` + `ccc-poll.sh` + `ccc-exec-launcher.sh` | `bash scripts/ccc-exec-launcher.sh` 不报错 |
| 红线 15 | `ccc-poll.sh`（内部 break） | 跑 5s 测试 poll 自动退出 |

---

## 7. 未来扩展（v0.8+ 路线）

- 邮件/通知：poll 完成信号触发 webhook（v0.8）
- 多 session 支持：launcher 接受 `SESSION=xxx` 参数（已有，未文档化）
- poll 间隔可配置：当前硬编码 300s，未来接受 `--interval` 参数
