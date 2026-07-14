# Patrol v4 — CCC Engine 看门狗 + 自动化异常排查

> 本文档面向 CCC 开发者和运维人员，是 Patrol v4 的一站式参考。
> 另见：`scripts/ccc-patrol-v4.py`（源码）、`docs/lessons.md`（历史教训）、`scripts/ccc-loop-monitor.sh`（调用方）

---

## 1. 概述

### 定位
Patrol v4（`ccc-patrol-v4.py`）是 CCC Engine 的看门狗 + 自动化异常排查守护进程。每轮扫描解决三件事：
1. **Engine 还在不在**——不在就重启
2. **有没有异常任务没人管**——有就分类处理
3. **有没有任务卡死**——有就恢复

### 流程总览
```
Phase 0: Engine 存活检测
  ├── 心跳文件存在? ──Yes─→ Engine 运行中
  └── 心跳文件陈旧? ──Yes─→ 三重重启策略
      ├── launchctl bootstrap → 失败 → restart_engine()
      ├── launchctl load → 失败 → restart_engine()
      └── Popen 后台启动 → 成功 → 记录日志

Phase 1: 扫描 5 个工作区
  └── 读取每个工作区 board/index.json，统计 in_progress 任务

Phase 2: 异常排查（三步法）
  Step 1: note/updated_at 创建时间 → 超时 2 小时?
  Step 2: verdict/report/plan 产出是否完整?
  Step 3: 根据产出内容分类移动
      ├── 有产出且成功 → released
      ├── 有产出但失败 → planned
      └── 无产出 → backlog 或 abnormal

Phase 2.5: 持续失败三态检测
  ├── consecutive_skip >= 3
  ├── retry_count >= 3
  └── all_failed_or_skipped

Phase 3: 活跃任务卡死检测
  ├── 是否 in_progress 且时长 > STUCK_THRESHOLD (300s)?
  └── 是否 opencode-pids 有 clearlock 重启记录?
      └── 是 → 列移回 planned + 清理 PID 文件

Phase 4: 状态持久化 + 停滞检测
  ├── 保存最近 N 轮状态到 ~/.ccc/patrol-state.json
  ├── 监控 MAX_ROUNDS (6) 是否达标
  └── 连续无变化? 警告 + 停滞降频
      └── (当前尚未实现自动降频)

Phase 5: 修复后 Commit
  └── git commit -m "patrol: [engine: RESTARTED/DEAD]|清空 abnormal|恢复 stuck task|N 轮停滞|无变化"

Phase 6: 报告输出
  └── 单行摘要: "[Engine存活] workspaces=N abnormal=N stuck=N active=N rounds=N"
```

### 与其他组件关系
| 组件 | 关系 |
|------|------|
| Engine（ccc-engine.py）| Patrol 监控目标：心跳检测 + 存活检查 + 自动重启 |
| Loop Monitor（ccc-loop-monitor.sh）| Patrol 调用方：loop-monitor 的 step 1 执行 patrol |
| Cockpit（ccc-cockpit.py）| 无直接集成，Cockpit 可后续显示 patrol 状态摘要 |
| Notify（ccc-notify.sh）| Patrol 调用方：Engine 重启/死亡时发桌面通知 |

---

## 2. 功能列表

### 步骤 0：Engine 存活检测（最高优先级）

Patrol 启动时首先检查 Engine 是否运行：
1. **心跳时效判断**：访问每个工作区 `.ccc/.engine-heartbeat.json`，检查 `last_updated` 扣除当前时间是否超过 `HB_STALE_SECONDS`（默认 300 秒）
2. **进程存活检查**：运行 `ps aux | grep ccc-engine.py` 确认进程 PID 存在
3. **三层回退重启**：
   - 回退 1：`launchctl bootstrap` Engine plist
   - 回退 2：`launchctl load` Engine plist
   - 回退 3：`subprocess.Popen` 直接启动 `python3 scripts/ccc-engine.py --workspace <ws>`
4. **记录重启事件**：成功重启后写入 `~/.ccc/logs/engine-restarts.jsonl`，包含时间戳、工作区、PID、原因

### 步骤 1：扫描 5 个工作区

遍历 5 个硬编码工作区，读取各自 `board/index.json`：
- CCC → `~/program/CCC`
- qxo → `~/program/qx-observer`
- xianyu → `~/program/xianyu`
- qb → `~/program/projects/qb`
- qx → `~/program/projects/qx`（只读，不修改）

