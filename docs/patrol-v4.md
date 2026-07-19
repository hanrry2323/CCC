# Patrol v4 — CCC Engine 看门狗 + 自动化异常排查

> 本文档面向 CCC 开发者和运维人员,是 Patrol v4 的一站式参考。
> 另见: `scripts/ccc-patrol-v4.py` (源码)、`docs/lessons.md` (历史教训)、`scripts/ccc-loop-monitor.sh` (调用方)

---

## 1. 概述

### 定位

Patrol v4 (`ccc-patrol-v4.py`) 是 CCC Engine 的看门狗 + 自动化异常排查守护进程。每轮扫描解决三件事:
1. **Engine 还在不在** — 不在就重启
2. **有没有异常任务没人管** — 有就分类处理
3. **有没有任务卡死** — 有就恢复

### 流程总览

```
┌─────────────────────────────────────────────────────────────┐
│步骤 0: Engine 存活检测                                        │
│  → 检查 ~/.ccc/engine-heartbeat.json 时效性                  │
│  → 死: 三重回退重启 (launchctl bootstrap → launchctl load → Popen) │
│  → 活: 记录重启事件到 engine-restarts.jsonl                   │
└─────────────────────────────────────────────────────────────┘
    ↓ 存活
┌─────────────────────────────────────────────────────────────┐
│步骤 1: 扫描 5 个工作区                                         │
│  → 读取每个工作区的 board/index.json                         │
│  → 提取所有 label: [backlog, planned, in_progress, testing, │
│                     verified, released, abnormal]          │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│步骤 2: 异常排查 (三步法)                                      │
│  2.1 读取 note/updated_at 时间戳                             │
│  2.2 查验 verdict, report, plan 产出文件是否存在             │
│  2.3 分类移除:                                               │
│    - 有验证通过的 report → released                            │
│    - 有失败的 verdict → abnormal                              │
│    - 无产出但近 3 天未更新 → backlog (consecutive_skip >= 3) │
│    - retry_count >= 3 且 all_failed_or_skipped → abnormal    │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│步骤 3: 活跃任务卡死检测                                        │
│  条件 A: in_progress 全 terminal 但列继续                     │
│  条件 B: opencode-pids 已 clearlock 但 opencode 进程仍存活   │
│  动作: 取消 clearlock, 清理残留 PID 文件                      │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│步骤 4: 状态持久化 + 停滞检测                                    │
│  → 写入 patrol-state.json (最近 6 轮 + stuck_tasks)          │
│  → 检查 patrol-state.json 是否连续 MAX_ROUNDS 轮无变化         │
│  → 警告: 连续 6 轮无变化时输出 "WARNING: interval no change" │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│步骤 5: 修复后 Commit                                          │
│  → 如果有状态变更 → git add . && git commit                 │
│  → message 开头写 "(engine: RESTARTED/DEAD)" 或 "(engine: OK)" │
│  → 默认写 "(engine: OK)" (无 Engine 死亡)                     │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│步骤 6: 报告输出                                               │
│  → 单行摘要格式: "patrol: <actions> <engine-status>"          │
│  → 示例: "patrol: MOVE 5 backlog → back won abnormal | engine: OK" │
└─────────────────────────────────────────────────────────────┘

### 与其他组件关系

| 组件 | 关系 |
|------|------|
| Engine (ccc-engine.py) | Patrol 监控目标: 心跳检测 + 存活检查 + 自动重启 |
| Loop Monitor (ccc-loop-monitor.sh) | Patrol 调用方: loop-monitor 的 step 1 执行 patrol |
| Cockpit (ccc-cockpit-desktop) | 无直接集成, Tauri 桌面壳子可后续显示 patrol 状态摘要 |
| Notify (ccc-notify.sh) | Patrol 调用方: Engine 重启/死亡时发桌面通知 |

---

## 2. 功能列表

### 步骤 0: Engine 存活检测 (最高优先级)

Patrol 启动时首先检测 Engine 进程是否存在且心跳文件有效:

- **进程检测**: 通过 `ps aux | grep ccc-engine.py` 判断进程是否运行
- **心跳时效**: 检查每个工作区的 `.ccc/engine-heartbeat.json` 文件时间戳
  - 若心跳文件距今 < `HB_STALE_SECONDS` (默认 300 秒), 认为引擎健康
  - 若心跳陈旧但进程存活, 标记 `_stale_heartbeat=True`, 但不立即重启
- **死亡处理**: 若进程不存在或心跳陈旧:
  1. 尝试 `launchctl bootstrap` 加载 Engine plist
  2. 若失败, 尝试 `launchctl load` 直接加载
  3. 若仍失败, 使用 `subprocess.Popen` 启动后台进程
- **重启记录**: 每次成功重启后, 将事件写入 `~/.ccc/logs/engine-restarts.jsonl`

### 步骤 1: 扫描 5 个工作区

Patrol 硬编码扫描以下 5 个工作区:

| 名称 | 磁盘路径 | 备注 |
|------|----------|------|
| CCC | `~/program/CCC` | 主控项目 |
| qxo | `~/program/qx-observer` | QXO 监听器 |
| xianyu | `~/program/xianyu` | 游戏项目 |
| qb | `~/program/projects/qb` | 另一游戏项目 |
| qx | `~/program/projects/qx` | 只读工作区 |

**扫描逻辑**:
- 读取每个工作区的 `.ccc/board/` 目录
- 读取 `board/index.json`, 提取所有 `label` 字段
- 按 label 聚合任务计数: `backlog, planned, in_progress, testing, verified, released, abnormal`
- 跳过不存在的 `.ccc/board/` 目录 (静默失败)

### 步骤 2: 异常排查 (三步法)

对于 `abnormal` 标签且状态为 `in_progress` 的任务, 执行三步判定:

1. **读取时间戳**: 检查 `note/updated_at` 文件是否存在, 获取最近更新时间
2. **查验产出文件**: 检查以下文件是否存在:
   - `verdict/`: reviewer 得出的结论
   - `report/`: dev 完成任务的产出
   - `plan/`: product 的计划说明
3. **分类处理**:
   - **移除到 released**: 有关于通过验证的 report (约定: report.md 存在且不含 "failed" 关键字)
   - **移除到 abnormal**: 有失败的 verdict 或持续失败模式
     - `consecutive_skip >= 3`: 连续 3 轮跳过
     - `retry_count >= 3`: 重试次数 ≥3 次且所有尝试失败
     - `all_failed_or_skipped`: 所有子 phase 都失败或跳过
   - **留待处理**: 其他情况 (如无产出但更新时间充足)

**持续失败三态** 由 `patrol-state.json` 中的 `stuck_tasks` 字典维护。

### 步骤 3: 活跃任务卡死检测

检测两种卡死场景, 并自动恢复:

- **条件 A**: 当前运行的全部都在 `in_progress` terminal, 但任务滞留在 `in_progress` 列
  - 判定: `all_in_terminal && not all_completed` 且 `in_progress > 0`
  - 动作: 强制移回 `planned`
- **条件 B**: `opencode-pids/` 目录存在某任务 PID 文件 (`<stable_id>.lock`)
  - 检测目标: 文件存在但对应 opencode 进程已退出 (ps aux 搜索不到)
  - 动作: 删除 `.lock` 文件, 清理残留 PID (需要手动清理 `opencode-pids/` 目录)

### 步骤 4: 状态持久化 + 停滞检测

- **patrol-state.json** 格式:
  ```json
  {
    "ts": "2026-07-19T15:00:00+08:00",
    "stuck_tasks": {
      "<stable_id>": {"consecutive_skip": 3, "stuck_duration_seconds": 1800}
    }
  }
  ```
- **MAX_ROUNDS** (默认 6): 保留最近的轮次数
- **停滞检测**: 每轮检查 `patrol-state.json` 与上一轮的差异
  - 若连续 `MAX_ROUNDS` 轮没有任务修改 ( `MOVE` 事件), 输出警告
  - 示例: `patrol: WARNING: interval no change`

### 步骤 5: 修复后 Commit

- 若本轮有任何状态变更 (`abnormal` 清理, 卡死恢复), 触发 commit
- Commit 格式化为单行消息:
  - 默认: `patrol: [actions描述] | engine: OK`
  - Engine 死亡: `patrol: [actions描述] | engine: RESTARTED` 或 `engine: DEAD`
  - 例如: `patrol: MOVE 5 backlog → back won abnormal | engine: OK`
- Commit 后更新 `patrol-state.json` 记录当前时间戳

### 步骤 6: 报告输出

- Patrol 每轮执行结束后, 输出单行摘要日志
- 格式: `patrol: <actions> | engine: <status>`
- `actions` 使用简化表示法, 如:
  - `MOVE 3 backlog → back won abnormal`
  - `CLEARLOCK task123`
  - `CLEANUP opencode-pids/task123.lock`
- 示例:
  ```bash
  npm run patrol  # 手动执行 patrol
  ```
  输出:
  ```
  patrol: MOVE 3 backlog → back won abnormal | engine: OK
  ```

---

## 3. 配置参数

### 阈值参数

| 参数名 | 默认值 | 单位 | 含义 |
|--------|--------|------|------|
| `HB_STALE_SECONDS` | 300 | 秒 | Engine 心跳文件陈旧阈值, 超此时认为是 Engine 卡死 |
| `STUCK_THRESHOLD` | 300 | 秒 | in_progress 任务卡死时间阈值 (当前未使用) |
| `FORCE_MV_THRESHOLD` | 1800 | 秒 | 强制移回 planned 的超时阈值 (当前未使用) |
| `MAX_ROUNDS` | 6 | 轮次 | patrol-state.json 保留的最大轮次数 |
| `CONSECUTIVE_SKIP_THRESHOLD` | 3 | 轮次 | 判定任务连续失败的最小轮次 |

### 工作区映射

| 名称 | 磁盘路径 | 只读 | 说明 |
|------|----------|------|------|
| CCC | `~/program/CCC` | 否 | 主控项目 |
| qxo | `~/program/qx-observer` | 否 | QXO 监听器 |
| xianyu | `~/program/xianyu` | 否 | 游戏项目 |
| qb | `~/program/projects/qb` | 否 | 另一游戏项目 |
| qx | `~/program/projects/qx` | 是 | 只读工作区 (不修改) |

> 警告: 当前参数为**硬编码**, 不读 `_config.py` 或环境变量。如需调参须直接修改源码参数值。

### 文件路径

| 路径 | 用途 | 是否自动创建 |
|------|------|-------------|
| `~/.ccc/patrol-state.json` | 状态持久化 (最近 N 轮 + 卡死任务计数) | 是 |
| `~/.ccc/logs/engine-restarts.jsonl` | Engine 重启事件日志 (JSONL) | 是 |
| `~/.ccc/opencode-pids/` | 崩溃循环检测 PID 目录, 存放 `<stable_id>.lock` 文件 | 否 (需手动创建或 tmt 生成) |
| `~/.ccc/engine-heartbeat.json` | Engine 心跳文件, 每轮更新时间戳 | 是 |
| `.ccc/board/index.json` | 看板索引 (每个工作区) | 否 (由 Engine 生成) |

---

## 4. 部署方式

### 启动方式

Patrol 不单独运行, 由 `ccc-loop-monitor.sh` 的 step 1 每轮调用:

```bash
# ccc-loop-monitor.sh 内部调用
python3 scripts/ccc-patrol-v4.py >> ~/.ccc/loop-monitor.log 2>&1
```

**loop-monitor 流程** (简化):

```bash
#!/bin/bash
# ccc-loop-monitor.sh

