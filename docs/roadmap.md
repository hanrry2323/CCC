# CCC 发展路线图

> **当前状态(2026-07-07)**:
> - **v0.6 调度器集成阶段**:已完成(v0.6-ide-scheduler, git history)
> - **v0.7 阶段**(v0.7-slim → v0.7f 共 9 子任务):全部 PASS,**v0.7.0** 2026-07-07 收束
> - **v0.8 阶段**(OpenCode CLI 执行端重构):全部 PASS,**v0.8.0** 2026-07-07
> - **v0.9 阶段**(model provider 修复 + 飞轮/队列简化版):全部 PASS,**v0.9.0** 2026-07-07
> - **v0.10 阶段**(修 v0.9b 雷 + 队列 commit/状态):全部 PASS,**v0.10.0** 2026-07-07
> - **v0.11 阶段**(开箱即用调度 + 队列真测试):全部 PASS,**v0.11.0** 2026-07-07
> - **当前最新版本**:v0.11.0(push + tag 已打,见 git ls-remote)
>
> **范式转变(2026-07-07)**:v0.11 起,CCC 默认模式 = "opencode 写 + 人工 review"。
> opencode loop/flash 写工程代码质量已超 v0.7 时代人工基线(Lesson 35)。
>
> 本文件保留作为 v0.5 时期路线设计的历史存档。**新任务参考 `.ccc/state.md`** + `CHANGELOG.md`。

---

## v0.5 时期路线设计(历史存档)

> v0.5 是关键转折：CCC 从「framework 代码库」转型为「SKILL 资产」。
> 本节记录当时规划的方向,实际执行进度见上方"过期标注"。

---

## 当前版本:v0.7.0(2026-07-07,见 CHANGELOG.md)

### 已完成（v0.5.0 重构）

- [x] CCC 定位从 framework 改为 SKILL 资产
- [x] `SKILL.md` 重写为单一 prompt 资产（**含义**：**C**onnect — **C**laude **C**ode）
- [x] 引入红线条目：
  - 红线 11（Verifier 必须写 verdict 文件，Lesson 28 配套）
  - 红线 12（禁止 agent 自主启用 CCC）
- [x] 经验教训沉淀到独立 lessons.md：
  - Lesson 27（`claude -p` 真实语义，prompt 走 stdin）
  - Lesson 28（口头 PASS 不算 PASS，Verifier 必须有产物证据）
- [x] 文档分层：
  - `SKILL.md` — agent prompt 入口（**唯一注入**）
  - `README.md` — 项目介绍 / 30 秒上手
  - `CLAUDE.md` — 框架总纲（面向维护者，不注入 agent）
  - `references/red-lines.md` — 11 + 2 红线细则
  - `docs/lessons.md` — 框架级教训沉淀
  - `docs/roadmap.md` — 本文件
  - `docs/architecture.md` — 框架说明书
- [x] 与 qxo 项目解耦（`projects/qxo/lessons.md` → `docs/lessons.md`）

### 关键设计决策

| 项 | 决策 | Why |
|---|------|-----|
| CCC 形态 | SKILL 资产 | 不挑 IDE，可移植，迁移性最强 |
| 三角色 | Planner / Executor / Verifier 严格分离 | 防 Planner 越界 = 防红线 8 |
| 工作目录 | 由 agent 当前目录决定 | 不绑死 IDE / 项目 |
| IDE 选择 | 用户自选 | Trae / Cursor / Zed / VS Code 都可以 |
| 模型选择 | 由用户或中转站路由 | 灵活度最大 |
| CCC 启用 | **用户显式触发**，agent 不自主启用 | 红线 12，防意识漂移 |

---

## v0.6.0 — IDE 定时任务自动唤起

### 目标

CCC 当前需要用户显式触发。v0.6 让 IDE 自动定时唤醒 CCC 跑下一阶段。

### 具体动作