统计：
- 总任务数
- `in_progress` 任务数（潜在卡死候选）
- `abnormal` 任务数（待清理）

### 步骤 2：异常排查（三步法）

对每个工作区的每个 task：
1. **步骤 2.1：时效检测**：读取 `note/updated_at`，如果距离当前时间超过 2 小时，进入异常排查
2. **步骤 2.2：产出检查**：读取 `verdict/`、`report/`、`plan/` 目录是否存在且非空
3. **步骤 2.3：分类处理**：
   - 有产出 + 内容合格 → 移至 `released/`
   - 有产出 + 内容质量问题 → 移至 `planned/`
   - 无产出 → 移至 `backlog/` 或 `abnormal/`

### 步骤 2.5：持续失败三态检测

检测任务是否陷入持续失败状态，触发较低优先级的清理：
- `consecutive_skip >= 3`：连续 3 轮被跳过
- `retry_count >= 3`：重试次数超过 3 次
- `all_failed_or_skipped`：所有子阶段失败或跳过

### 步骤 3：活跃任务卡死检测

检查 `in_progress` 任务是否卡死，触发恢复：
1. **时间阈值**：task `updated_at` + `STUCK_THRESHOLD`（默认 300 秒）超过当前时间
2. **重启记录**：检查 `~/.ccc/opencode-pids/<task_id>.txt` 是否存在且包含 `clearlock` 关键字
3. **恢复动作**：移回 `planned/` 并删除 PID 文件，避免下次 Engine 启动时再次卡死

### 步骤 4：状态持久化 + 停滞检测

1. **状态文件**：`~/.ccc/patrol-state.json` 格式：
   ```json
   {
     "last_rounds": {
       "round_1": { "timestamp": 1699999999, ... },
       ...
       "round_6": { "timestamp": 1699999999, ... }
     },
     "stuck_tasks": {
       "task_id_1": { "count": 2, "blocked_at": 1699999999 },
       ...
     },
     "max_rounds_reached": false,
     "rounds_count": 6
   }
   ```

2. **停滞检测**：比较最近 `N` 轮的 `abnormal`、`stuck` 数量，如果连续 `N` 轮（`MAX_ROUNDS` 默认 6 轮）无变化，发出警告（当前尚未实现自动降频）

### 步骤 5：修复后 Commit

根据本轮操作生成 git commit，格式：
```
patrol: [engine: RESTARTED/DEAD] 清空 abnormal N 恢复 stuck task M rounds 无变化
```

### 步骤 6：报告输出

单行摘要输出到日志，格式：
```
[Engine存活]=True workspaces=5 abnormal=3 stuck=2 active=5 rounds=6
```

---

## 3. 配置参数

### 阈值参数
| 参数 | 默认值 | 含义 |
|------|--------|------|
| `HB_STALE_SECONDS` | 300 | Engine 心跳文件陈旧阈值（秒） |
| `STUCK_THRESHOLD` | 300 | in_progress 任务卡死时间阈值（秒） |
| `FORCE_MV_THRESHOLD` | 1800 | 强制移回 planned 的超时阈值（秒） |
| `MAX_ROUNDS` | 6 | patrol-state 保留的最大轮次数 |

### 工作区映射
| 名称 | 磁盘路径 | 只读 |
|------|----------|------|
| CCC | ~/program/CCC | 否 |
| qxo | ~/program/qx-observer | 否 |
| xianyu | ~/program/xianyu | 否 |
| qb | ~/program/projects/qb | 否 |
| qx | ~/program/projects/qx | 是 |

> **重要**：当前参数为**硬编码**，不读 `_config.py` 或环境变量。如需调参须直接改脚本。

### 文件路径
| 路径 | 用途 |
|------|------|
| `~/.ccc/patrol-state.json` | 状态持久化（最近 N 轮 + 卡死任务计数） |
| `~/.ccc/logs/engine-restarts.jsonl` | Engine 重启事件日志（JSONL） |
| `~/.ccc/opencode-pids/` | 崩溃循环检测 PID 目录 |
| `<workspace>/.ccc/.engine-heartbeat.json` | Engine 心跳文件（由 Engine 主循环写入） |

---

## 4. 部署方式