while true; do
    step1_manual_run_patrol  # 执行 patrol
    step2_check_engine_alive  # 检查 Engine
    step3_scrape_knowns       # 概率性扫 backlog
    ...
done
```

### 安装前提

- CCC 项目已 clone 到 `~/program/CCC`
- `scripts/install-ccc-roles.sh` 已执行 (安装了 Engine plist 等基础设施)
- Engine 的 `.ccc/board/` 看板目录结构存在
- 若要在 Cockpit 中显示 patrol 状态, 需额外打通 Cockpit 与 patrol-state.json 的读取接口

### Launchd 集成

- Patrol 没有自己的 plist
- Engine plist `com.ccc.engine.plist` 保证 Engine 持续运行 → Engine 创造 Board 数据 → Patrol 消费 Board 数据
- 如果 Engine 死亡, Patrol 会通过 plist 尝试重启
- Patrol 相对脆弱: 若 Engine 终止但 launchctl 加载失败, 需手动介入

---

## 5. 故障排查

### 场景 A: Engine 死亡且三重重启都失败

**症状**: `ps aux | grep ccc-engine.py` 无输出, 静默运行无产出

**检查步骤**:
1. 查看日志: `cat ~/.ccc/loop-monitor.log | tail -20`
2. 检查 plist: `launchctl list | grep ccc.engine`
3. 手动尝试启动: `python3 scripts/ccc-engine.py`
4. 查看系统日志: `log show --predicate 'process == "Com.apple.xpc.launchd"' --last 10m`

**手动介入**:
```bash
# 1. 检查 launchd 状态
sudo launchctl list com.ccc.engine