- **Trae 路线**：利用 launchd 配置定时任务，周期唤起 CCC 跑 plan
- **通用路线**：cron / Task Scheduler 包装 CCC 执行器
- **配套机制**：watchdog 已有，加一层"任务表驱动"循环

### 验收

- 配 1 个 launchd plist 跑 CCC 自动化 demo
- 任务能被列出 / 优先级排序 / 失败重试

### 关键风险

- 自动执行可能误触红线 8（Planner 越界 commit）—— 已通过禁止自动 commit 解决
- watchdog 必须存活，否则死锁

### 工程化补单（实操清单）

| 文件 | 用途 | 行数 |
|------|------|------|
| `scripts/ccc-scheduler.sh` | 任务表驱动循环（输入 `.ccc/` queue，输出调 Executor） | ~50 |
| `scripts/ccc-task-done.sh` | 任务完成回调（自动 commit + 解锁下一任务） | ~30 |
| `references/adapters/scheduler-launchd.md` | launchd 接入规范 + plist 模板 | ~80 |
| `examples/scheduler/ccc-queue.plist` | 可直接 `launchctl load` 的 plist 模板 | ~30 |

### 红线 13（v0.6 配套）— **新增**

> **禁止在没有 watchdog 通过的情况下启动 IDE 定时任务**

- **Why**：调度循环高频触发，如果 watchdog 失效 → 自动 fail-loop 死锁
- **机制**：`scripts/ccc-scheduler.sh` 启动前 `bash scripts/executor-watchdog.sh || exit 2`
- **触犯后果**：Critical — 自动 fail-loop 烧预算；调度器必须立刻暂停

---

## v0.7.0 — 知识飞轮对接

### 目标

`quality_flywheel.py`（V8.2-Q 已有）实际跑起来：
- 自动扫描 report / verdict → 提取失败模式
- 把高频模式沉淀成新的红线 / lessons
- 红线从「人工维护」变成「自我进化」

### 具体动作

- 在 `.ccc/` 下接入飞轮入口
- 每周跑一次扫描，写 `docs/lessons.md` 增量
- 红线条目（`references/red-lines.md`）自动 diff 提案，**人工 review 才合并**

### 验收

- 跑 1 个真实任务的 report，飞轮建议 1 条新红线
- 人工 review 后，写入 references/red-lines.md（不超过 5 分钟 / 条）

### 关键风险

- 自动飞轮可能"伪发现"——人工 gate 必须实
- lessons 膨胀到噪音级别——de-dup 机制要硬

### 工程化补单（实操清单）

| 文件 | 用途 | 行数 |
|------|------|------|
| `scripts/quality-flywheel.py` | 扫描 reports/verdicts，提取失败模式 | ~100 |
| `scripts/lesson-merge.py` | lesson dedupe 算法（防 lessons 膨胀） | ~80 |
| `references/flywheel-protocol.md` | 飞轮运行协议 + 人工 gate 流程 | ~60 |
| `scripts/quality_flywheel/<module>.py` | 从 qx-observer/app/core/quality_flywheel.py 抽取独立 | ~200 |

### 模块迁移路径

`quality_flywheel.py` 现在嵌在 `~/program/qx-observer/app/core/`，v10 cleanup 后会迁到 `app/services/quality/flywheel.py`。**v0.7 加一步**：把它**抽成 CCC 独立模块**（不依赖 qx-observer），CCC 与 qx-observer **逻辑解耦**——飞轮是 CCC 的能力，不是 qx-observer 的能力。

### 红线 14（v0.7 配套）— **新增**

> **飞轮发现的"红线候选"必须经过人工 review 才合并**

- **Why**：AI 自动归纳失败模式容易"伪发现"——把一次性 / 边缘 case / 项目专属问题误判为通用模式
- **机制**：飞轮只生成 `.ccc/abnormal-reports/flywheel-candidate-<date>.md`，**不直接写** `references/red-lines.md`
- **触犯后果**：Warning — 减少人工 gate 必经入口；如果直接合入，1 周内回滚

