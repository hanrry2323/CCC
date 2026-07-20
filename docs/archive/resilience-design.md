# CCC 容错设计（v0.18-resilience）

## 核心原则

1. **一个任务失败，不影响其他任务**
2. **自动恢复优于手动干预**
3. **异常可见性：异常列 + 通知 = 操作员知道什么出了问题**
4. **指数退避：短频重试浪费资源，高频重试过快用尽次数**

---

## 一、Phase 重试 → 异常隔离

### 1.1 重试+退避（ccc-board.py dev_role）

当前 phases.json 格式：
```json
[{"phase": "task-p1", "status": "pending", "timeout": 300, "retry": 0}]
```

改为：
```json
[{"phase": "task-p1", "status": "pending", "timeout": 300, "retry": 0, "retry_at": null}]
```

退避策略：
- 第1次失败：等待 60s，retry=1
- 第2次失败：等待 120s，retry=2
- 第3次失败：等待 240s，retry=3
- 第4次失败：等待 480s，retry=4
- 第5次失败：retry>=5 → **移入异常列**

计算公式：`backoff_seconds = 60 * 2^retry`（60s, 120s, 240s, 480s, 960s, 1920s, 3600s）
封顶 3600s（1h）。

### 1.2 异常列（新列 abnormal）

```
backlog → planned → in_progress → testing → verified → released
                                        ↓（失败>=5次）
                                     abnormal
```

- `.ccc/board/abnormal/` 目录
- 进入 abnormal 的任务：
  - 不在任何角色的扫描范围内（跳过）
  - 标题前缀 `[ABNORMAL]`
  - `tags` 含 `"abnormal"` 和 `"automated"`
- ops_role 扫描 abnormal 并发送 L2 通知
- 操作员手动从 abnormal 拖回 backlog 后重试

### 1.3 全局超时（ccc-board.py dev_role）

- `max_exec_time`（环境变量 `DEV_MAX_EXEC_TIME`，默认 3600s）
- 从 task `started_at` 开始计时，超过 max_exec_time 仍未完成 → kill → 移 abnormal
- 防止 opencode 子进程永久卡死

---

## 二、Pipeline 隔离

### 2.1 单 tick 单 task

dev_role 当前逻辑（伪码）：
```
for task in in_progress:
    run phase
```
改为：
```
pick = list_tasks("in_progress")[0]  # 只取第一个
phase = next_unfinished(pick)
run phase(pick, phase)
```

一个 task 卡住不会阻塞其他 task——因为下一个 tick 会挑下一个 task 而不是永远重试同一个。

### 2.2 Tick timeout

每个 role 入口脚本包装 `timeout`：

```bash
timeout 600 python3 "$CCC_HOME/scripts/ccc-board.py" "$CCC_ROLE" 
```

- product/tester/reviewer/ops: 300s（5min）
- dev: 600s（10min，匹配 tick 间隔）
- kb/regress: 600s

---

## 三、Stale 检测（ops_role）

ops_role 每次扫描执行：

| 检查 | 条件 | 动作 |
|------|------|------|
| in_progress 超时 | updated_at > 6h | 移 abnormal，L2 通知 |
| abnormal 驻留 | updated_at > 24h | L3 通知 |
| 孤儿 PID | 有 pid 文件但进程不存在 | 清 pid 文件 |
| 重复 emergency | 同一 task 有 >=2 条 emergency | 去重，保留最近一条 |

---

## 四、执行计划

### Phase 1：ccc-board.py 改动

1. 退避计算函数 `_backoff_seconds(retry: int) -> int`
2. dev_role 失败时：写入 `retry_at`，不立即重试
3. dev_role 读取 task 时：跳过 `retry_at > now` 的 phase
4. 移入 abnormal 列的函数 `_quarantine(task_id, reason)`
5. abnormal 列的操作函数（create_abnormal_board_dir 等）

### Phase 2：ops_role 增加

1. stale task 扫描
2. 孤儿 PID 清理
3. L2/L3 通知

### Phase 3：role 脚本包装

1. 所有 role 脚本加 `timeout` 包装