# 2. 手动 load plist
sudo launchctl load -w ~/Library/LaunchAgents/com.ccc.engine.plist

# 3. 强制重启进程
pkill -9 -f ccc-engine.py
python3 scripts/ccc-engine.py &
```

### 场景 B: abnormal 积压不清理

**症状**: `board/abnormal/` 目录下堆积大量任务, 无人处理

**分析**: 可能是 Judge 判定逻辑偏差, 或 Patrol 三步法判定条件过于严格

**检查项**:
1. 查看 `note/updated_at` 文件: `cat .ccc/board/abnormal/<stable_id>/note/updated_at`
2. 检查 verdict/ 目录: `ls .ccc/board/abnormal/<stable_id>/verdict/`
3. 查看 report.md 内容: `cat .ccc/board/abnormal/<stable_id>/report/report.md`

**手动干预**:
```bash
# 1. 手动移回
mv .ccc/board/abnormal/<stable_id> .ccc/board/backlog/

# 2. 恢复
echo "Restored to backlog" > .ccc/board/abnormal/<stable_id>/note/restored_from_abnormal.md
```

### 场景 C: 连续 N 轮无变化

**症状**: patrol 输出 `WARNING: interval no change` 且无任务移动

**原因分析**:
- backlog 为空或所有任务都 stalled
- Engine 运行但无人提交任务
- loop-monitor 的手动调用频率过低

**对策**:
1. 检查 Engine 状态: `cat ~/.ccc/engine-heartbeat.json`
2. 手动触发某个任务: 从 oo-board 调度 backlog 任务到 planned
3. 调整 loop-monitor 频率: 修改 `ccc-loop-monitor.sh` 中的 `while sleep <seconds>` 时间

### 场景 D: 心跳陈旧但进程存活 (`_stale_heartbeat`)

**症状**: `patrol` 日志显示 `Engine heartbeat stale but process alive`, 但未触发重启

**原理**: Patrol 设计时选择"宁可信其有", 不在心跳老旧时强制重启 Engine, 以避免误杀

**检查步骤**:
1. Engineer 心跳文件: `cat ~/.ccc/engine-heartbeat.json`
2. Engine 日志: `tail -100 ~/.ccc/logs/engine.log`
3. Engine 主循环状态: `grep -A 5 "heartbeat" ~/.ccc/logs/engine.log`

**对策**: 若确认 Engine 卡死, 手动重启:
```bash
pkill -9 -f ccc-engine.py
python3 scripts/ccc-engine.py &
```

### 场景 E: 残留 opencode PID 文件

**症状**: `.ccc/opencode-pids/` 目录存在 `.lock` 文件, 但 opencode 进程已退出

**检查**:
```bash
# 查看残留 PID
ls -lh .ccc/opencode-pids/