---

## v1.0.0 — 跨设备集群 Agent 军团（**最终目标**）

> CCC v1.0 = 完整的 Loop Engineering：跨设备、跨项目、跨 IDE、统一 agent 调度网络。
> 老板原话："1.0 最终目标是跨设备集群内调用 agent；涉及到项目同步，算力平衡，中转站。"

### 核心架构（4 层）

```
┌──────────────────────────────────────────────────────────┐
│  L4 — Human / IDE 接口层                                 │
│  Trae / Cursor / Zed + user                              │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  L3 — CCC 调度中心（单 IDE 内）                          │
│  - 三角色 + 4 文件契约 + 红线                            │
│  - 本地任务表 → 派单 / 状态机                             │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  L2 — Cluster Bus（项目总线）                            │
│  - 项目同步（git push/pull）                              │
│  - 算力路由（CPU/RAM/queue 长度分派）                    │
│  - 任务队列（优先级、重试、escalation）                   │
│  - 中转站路由（127.0.0.1:4000，按任务选 model）          │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  L1 — Device Agents（设备节点）                          │
│  - M1 (本机) / feiniu (ollama) / qb cluster              │
│  - 每个节点 = 一个 ccc-executor                           │
│  - 健康心跳 + watchdog 二级                                │
└──────────────────────────────────────────────────────────┘
```

### 借鉴来源：clawmed-ai Universal Worker v3.1（**借鉴思路，不照搬代码**）

> 评估日期：2026-07-06
> 来源：`/Users/apple/program/projects/clawmed-ai/{plans,reviews,workers,scripts}/`
> 关键文档：`plans/universal-worker-v3.1.md` + `reviews/universal-worker-v3.1-review.md`
> + `plans/T1.2_worker_analysis.md`

clawmed-ai 已经做过 worker 调度 / 能力标签 / 任务队列的尝试，**真实证据**：
- `task_queue.json` 4 任务中 3 个失败（任务超时 2 小时）→ **PoC 不切实际是真实风险**
- `worker_v3.py` 能力标签代码**被注释掉未启用**（review 标 FAIL）→ 防"写了不用"
- 架构：`scheduler → chunk 队列 → worker poll 拉取 → subprocess.run(command)`
- 心跳协议：30 秒一次，90 秒超时假死
- 没有 Agent 互调（**单一调度器**，自证 v1.0 禁互调合理）

### 借鉴来源扩展：agentmesh 社区共识（2025-11 同期 GitHub 真实项目）

> 研究日期：2026-07-06
> 输出位置：`~/research-bundles/ccc-v0.5-validation/C-cluster-distributed-agents.md`
> 状态：snippet 级确认，受 GFW 限制无法直接 fetch 原 README

CCC v1.0 的 capability-based cluster bus 设计在 GitHub 上有 **6+ 个 2025-2026 真实项目**：