### 启动方式
Patrol 不单独运行，由 `ccc-loop-monitor.sh` 的 step 1 每轮调用：
```bash
python3 scripts/ccc-patrol-v4.py >> ~/.ccc/loop-monitor.log 2>&1
```

### 安装前提
- CCC 项目已 clone 到 `~/program/CCC`
- `install-ccc-roles.sh` 已执行（安装了 Engine plist 等基础设施）
- Engine 的 `.ccc/board/` 看板目录结构存在

### Launchd 集成
- Patrol 没有自己的 plist
- Engine plist `com.ccc.engine.plist` 保证 Engine 持续运行 → Engine 创造 Board 数据 → Patrol 消费 Board 数据
- 如果 Engine 死亡，Patrol 会通过三层回退策略尝试重启

---

## 5. 故障排查

### 场景 A：Engine 死亡且重启失败

**现象**：日志显示 `_engine_alive()` 返回 False，且三层回退都失败
**检查项**：
1. 检查 `~/.ccc/logs/engine-restarts.jsonl` 确认重启尝试历史
2. 运行 `launchctl list | grep com.ccc.engine` 确认 plist 是否加载
3. 检查 `/Library/LaunchDaemons/com.ccc.engine.plist` 文件路径和权限
4. 检查 macOS 系统日志 `log show --predicate 'process == "ccc-engine"' | tail -50`
**手动介入步骤**：
1. 手动运行 `launchctl bootstrap ~/Library/LaunchAgents com.ccc.engine.plist`
2. 或直接在命令行启动：`python3 scripts/ccc-engine.py --workspace ~/program/CCC`
3. 恢复后观察下一轮 patrol 日志，确认是否正常

### 场景 B：abnormal 积压不清理

**现象**：`abnormal` 列持续堆积，甚至占满队列
**检查项**：
1. 读取某个 abnormal 任务 `verdict/summary.md` 确认失败原因
2. 检查 `patrol-state.json` 的 `stuck_tasks` 是否有对应条目
3. 查看 `.ccc/plans/<task>.plan.md` 是否缺失或无效
**手动介入步骤**：
1. 对于合理的 abnormal（比如依赖外部服务）：手动移回 `planned/` 并在 report 中说明原因
2. 对于上游未完成的 abnormal：保持 `abnormal` 等上游恢复
3. 对于人为错误的 abnormal：手动修复 `verdict/summary.md`，然后移至 `released/`

### 场景 C：连续 N 轮无变化

**现象**：最近 `N` 轮 patrol 输出摘要中 `abnormal`、`stuck`、`active` 数量一致
**检查项**：
1. 确认 Engine 是否正常运行（心跳文件存在）
2. 确认 backlog 是否有新任务待处理
3. 查看 `ccc-loop-monitor.log` 确认 patrol 是否在正常执行
4. 手动统计最近 6 轮的 `patrol-state.json`（通过 git 历史回溯）
**应对**：
- **短期**：手动调整 back 队列任务，触发变动
- **长期**：实现 patrol 自动降频（如 `patrol-state.json` 中增加 `cooldown_remaining_seconds` 字段）

### 场景 D：心跳陈旧但进程存活（`_engine_alive=True` 但 `_stale_heartbeat`）

**现象**：`ps aux | grep ccc-engine.py` 显示进程存在，但心跳文件过期超过 300 秒，patrol 检测到陈旧
**根因**：Engine 主循环卡在非心跳分支（比如无限重试某个 API）
**应对**：按步骤 0 的三层回退重启 Engine，强制唤醒主循环更新心跳

### 场景 E：残留 opencode PID 文件

**现象**：`~/.ccc/opencode-pids/` 目录下存在 `task_id.txt` 但对应的 task 已不在 `in_progress` 或已成功
**检查项**：
1. 读取 PID 文件内容，运行 `ps -p <pid> -o pid,comm` 确认进程是否存在
2. 检查对应 task 的 board 状态（`in_progress` 是否已归位）
3. 查看 `engine-restarts.jsonl` 是否有 `clearlock` 重启记录
**处理**：
- 如果进程仍存在但 task 已完成 → 删除 PID 文件，记录为异常重启
- 如果进程已死 → 删除 PID 文件，补发桌面通知

### 场景 F：patrol-state.json 已损坏