# 搜索进程
ps aux | grep opencode

# 尝试清理
rm .ccc/opencode-pids/<stable_id>.lock
```

**对策**: 残留文件不影响功能, 但可能造成误导。若需要自动清理, 可扩展 Patrol 的步骤 3 逻辑。

### 场景 F: patrol-state.json 已损坏

**症状**: Patrol 启动时报错 `JSONDecodeError: Expecting value: line 1 column...`

**对策**:
```bash
# 1. 备份旧文件
cp ~/.ccc/patrol-state.json ~/.ccc/patrol-state.json.backup

# 2. 删除损坏文件 (重建)
rm ~/.ccc/patrol-state.json

# 3. patrol 自动重建
```

**注意**: 删除 `patrol-state.json` 会丢失卡死任务计数器, 改为初始状态重置。

---

## 6. 文件路径索引

| 文件路径 | 用途 | 读/写 | 备注 |
|----------|------|-------|------|
| `scripts/ccc-patrol-v4.py` | Patrol 主程序 | 脚本 | 955 行, 无参数无子命令 |
| `scripts/ccc-loop-monitor.sh` | Loop Monitor 调用方 | Shell脚本 | step 1 调用 patrol |
| `~/.ccc/engine-heartbeat.json` | Engine 心跳文件 | 读写 | 每轮追踪时间戳, Patrol 读取 |
| `~/.ccc/patrol-state.json` | Patrol 状态记录 | 读写 | 记录最近 6 轮 + 卡死任务 |
| `~/.ccc/logs/engine-restarts.jsonl` | Engine 重启日志 | 读写 | JSONL 格式, 每行一个事件 |
| `.ccc/board/index.json` | 看板索引 | 读取 | Engine 生成, Patrol 消费 |
| `.ccc/board/<stable_id>/note/updated_at` | 任务更新时间戳 | 读取 | patrol-state.json 依赖 |
| `.ccc/board/<stable_id>/verdict/` | Reviewer 结论 | 读取 | 三步法第二步查验 |
| `.ccc/board/<stable_id>/report/` | Dev 产出 | 读取 | 三步法第二步查验 |
| `.ccc/board/<stable_id>/plan/` | Product 计划 | 读取 | 三步法第二步查验 |
| `.ccc/board/abnormal/` | 异常任务目录 | 读写 | Patrol 移动操作目标 |
| `.ccc/opencode-pids/` | opencode PID 管理 | 读写 | 存放 `.lock` 文件 |
| `docs/lessons.md` | 历史教训沉淀 | 读取 | 避坑参考 |
| `docs/README.md` | docs 总目录 | 链接 | 建议添加 patrol-v4.md 引用 |

---

## 7. 历史教训

Lessons from `docs/lessons.md`:

- **Lesson 43**: 巡检必须覆盖所有工作区 — 曾只扫 CCC 漏掉 qxo/qb/qx 的异常 (2024-02-01)
  - 参考: `ccc-patrol-v4.py:245-251` 硬编码 5 个工作区
- **Lesson 44**: 异常排查必须看 verdict/report/code 内容 — 不能只看数字 (2024-02-02)
  - 参考: `ccc-patrol-v4.py:300-315` 三步法查验产出文件
- **Lesson 45**: 连续 N 轮无变化应自动降频 (当前无) — patrol-state 停滞检测 WARNING (2024-02-03)
  - 建议: 若连续 6 轮无变化, 可降低 loop-monitor 频率或发送通知
- **Lesson 46**: abnormal 清理机制不完善 — in_progress 滞留模式不匹配时需人工介入 (2024-02-05)
  - 参考: `ccc-patrol-v4.py:320-340` 卡死检测逻辑灵活调整

---

## 8. 限制与已知问题

- 无 CLI 参数 — 所有行为硬编码在源码中
- 无外部化配置 — 调参需直接修改 `scripts/ccc-patrol-v4.py` 的参数值
- 无测试覆盖 — tests/ 下无 patrol 前端测试
- 无并发保护 — 同一时刻运行两个 patrol 进程无互锁机制
- 仅 macOS — 依赖 launchctl、osascript、ps aux
- 不支持远程监控 — 只在 M1 本机运行, 无 HTTP API
- 停滞检测触发阈值卡死 — 连续 6 轮无变化才 WARNING, 可能错过早期停滞
- 心跳陈旧不触发重启 — 宁信 Engine 健康, 避免误杀 (谨慎起见)
- opencode PID 清理手动 — `.lock` 文件管理依赖于手动介入
- 无 Cockpit 集成 — 目前无 Dashboard 显示 patrol 运行状态
- 无日志分级 — 所有输出都写入 loop-monitor.log, 无 INFO/WARN/ERROR 分级

---

## 9. 附录

### A. 常用命令速查

```bash
# 手动运行 patrol
python3 scripts/ccc-patrol-v4.py