| 项目 | 关键设计点 | 借鉴价值 |
|------|-----------|---------|
| [mesha-framework/mesha](https://github.com/mesha-framework/mesha) | "Kubernetes for agent runtimes"，多 runtime（Claude/Codex/Cursor）统一协议 | **直接对标** CCC v1.0——其抽象正是 CCC 想要的 |
| [agentmesh-labs/agentmesh](https://github.com/agentmesh-labs/agentmesh) | **TCP service registration + capability-based task routing** | **直接复用**——和 CCC v1.0 第 2 件事 1:1 |
| [dmontgomery40/agent-mesh](https://github.com/dmontgomery40/agent-mesh) | Python + MCP integration + 角色 dispatcher + eval system | **借鉴**：CCC 已是 MCP-heavy（`mcp__code-review-graph`）——可融合 |
| [Abinesh-Mathivanan/agentmesh](https://github.com/Abinesh-Mathivanan/agentmesh) | **mDNS-style service registration + capability routing** | 同模式，PoC 起点 |
| [rusty-robot/agent-mesh](https://github.com/rusty-robot/agent-mesh) | Distributed agent orchestration | 主题同 |
| [cnchenhaibin/agentMesh](https://github.com/cnchenhaibin/agentMesh) | Java LLM 分布式多 agent 协作（2024-01 老牌） | 跨语言实现参考 |

### agentmesh 社区共识（**借鉴参考**）vs CCC v1.0

| 设计点 | agentmesh 共识 | CCC v1.0 路线 |
|-------|---------------|--------------|
| **Discovery 协议** | TCP / mDNS service registration |  ✓ 已规划 |
| **Capability declaration** | node 注册时声明 `capabilities: []` |  ✓ 已规划（3 档 L1/L2/L3） |
| **Task routing** | capability-based + dynamic load balancing |  ✓ 已规划 |
| **Multi-backend** | Claude / OpenAI / local 都支持 |  ✓ ai-loop-router 已有 |
| **MCP integration** | dmontgomery40 已实现 |  ✓ CCC 已 MCP-heavy |

### agentmesh 社区**没共识**（= CCC 创新点 / 反借鉴）

| 设计点 | 社区状态 | CCC v1.0 反借鉴 |
|-------|---------|---------------|
| **跨设备 sync 冲突处理** | 几乎无项目严肃实现——假设 single-machine |  CCC 必须新设计（FSM + abnormal-reports） |
| **commit 幂等性**（红 15） | 较少提及 |  ✓ CCC 已计划（chunk_id 思路） |
| **cluster bus auth (mTLS)** | **所有项目均未做** |  ✓ CCC 反借鉴（必做） |
| **任务队列持久化 + retry 决策字段** | 大多在内存里 |  ✓ CCC 已计划（借鉴 clawmed 失败教训） |
| **跨 IDE / 跨 SKILL 抽象** | 仅 MESHA 对准 |  ✓ CCC 与 MESHA 同方向（MESH A = agent runtime orchestrator，**这是 CCC 的对标项目**） |
| **第一类公民 = "cluster bus"** | **无** |  CCC v1.0 跑出来 = 该领域早期 production |

### CCC v1.0 借鉴评估表修订

| 雷 | clawmed 借鉴 | agentmesh 借鉴 | 综合策略 |
|---|-------------|---------------|---------|
| 1. git sync 冲突 | 思路可用（中） | 几乎无借鉴 | 借鉴 clawmed chunk_id 思路 + 新 FSM + abnormal-reports |
| 2. Agent 互调成环 | 空（clawmed 单一调度） | 共识倾向"不互调" | **直接禁** |
| 3. 算力路由伪优化 | 部分借鉴（capability） | **强借鉴**（agentmesh 共识） | capability-based dispatch + **红 18 防失效** |
| 4. 模型 + 算力耦合 | 无 | dmontgomery40 启发 | dispatcher [node_id, model_tier, est_cost] 三元组 |
| 5. PoC 不切实际 | 强借鉴失败教训 | 几乎所有 agentmesh 都没严肃 PoC | **降级 1 任务** |
| 6. cluster bus 安全 | 反借鉴（clawmed 无 auth） | **强反借鉴**（6 项目均无 auth） | mTLS + node fingerprint 必备 |

### v1.0 实操补单已含 agentmesh 视角

`scripts/cluster-bus.py` 的 discovery 协议可**直接借鉴** agentmesh-labs/agentmesh
的 TCP service registration 设计（无需重发明）。`scripts/ccc-dispatch.py` 的
capability matching 可参考 dmontgomery40/agent-mesh 的 role dispatcher 思路。

**借鉴评估表**（详见对话历史）：

| 雷 | 借鉴度 | 策略 |
|---|------|------|
| git sync 冲突 | 中 | 借鉴思路（chunk_id 全链路带）+ 新 FSM + abnormal-reports 缓冲 |
| Agent 互调成环 | 空 | **借鉴思路 = 直接禁**（clawmed 没这层是优势） |
| 算力路由伪优化 | 高 | 借鉴 capabilities + 当前负载模型，加红线防失效 |
| 模型 + 算力耦合 | 低 | 借鉴 ai-loop-router upstreams.json tier 模型 |
| PoC 不切实际 | 高 | **借鉴失败教训**：降级到 1 任务而非 4 任务 |
| cluster bus 安全 | 高 | **反借鉴**：clawmed 没 auth → 我们必须 mTLS |

---

### v1.0 必做的 5 件事（借鉴 clawmed 思路后修订版）

#### 1. 项目同步（Cluster Sync）
- **现状**：qb / qx-observer / xianyu 在不同设备，独立 git
- **v1.0 需求**：CCC 任务跑在设备 A，但 git 改动要 sync 到设备 B
- **机制**（**借鉴 clawmed chunk_id 思路**）：
  - 每个 chunk 分配唯一 `chunk_id`（uuid），commit message 含 `ccc-task-id=<id>`
  - commit 幂等性 = re-run 命中 fast-forward，不产生重复 commit（**新红线 15**）
  - sync 冲突 → 不解决，进 `.ccc/abnormal-reports/` 缓冲，等 verifier 在 sink 端检测
  - FSM 状态：`pending → assigned → running → success/failed/retry`
- **风险**：跨文件 + 多设备并发改 = 概率仍高，需要 LLM 协助解决 20% 边缘 case

#### 2. 算力平衡（Compute Balance）
- **现状**：设备调度全靠"我现在在哪个 IDE"
- **v1.0 需求**：CCC dispatcher 知道每台设备的当前负载 + 能力
- **机制**（**核心借鉴 clawmed capabilities**）：
  - 每个 ccc-node 注册到 cluster bus（POST `/api/node/register`）
  - 注册 payload：`{node_id, ip, port, capabilities: [...], fingerprints}`
  - 健康上报（POST `/api/node/heartbeat`）：每 **30 秒** 一次
  - 超时阈值（**借鉴 clawmed 90 秒**）：heartbeat 超时 → node 标 dead
- **能力标签格式**（**借鉴 clawmed 但扩成 3 档**）：
  - **L1**（基础）：`shell`, `python`, `git`
  - **L2**（AI）：`claude-p`, `glm-5`, `deepseek-v4-flash`
  - **L3**（专用）：`browser`, `gpu`, `cron`, `ssh-remote`
- **决策逻辑**：
  ```
  1. filter_nodes(required_capability) → 候选列表
  2. score_nodes(load, last_heartbeat) → 排序
  3. pick_top(min_capacity=1)
  4. 如果所有 node 超载 → queue 等待（escalation 阈值 = 5 min）
  ```

#### 3. 中转站路由（Model Router）
- **现状**：ai-loop-router 已在 `127.0.0.1:4000`，按 prompt hash 路由
- **v1.0 需求**：任务类型 → 模型映射可配置
- **借鉴 ai-loop-router `upstreams.json` 的 `tier` 模型**：

  | tier | upstream_model | CCC 用途 |
  |------|---------------|---------|
  | `flash` | minimax/M3 / deepseek-v4-flash | CCC Planner / 小任务 |
  | `sonnet` | sonnet 4.5 | CCC Executor（默认） |
  | `opus` | opus 4.8 | CCC Verifier / 大型重构 |
  | `max` | opus max reasoning | 失败 retry |

- **机制**：
  - **node 决策 + model 决策解耦**（**clawmed 没这层，**新设计**）**
  - dispatcher 选 node（基于 capabilities）→ 同时告诉 node "调 claude -p 时设 ANTHROPIC_BASE_URL + metadata task-type=ccc-executor"
  - 中转站读 metadata 路由
- **关键创新**：dispatcher 输出 `[node_id, model_tier, est_cost_seconds]` 三元组供人 review

#### 4. Agent 互调（**v1.0 默认禁止** —— 反 clawmed 但符合它的设计哲学）
- **clawmed 真相**：clawmed-ai 是 **scheduler → worker 单向**，**没有 agent → agent 互调**。
  → 这就是 v1.0 应该遵循的设计：单层调度，无环。
- **v1.0 决策**：**禁止 Agent 互调**（红线 17 替代品 → 新红线 18）
  - 主体（user / IDE）→ CCC dispatcher → worker（CCC executor）
  - worker 之间**不走 dispatcher**，**只走文件总线**（`.ccc/reports/` = 共享结果）
  - 跨 agent 通信 = 文件 + git push，不在 dispatcher 内递归
- **v1.x 才允许的扩展**：trace TTL 机制（v1.0 不需要）

#### 5. 容错与降级（Fault Tolerance）
- **设备离线**：cluster bus 标记 node = dead，自动 shrink 任务到 alive node（**借鉴 clawmed 90s 超时**）
- **网络分割**：本地 buffer 任务，rejoin 后 reconcile
- **中转站掉线**：fallback 到直连 `api.anthropic.com`，触发红线 escalate
- **commit 失败**：stash 改动 → 进 `abnormal-reports/` → 等 sync 通 → 重试
- **能力标签被注释风险**（**借鉴教训**）：加测试 case，dispatcher 启动时自检 "capabilities match enabled?"

### 验收（v1.0 release 必跑） —— **降级版**

> **降级依据**：clawmed-ai task_queue.json 4 个任务中 3 个失败直接归因"想跑全套"。v1.0 PoC 必须降级。

1. **最小 PoC**（**必跑，failure = v1.0 不发版**）：
   - 1 个 qb 任务，分配到 feiniu 跑 executor
   - feiniu 完成后 commit + push 回 M1
   - M1 跑 verifier
   - 全程 0 用户介入

2. **健康心跳 PoC**（**必跑**）：
   - 启动 2 node + cluster-bus
   - 杀掉其中一个
   - 验证 90 秒内 dispatcher 不再派单到 dead node

3. **能力标签 PoC**（**必跑**）：
   - dispatcher 自检 capabilities 启用（**红 18 配套**）
   - 故意改 capability 需求，验证节点选择变化

4. **不验收**（v1.x 才做）：
   - 多任务并发
   - 故障自动降级完整流程
   - 知识飞轮跨设备同步

### 工程化补单（v1.0 实操清单 ~ 750 行）

| 文件 | 用途 | 行数 | 借鉴 |
|------|------|------|------|
| `scripts/cluster-bus.py` | 集群总线 + 健康心跳 + node 注册 | ~150 | clawmed heartbeat 协议 |
| `scripts/ccc-dispatch.py` | 能力标签匹配 + 算力路由 + model tier | ~150 | clawmed select_best_worker（**已修**：能力匹配**默认开启** + 加自检） |
| `scripts/ccc-sync.sh` | 跨设备 git 同步 + chunk_id 幂等 | ~80 | 新设计 |
| `references/cluster-protocol.md` | 集群协议规范（必含 auth） | ~100 | clawmed 思路 + **反借鉴**（强制 mTLS） |
| `examples/cluster/m1.yaml` | node 配置示例 | ~30 | — |
| `examples/cluster/feiniu.yaml` | node 配置示例 | ~30 | — |
| `tools/cluster-doctor.sh` | 一键诊断集群状态 | ~60 | — |
| `tests/cluster/test-capability-required.py` | 能力标签默认开启测试 | ~50 | 借鉴 clawmed v3.1 失败教训 |

> 注：v1.0 不再需要 `agent-mesh.md` 和 `mavis/session-bus.xml`（agent 互调已禁）

### 红线 15-18（v1.0 配套）— **新增**

#### 红线 15：项目 sync 必须有 commit 幂等性
- **Why**：跨设备 sync 后失败重试，不能产生重复 commit
- **机制**：commit message 含 `ccc-task-id=<id>` + retry-count；re-run 命中则 fast-forward

#### 红线 16：算力路由必须显式感知设备状态
- **Why**：node offline 时继续派单 → 任务挂死
- **机制**：派单前 `cluster-bus ping <node> --timeout=3s`，失败则 skip

#### 红线 17：**取消**（v1.0 改红线 18：禁 agent 互调）
- 旧红线 17（trace TTL）已废除，因为 v1.0 默认禁止互调

#### 红线 18（v0.5 起新增）：能力标签匹配必须**默认开启**（防 clawmed v3.1 失败重演）
- **Why**：clawmed-ai v3.1 失败教训——能力匹配代码被注释掉，结果 task_type 硬编码逻辑全留着
- **机制**：
  1. dispatcher 启动时自检 `capabilities_match_enabled == True`，否则 fail-fast
  2. 加测试用例 `tests/cluster/test-capability-required.py`：模拟"试图禁用能力匹配" 必须 panic
  3. 任何 PR 关掉能力匹配 = Critical violation

### v1.0 完结判定（**借鉴 PoC 失败教训，降级**）

> **降级版 4 条**（比 v1.0 初版"4 项目"降级为"1 项目 + 完整流程"）：

- **必达**：1 个真实项目（qb）成功跑过跨设备任务（写 plan → 派单到 feiniu → commit + push → M1 跑 verifier）
- **必达**：集群 bus 跑通健康心跳 + 派单 + 同步（最小 2 节点 PoC）
- **必达**：能力标签 PoC 通过（红 18 自检不挂）
- **必达**：用户不再需要手动选择设备："按 ccc full 跑"就够了，**CCC 自动选**

> "4 个项目跑通"是 v1.x 验证，不是 v1.0 release gate。

### 反借鉴清单（**clawmed 不做的事 = CCC 必须做**）

| clawmed 没有 | CCC v1.0 必须有 |
|--------------|-----------------|
| cluster bus auth | mTLS 或 static token + node fingerprint |
| retry 决策字段 | `chunk.status` 显式 `retry: false \| once \| always` |
| failure_reason 中文 | 保留 `failure_reason: "..."` 中文可读 |
| capabilities 默认开启 | 红线 18 强制 + 启动自检 |
| PoC 范围控制 | 1 项目 / 2 节点，**不**跑全套 |

---

## v1.x — 扩展阶段（v1.0 完成后的演进）

### 跨工具调用

- CCC skill 调度 Cursor / Codex / OpenCode 当 sub-agent
- 一个 IDE 内**聚合所有 LLM 工具**

### 模型路由成熟

- 中转站按任务类型选 model（v1.0 已经做了基础，v1.x 完善）

### Agent 军团模式

- CCC = 连接器（v1.0 已经做了基础）
- 每个项目部署一个 ccc-style agent，agent 之间相互调度
- agent = prompt + skill 的最小可复用单元

**v1.x 起源**：v1.0 设计借鉴来源全部在
`/Users/apple/program/projects/clawmed-ai/`（Universal Worker v3.1 +
T1.2 worker_analysis.md）。v1.x 扩展时优先复用 v1.0 已落地的 capability-tier
模型，复用率估计 70%。

---

## 路线收敛条件

CCC **不再扩张**（不写 framework 代码库）的条件：

1. v1.0 闭环跑通
2. 至少 3 个真实项目跑过 CCC（验证可移植性）
3. 知识飞轮 1 个完整循环跑过（lessons 自动增量 1 条）
4. 用户不再需要知道 SKILL 内容，**只说"按 ccc full 跑"** 就够了

满足这 4 条，CCC 算完成它的历史使命。

---

## 相关文件

- `SKILL.md` — 注入 prompt
- `CLAUDE.md` — 框架总纲
- `references/red-lines.md` — 11+2 红线
- `docs/lessons.md` — 教训沉淀
- `docs/architecture.md` — 框架说明书
- `CHANGELOG.md` — 版本历史