**现象**：读取 `~/.ccc/patrol-state.json` 时抛出 JSON 解析错误或 KeyError
**应对**：
1. 备份损坏文件：`cp ~/.ccc/patrol-state.json ~/.ccc/patrol-state.json.bak`
2. 删除损坏文件：`rm ~/.ccc/patrol-state.json`
3. 下次 patrol 运行时会自动重建，`max_rounds_reached` 会重置为 `False`

---

## 6. 文件路径索引

| 路径 | 类型 | 说明 |
|------|------|------|
| `scripts/ccc-patrol-v4.py` | 源文件 | Patrol 主逻辑（955 行） |
| `scripts/ccc-loop-monitor.sh` | 脚本 | 每轮调用 patrol 的入口 |
| `scripts/ccc-engine.py` | 源文件 | Engine 主循环（写入心跳文件） |
| `scripts/ccc-notify.sh` | 脚本 | Engine 重启/死亡时发送桌面通知 |
| `<workspace>/.ccc/board/` | 目录 | 看板数据（patrol 消费） |
| `<workspace>/.ccc/.engine-heartbeat.json` | 文件 | Engine 心跳文件（patrol 检测来源） |
| `~/.ccc/patrol-state.json` | 数据文件 | patrol 状态持久化 |
| `~/.ccc/logs/engine-restarts.jsonl` | 日志文件 | Engine 重启事件流水 |
| `~/.ccc/opencode-pids/` | 目录 | opencode 进程 PID 文件（检测崩溃循环） |
| `docs/patrol-v4.md` | 文档 | 本说明书 |

---

## 7. 历史教训

Lessons from `docs/lessons.md`：
- **Lesson 43**：巡检必须覆盖所有工作区——曾只扫 CCC 漏掉 qxo/qb/qx 的异常
- **Lesson 44**：异常排查必须看 verdict/code 内容——不能只看数字
- **Lesson 45**：连续 N 轮无变化应自动降频（当前无自动降频机制）
- **Lesson 46**：abnormal 清理机制不完善——in_progress 滞留模式不匹配时需人工介入

---

## 8. 限制与已知问题

- **无 CLI 参数**——所有行为硬编码，无法通过命令行生效
- **无外部化配置**——调参须直接修改 `scripts/ccc-patrol-v4.py`，不支持环境变量或配置文件
- **无测试覆盖**——`tests/` 下无 patrol 相关测试用例
- **无并发保护**——同一时刻运行两个 patrol 实例无互斥锁，可能导致状态不一致
- **仅 macOS**——依赖 launchctl、osascript等 macOS 特有工具
- **不支持远程监控**——只在本地 M1 环境运行，无法远程巡检
- **停滞检测未自动降频**——连续 N 轮无变化时仅发出警告，未实现自动降频机制（参见 Lesson 45）

---

## 9. 快速参考

### 常用命令
```bash
# 手动运行 patrol（用于测试）
python3 scripts/ccc-patrol-v4.py

# 检查 Engine 心跳
cat ~/program/CCC/.ccc/.engine-heartbeat.json

# 查看 patrol 状态
cat ~/.ccc/patrol-state.json

# 查看引擎重启日志
tail -50 ~/.ccc/logs/engine-restarts.jsonl

# 检查残留 PID 文件
ls ~/.ccc/opencode-pids/

# 强制清理所有残留 PID
rm ~/.ccc/opencode-pids/*.txt
```

### 调参指引
如需修改 patrol 行为，编辑 `scripts/ccc-patrol-v4.py`，搜索以下关键字：
- `HB_STALE_SECONDS`：Engine 心跳超时
- `STUCK_THRESHOLD`：卡死检测阈值
- `FORCE_MV_THRESHOLD`：强制移回 planned 阈值
- `MAX_ROUNDS`：历史轮次保留数
- 工作区列表替换：替换 `WORKSPACE_PATHS` 字典

### 调试技巧
```bash
# 启用调试输出（修改源码，添加调试语句到日志）
# logs/patrol.log (当前输出到 ccc-loop-monitor.log)

# 单独重启 Engine（手动触发三层回退的第一层）
launchctl unload ~/Library/LaunchAgents/com.ccc.engine.plist
launchctl bootstrap ~/Library/LaunchAgents com.ccc.engine.plist

# 查看 loop-monitor 调用 patrol 的上下文
grep "patrol" ~/.ccc/loop-monitor.log
```