# 检查 Engine 心跳
cat ~/.ccc/engine-heartbeat.json

# 查看 patrol 状态
cat ~/.ccc/patrol-state.json

# 查看引擎重启日志
tail -10 ~/.ccc/logs/engine-restarts.jsonl

# 手动清理 opencode 残留 PID
rm ~/.ccc/opencode-pids/<stable_id>.lock

# 启动 Engine (调试用)
python3 scripts/ccc-engine.py --workspace ~/program/CCC
```

### B. 报告格式说明

| 日志字段 | 格式 | 示例 |
|----------|------|------|
| 动作描述 | `MOVE <数字> <源> → <目标>` 或 `CLEARLOCK <id>` 或 `CLEANUP <path>` | `MOVE 3 backlog → back won abnormal` |
| 引擎状态 | `engine: OK` | `patrol: MOVE 3 backlog → back won abnormal | engine: OK` |

### C. 扩展阅读

- [CCC 总览 — CLAUDE.md](../../CLAUDE.md)
- [CCC Engine 架构 — CLAUDE.md 第 7 角色系统章节](../../CLAUDE.md#7-角色系统--ccc-engine-v0201-架构)
- [Roadmap — docs/roadmap.md](../../docs/roadmap.md)
- [历史教训 — docs/lessons.md](../../docs/lessons.md#L43-L46)

---

**文档版本**: 1.0  
**最后更新**: 2024-01-01  
**维护者**: CCC Team
