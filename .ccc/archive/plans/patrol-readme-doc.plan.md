# Plan: patrol-readme-doc — Patrol v4 使用文档

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-patrol-v4.py`（955 行，单文件无子命令）
- **当前结构要点**：
  1. Patrol-v4 是一个无参数、无子命令的单文件脚本，`main()` 按序执行 6 步流程：Engine 存活检测 → 5 工作区扫描 → 异常排查（三步法）→ 活跃任务卡死检测 → 状态持久化+停滞检测 → 修复后 commit → 报告输出
  2. 所有配置（阈值、工作区列表、路径）硬编码在脚本中，不读 `_config.py` 或环境变量。关键参数：`HB_STALE_SECONDS=300`、`STUCK_THRESHOLD=300`、`FORCE_MV_THRESHOLD=1800`、`MAX_ROUNDS=6`
  3. 5 硬编码工作区：CCC→`~/program/CCC`、qxo→`~/program/qx-observer`、xianyu→`~/program/xianyu`、qb→`~/program/projects/qb`、qx→`~/program/projects/qx`（同名键值，qx 为只读）
  4. Engine 存活通过 `ps aux | grep ccc-engine.py` 检查心跳文件 `<ws>/.ccc/engine-heartbeat.json` 时效性，死亡时三层回退（launchctl bootstrap → launchctl load → Popen 后台）。重启记录到 `~/.ccc/logs/engine-restarts.jsonl`
  5. 异常排查三步法：读 note/updated_at → 检查 verdict/report/plan 产出 → 分类移 released/planned/backlog 或留 abnormal。持续失败三态：`consecutive_skip>=3`、`retry_count>=3`、`all_failed_or_skipped`
  6. 卡死检测基于 phases.json 全 done 但列滞留，或 opencode-pids 被 clearlock 重启。`patrol-state.json` 持久化最近 6 轮 + `stuck_tasks` 字典
  7. 无现有文档。`docs/` 下无 `patrol.md`。`docs/lessons.md` 含 4 条相关教训（43-46）关于全工作区覆盖、异常内容检查、停滞降频、abnormal 清理
  8. 无测试覆盖率。`tests/` 下无 patrol 测试
- **待改动点**：
  - `docs/patrol-v4.md`：全新文档文件。结构要求：功能列表、配置参数、部署方式、故障排查

---

## 范围

- **目标**：在 `docs/` 下创建完整的 Patrol v4 使用说明书，覆盖功能列表、配置参数、部署方式、故障排查四部分，作为开发者和运维者的一站式参考
- **只改文件**：`["docs/patrol-v4.md"]`
- **不改文件**：`["scripts/ccc-patrol-v4.py", "scripts/ccc-engine.py", "scripts/_config.py", "scripts/ccc-cockpit.py", "scripts/ccc-loop-monitor.sh", "scripts/ccc-notify.sh", "tests/"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：创建 docs/patrol-v4.md 使用文档

### 做什么

在 `docs/` 下创建 `patrol-v4.md` 文档，作为 Patrol v4 使用说明书。需要完整覆盖以下 5 个章节：

1. **概述**：Patrol 的定位（Engine 的看门狗 + 自动化异常排查），架构示意（6 步流程总览），与 CCC 其他组件的关系（Engine/Cockpit/Loop-Monitor）
2. **功能列表**：逐一说明 6 步流程的每步做什么，含 Engine 存活检测的三大回退策略、异常排查的三步判定法、卡死检测的两种触发条件、停滞检测的 N 轮无变化警告
3. **配置参数**：列出所有硬编码参数表，含参数名、默认值、含义，以及工作区映射表。注明"当前为硬编码，未来可能外部化"
4. **部署方式**：启动方式（被 `ccc-loop-monitor.sh` 调用）、launchd 集成（`com.ccc.engine.plist` 不直接包含 patrol，但 patrol 依赖 Engine 运行）、安装前提（`install-ccc-roles.sh`）、状态文件路径清单
5. **故障排查**：常见场景与对策。包括：Engine 死亡且三重重启都失败、abnormal 任务积压不清理、patrol-state.json 轮次无变化警告、心跳陈旧但进程存活、残留 opencode PID 文件

此外附加：
- **文件路径索引**：所有 patrol 相关文件的路径与说明的汇总表
- **历史教训**：引用 `docs/lessons.md` 中 4 条与 patrol 相关的教训，供新开发者避坑

### 怎么做

**1a. `docs/patrol-v4.md`** — 全新文件，放在 `docs/` 目录下。

结构：

```markdown
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
[插入 ASCII 流程图，标注 6 步流程与决策分支]

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

[详细说明 ps aux 检测 + 心跳时效判断 + 三层重启回退]

### 步骤 1：扫描 5 个工作区

[说明 5 个硬编码工作区 + board/index.json 读取]

### 步骤 2：异常排查（三步法）

[三步判定法 + 三种移动目标 + 持续失败三态]

### 步骤 3：活跃任务卡死检测

[两种触发条件 + 自动恢复动作]

### 步骤 4：状态持久化 + 停滞检测

[patrol-state.json 格式 + MAX_ROUNDS + 连续 N 轮无变化警告]

### 步骤 5：修复后 Commit

[commit 格式 + 可选 (engine: RESTARTED/DEAD) 后缀]

### 步骤 6：报告输出

[单行摘要格式示例]

---

## 3. 配置参数

### 阈值参数
| 参数 | 默认值 | 含义 |
|------|--------|------|
| `HB_STALE_SECONDS` | 300 | Engine 心跳文件陈旧阈值（秒） |
| `STUCK_THRESHOLD` | 300 | in_progress 任务卡死时间阈值 |
| `FORCE_MV_THRESHOLD` | 1800 | 强制移回 planned 的超时阈值 |
| `MAX_ROUNDS` | 6 | patorl-state 保留的最大轮次数 |

### 工作区映射
| 名称 | 磁盘路径 | 只读 |
|------|----------|------|
| CCC | ~/program/CCC | 否 |
| qxo | ~/program/qx-observer | 否 |
| xianyu | ~/program/xianyu | 否 |
| qb | ~/program/projects/qb | 否 |
| qx | ~/program/projects/qx | 是 |

> 当前参数为**硬编码**，不读 `_config.py` 或环境变量。如需调参须直接改脚本。

### 文件路径
| 路径 | 用途 |
|------|------|
| `~/.ccc/patrol-state.json` | 状态持久化（最近 N 轮 + 卡死任务计数） |
| `~/.ccc/logs/engine-restarts.jsonl` | Engine 重启事件日志（JSONL） |
| `~/.ccc/opencode-pids/` | 崩溃循环检测 PID 目录 |

---

## 4. 部署方式

### 启动方式
Patrol 不单独运行，由 `ccc-loop-monitor.sh` 的 step 1 每轮调用：
```
python3 scripts/ccc-patrol-v4.py >> ~/.ccc/loop-monitor.log 2>&1
```

### 安装前提
- CCC 项目已 clone 到 `~/program/CCC`
- `install-ccc-roles.sh` 已执行（安装了 Engine plist 等基础设施）
- Engine 的 `.ccc/board/` 看板目录结构存在

### Launchd 集成
- Patrol 没有自己的 plist
- Engine plist `com.ccc.engine.plist` 保证 Engine 持续运行 → Engine 创造 Board 数据 → Patrol 消费 Board 数据
- 如果 Engine 死亡，Patrol 会通过 plist 尝试重启

---

## 5. 故障排查

### 场景 A：Engine 死亡且重启失败
[检查项 + 手动介入步骤]

### 场景 B：abnormal 积压不清理
[检查三项文件产出 + 手动移回]

### 场景 C：连续 N 轮无变化
[确认 Engine 健康 + 变更 backlog 任务]

### 场景 D：心跳陈旧但进程存活（`_engine_alive=True` 但 `_stale_heartbeat`）
[Engine 主循环卡在非心跳分支 + 重启策略]

### 场景 E：残留 opencode PID 文件
[opencode-pids/ 目录存在死 PID + 手动清理]

### 场景 F：patrol-sate.json 已损坏
[删除后重建 + 丢失卡死计数器]

---

## 6. 文件路径索引

[汇总表：所有 patrol 读写文件的路径与说明]

---

## 7. 历史教训

Lessons from `docs/lessons.md`：
- **Lesson 43**：巡检必须覆盖所有工作区——曾只扫 CCC 漏掉 qxo/qb/qx 的异常
- **Lesson 44**：异常排查必须看 verdict/code 内容——不能只看数字
- **Lesson 45**：连续 N 轮无变化应自动降频（当前无自动降频机制）
- **Lesson 46**：abnormal 清理机制不完善——in_progress 滞留模式不匹配时需人工介入

---

## 8. 限制与已知问题

- 无 CLI 参数——所有行为硬编码
- 无外部化配置——调参需直接改脚本
- 无测试覆盖——tests/ 下无 patrol 测试
- 无并发保护——同一时刻运行两个 patrol 实例无互斥
- 仅 macOS——依赖 launchctl、osascript
- 不支持远程监控——只在 M1 本机运行
```

注意：文档撰写时从 `scripts/ccc-patrol-v4.py` 源码中提取所有准确参数值。上面的参数值（HB_STALE_SECONDS=300 等）必须在写文件时对照源码确认，以源码实际值为准。每个章节的详细说明需参考源码对应代码位置。

### 验收清单

- [ ] `docs/patrol-v4.md` 存在且可读（`cat docs/patrol-v4.md` 正常输出）
- [ ] 5 个主要章节完整：概述、功能列表、配置参数、部署方式、故障排查
- [ ] 概述节包含 patrol 的定位说明和 6 步流程概览
- [ ] 功能列表节逐一说明 6 步流程，每步用 2-5 句自然语言描述
- [ ] 配置参数节包含阈值参数表和工作区映射表，参数值与 `scripts/ccc-patrol-v4.py` 源码一致
- [ ] 部署方式节包含启动方式（ccc-loop-monitor.sh 调用）、安装前提、launchd 关系说明
- [ ] 故障排查节包含至少 4 个常见场景及对策
- [ ] 包含文件路径索引汇总表
- [ ] 引用 `docs/lessons.md` 中所有与 patrol 相关的历史教训
- [ ] 限制与已知问题节诚实说明当前局限
- [ ] 文档使用中文正文，专业术语保留英文原文
- [ ] 无代码/配置/路径拼写错误

### 验收

- [文件存在] `cat docs/patrol-v4.md` → 正常输出，文件创建成功
- [章节完整性] `grep -c "^## " docs/patrol-v4.md` → 应 >= 5 个二级标题章节
- [参数准确性] `grep "HB_STALE_SECONDS" docs/patrol-v4.md` → 包含该参数名
- [参数准确性] `grep "MAX_ROUNDS" docs/patrol-v4.md` → 包含该参数名
- [源码一致性] 文档中的参数值（HB_STALE_SECONDS=300, STUCK_THRESHOLD=300, FORCE_MV_THRESHOLD=1800, MAX_ROUNDS=6）与 `scripts/ccc-patrol-v4.py` 中定义一致
- [工作区列表] 文档覆盖 5 个工作区且 qx 标注为只读
- [故障场景] `grep -c "### 场景" docs/patrol-v4.md` → >= 4 个故障场景
- [历史教训] `grep "Lesson" docs/patrol-v4.md` → 至少 3 条 Lesson 引用
- [限制] `grep -i "限制\|已知问题\|局限" docs/patrol-v4.md` → 有限制章节

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 创建 docs/patrol-v4.md，覆盖概述、功能列表、配置参数、部署方式、故障排查 5 大章节 + 文件路径索引 + 历史教训 + 已知问题 | `docs(patrol): 创建 Patrol v4 使用说明书 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查（N/A — 纯文档，无代码改动）
- [ ] diff 范围仅限 `docs/patrol-v4.md`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] 文档中的参数值经源码确认一致
- [ ] 章节结构完整、逻辑连贯
- [ ] 无错别字、无路径拼写错误

---

## 后续步骤

完成文档后，建议：
- 链接在 `README.md` 中添加 `docs/patrol-v4.md` 的引用
- 后续 patrol 代码改动（如外部化配置、增加 CLI 参数）后应同步更新本文档
- Cockpit Dashboard 后续可增加 patrol 运行状态指示器（最近一轮时间、Engine 健康度等）