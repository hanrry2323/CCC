# CCC 发展路线图

> v0.5 是关键转折：CCC 从「framework 代码库」转型为「SKILL 资产」。
> 本文件记录当前 + 未来的路线，分阶段清晰。

---

## 当前版本：v0.5.0（2026-07-06）

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

### v1.0 必做的 5 件事

#### 1. 项目同步（Cluster Sync）
- **现状**：qb / qx-observer / xianyu 在不同设备，独立 git
- **v1.0 需求**：CCC 任务跑在设备 A，但 git 改动要 sync 到设备 B
- **机制**：CCC executor 完成后触发 `git push`（红线扩展——v1.0 允许 commit-push 但仍不允许 Planner commit），其他设备 `git pull` + reconcile
- **风险**：sync 冲突 = git merge 失败，需要 LLM 协助解决
- **新红线 15**：项目 sync 必须有 commit 幂等性（re-runnable）

#### 2. 算力平衡（Compute Balance）
- **现状**：设备调度全靠"我现在在哪个 IDE"
- **v1.0 需求**：CCC dispatcher 知道每台设备的当前负载（CPU / RAM / running claude count）
- **机制**：每个 ccc-node 注册到 cluster bus（mDNS / broadcast / 静态 IP），健康上报每 30s
- **决策逻辑**：
  ```
  - 如果 M1 满载 → 派单到 feiniu
  - 如果 feiniu 满载 → 派单到空闲 node
  - 如果所有 node 满载 → queue 等待（escalation 阈值 = 5 min）
  - 模型决策 + 算力决策 **解耦**：算力选 node，模型经中转站路由
  ```

#### 3. 中转站路由（Model Router）
- **现状**：ai-loop-router 已在 `127.0.0.1:4000`，按 prompt hash 路由
- **v1.0 需求**：任务类型 → 模型映射可配置
  | 任务 | 模型 | Why |
  |------|------|-----|
  | CCC Planner | sonnet | 规划够用，省钱 |
  | CCC Executor | opus | 执行要稳，质量优先 |
  | CCC Verifier | opus | 验收要严，质量优先 |
  | 小任务（agent 自己处理） | sonnet | 便宜够用 |
  | 失败 retry | max | 最强推理救场 |
- **机制**：CCC 调 `claude -p` 时设 `ANTHROPIC_BASE_URL` + 加 `--metadata task-type=ccc-executor`，中转站读 metadata 路由

#### 4. Agent 军团模式（Agent Mesh）
- **现状**：CCC 是单 agent 三角色
- **v1.0 需求**：CCC = 连接器，连接多个 "ccc-style agent"
  ```
  qb 的 ccc-agent  ←→ CCC cluster bus ←→ qx-observer 的 ccc-agent
                          ↓
                   qx-observer 跑 qb 任务
                          ↓
                   qb 代码改动 → push → qb 自动回归
  ```
- **机制**：每个项目部署 1 个 `<project>-ccc-agent` (prompt + ccc SKILL)，通过 cluster bus 调度
- **风险**：agent 互相调用成环 → 加 trace TTL + 黑名单

#### 5. 容错与降级（Fault Tolerance）
- **设备离线**：cluster bus 标记 node = dead，自动 shrink 任务到 alive node
- **网络分割**：mavis session 缓冲任务，rejoin 后 reconcile
- **中转站掉线**：fallback 到直连 `api.anthropic.com`，触发红线 9 escalate
- **commit 失败**：stash 改动 → 等 sync 通 → 重试

### 验收（v1.0 release 必跑）

1. **单任务跨设备验证**：
   - qb 任务在 M1 写 plan，提交到 cluster
   - cluster 自动派单到 feiniu 跑 executor
   - feiniu 完成后 commit + push 回 M1
   - M1 跑 verifier
   - 全程 0 用户介入

2. **多任务并发验证**：
   - 3 个不同项目任务同时启动
   - cluster 自动分配（不全堆 M1）
   - 健康监控不漏报

3. **故障降级验证**：
   - 杀掉 feiniu 的 ccc-executor
   - 看任务是否 5 分钟内漂移到 M1
   - 报警机制工作

4. **知识飞轮闭环**：
   - 跨设备的 lessons.md 自动同步（gitea / git 私有 repo）
   - 红线增量在所有设备生效

### 工程化补单（v1.0 实操清单 ~ 800 行）

| 文件 | 用途 | 行数 |
|------|------|------|
| `scripts/cluster-bus.py` | 集群总线 + 健康心跳 | ~150 |
| `scripts/ccc-dispatch.py` | 任务派单 + 算力路由 | ~120 |
| `scripts/ccc-sync.sh` | 跨设备 git 同步 | ~50 |
| `references/cluster-protocol.md` | 集群协议规范 | ~100 |
| `references/agent-mesh.md` | agent 互调协议 | ~80 |
| `examples/cluster/<host>.yaml` | node 配置示例 | ~30 |
| `examples/mavis/session-bus.xml` | mavis session 总线配置 | ~40 |
| `tools/cluster-doctor.sh` | 一键诊断集群状态 | ~60 |
| 额外：knowledge-flywheel 集成（推送 lessons 通过 cluster bus） | ~50 |
| 额外：trace / 观察 | ~80 |

### 红线 15-17（v1.0 配套）— **新增**

#### 红线 15：项目 sync 必须有 commit 幂等性
- **Why**：跨设备 sync 后失败重试，不能产生重复 commit
- **机制**：commit message 含 cluster-task-id + retry-count；re-run 命中则 fast-forward

#### 红线 16：算力路由必须显式感知设备状态
- **Why**：node offline 时继续派单 → 任务挂死
- **机制**：派单前 `cluster-bus ping <node> --timeout=3s`，失败则 skip

#### 红线 17：agent 互调必须有 trace TTL
- **Why**：防 agent 调用成环 = 无限递归 = 预算烧光
- **机制**：每次 agent 调度带 TTL = 5 跳，超出 → escalate

### v1.0 完结判定

- 4 个真实项目跑过跨设备任务（qb + qx-observer + xianyu + CCC 自身）
- 集群 bus 跑通健康心跳 + 派单 + 同步
- 知识飞轮闭环跑过一次（lessons 增量经 cluster 同步所有 node）
- 用户不再需要手动选择设备："按 ccc full 跑"就够了，**CCC 自动选**

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
