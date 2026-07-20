# CCC 自动化成熟度等级 + 架构评估

> 2026-07-14 定案

---

## 一、自动化等级定义（L1-L4）

参考 SAE 自动驾驶分级思路，定义 AI Coding 自动化成熟度：

| 等级 | 名称 | 谁驱动 | 谁执行 | 谁兜底 | 典型特征 |
|------|------|--------|--------|--------|----------|
| **L1** | 辅助 | 人 | AI 辅助 | 人 | 代码补全、片段生成、人工看每个 diff |
| **L2** | 部分自动 | 人定方向 | AI 干活 | 人 reviewer | pipeline 跑通但常断，要人接 |
| **L3** | 有条件自动 | AI 跑通 | AI 干活 | AI 兜底+人抽查 | pipeline 自愈，异常自动处理 |
| **L4** | 高度自动 | AI 规划 | AI 执行 | AI 全权+人定目标 | AI 自主拆任务、开发、验证、发布 |

---

## 二、CCC 当前定级：**L2（部分自动）**

### 已具备（L2 baseline）

```
✅ backlog → planned → ip → testing → verified → released 全链跑通
✅ 多 workspace 并行（CCC / qxo / xianyu）
✅ product_role 自动拆任务 + 写 plan/phases
✅ dev_role 自动执行（opencode）
✅ reviewer + tester 门禁
✅ kb_role 发布
✅ Patrol v4 自动巡检（6 步：存活检测 → 扫描 → 异常排查 → 卡死检测 → commit → 报告）
✅ crontab + launchd 每 5 分钟持续监控
✅ 日志轮转
✅ phase 依赖解析、失败传染、跳过
```

### 缺什么到 L3

| 缺口 | 影响 | 优先级 |
|------|------|--------|
| **无反馈回路**：失败任务→lessons→优化 product_role | 同样原因反复失败 | H |
| **无自适应调参**：timeout/retry 写死 | 简单 task 跑太快，复杂 task 不够用 | H |
| **reviewer 失败不记教训** | reviewerer 重复发现同类问题 | H |
| **Engine 重启丢上下文** | 内存 active_tasks 没持久化 | H |
| **xianyu/qb 任务高失败率** | 2 workspace 实际停摆 | M |
| **patrol 不走 FileBoardStore** | index.json 持续不一致 | M |
| **无告警通知** | 断了没人知道 | M |
| **单 Engine 单点** | 挂了 patrol 重启，但中间有盲区 | L |

### 缺什么到 L4

| 缺口 | 影响 |
|------|--------|
| AI 自主规划 roadmap（现在是我写 backlog） | L3 仍需人投喂任务 |
| 跨 workspace 智能调度（不再轮流，按负载/优先级） | 资源利用率低 |
| 自动版本发布（released → CHANGELOG → VERSION bump → git tag） | 版本管理手动 |
| 失败根因分析 + 自动修 | 现在只能移走不能修 |
| 代码质量自进（lint/type/test 不通过→自动回滚） | 质量靠 reviewer 把关 |
| 自动生成新 task（audit_role 发现缺陷→写 backlog） | 靠我手动注入 |

---

## 三、架构评估

### 架构图（当前）

```
                    ┌─────────────┐
                    │   Patrol    │ ← crontab/launchd 每 5min
                    └──────┬──────┘
                           │ 读/写 board/*.jsonl
                    ┌──────▼──────┐
  ┌─────────────────┤   Engine    ├─────────────────┐
  │                 │  (单进程)    │                 │
  │                 └──────┬──────┘                 │
  │                        │                        │
  ▼                        ▼                        ▼
┌──────┐            ┌──────────┐            ┌──────────┐
│ board│            │ opencode │            │ ccc-board│
│.jsonl│            │ subproc  │            │ 模块函数 │
└──────┘            └──────────┘            └──────────┘
```

### 做对的

| 决策 | 理由 |
|------|------|
| **文件即状态** | 每个 task 一个 JSONL，可 grep/cat/debug，不需要连 DB |
| **Engine 单进程** | 避免分布式一致性问题，MAX_CONCURRENT 控制并发 |
| **Patrol 独立进程** | 与 Engine 解耦，Engine 挂了 patrol 能重启它 |
| **FileBoardStore 抽象** | 所有 board 操作收口，方便换后端 |
| **7 角色职责分离** | 每个角色单一职责，可独立迭代 |
| **Phase 依赖链** | JSONL 格式 + 拓扑排序，清晰可查 |

### 架构风险

| # | 风险 | 严重度 | 说明 |
|---|------|--------|------|
| **R1** | **文件并发写入** | H | Engine 和 patrol 同时写同一个 task 的 JSONL 可能丢数据。当前靠 atomic rename 缓解但不彻底 |
| **R2** | **patrol 不走 FileBoardStore** | H | `_move_task` 直接 shell mv，跳过列迁移校验和 index.json 更新 |
| **R3** | **index.json 持续不一致** | M | 4 个写入者（Engine / patrol / product_role / dev_role）写入后不保证更新 index |
| **R4** | **active_tasks 纯内存** | H | Engine 重启后丢所有活跃任务上下文，全靠 `_recover_tasks()` 猜 |
| **R5** | **opencode 子进程变成孤儿** | M | Engine SIGTERM → opencode 变孤儿进程 → patrol 检测到"无进程" → 任务被移走 |
| **R6** | **配置散落 3 处** | M | `_config.py` / env vars / CLAUDE.md 三处定义同类参数 |
| **R7** | **workspace 发现靠文件扫描** | L | `~/program/*` 下所有带 `.ccc/board` 的目录都被当成 workspace |
| **R8** | **无集成测试** | H | 只有单元测试（288 tests），没有 Engine+board+opencode 联调测试 |
| **R9** | **单点故障** | M | 一台机器跑了 Engine + board-server + patrol + cockpit，全挂了就全挂 |

### 紧急修（这个月）

```
R2 → patrol 走 FileBoardStore.move_task() 而不是直接 shell mv
R4 → active_tasks 持久化到 JSONL（Engine 启动时读）
R6 → 统一配置源，env 覆盖 config.py 覆盖默认值
```

### 短期修（下个月）

```
R1 → 所有 board 写入加文件锁（fcntl.flock 或 lockf）
R3 → move_task 后自动更新 index.json
R8 → 加 Engine E2E 测试（mock opencode）
```

### 架构结论

**当前架构对 L2 够用，但到 L3 必须修 R2/R4/R6。** 核心问题是"文件并发写入"和"状态不一致"——L3 需要自愈能力，而自愈依赖可靠的状态视图。状态视图不可靠，自愈就是乱治。

文件系统作为状态存储本身不是问题（git 也是文件系统），问题是多个写入者没协调。**统一写入路径到 FileBoardStore + 加锁** 就能解决大部分问题。
