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

---

## v1.0.0 — 最小化的 Loop Engineering

### 目标

把 CCC + IDE 定时 + 知识飞轮**实际拼成**：
> 任务投进去 → 自动拆解 → 自动调度 → 自动执行 → 自动验收 → 自动沉淀

### 验收

跑 1 个跨 3 阶段的项目级任务：
- 自动启动（cron / IDE 定时）
- 自动跑 3 阶段
- 自动沉淀 1 条 lessons
- 全程**零用户介入**

### 这是 Loop Engineering 的最小闭环

不靠 Mavis daemon、不靠 mavis session，靠：
1. CCC skill
2. IDE 定时
3. Claude executor
4. 知识飞轮

### 如果 v1.0 完成

> CCC 是 Loop Engineering 的最小可行实现。

---

## v1.x — 扩展阶段

### 跨设备集群

- ssh / mavis session 让 CCC 调度 feiniu / M1 / qb 集群
- agent 军团在多设备协调

### 跨工具调用

- CCC skill 调度 Cursor / Codex / OpenCode 当 sub-agent
- 一个 IDE 内**聚合所有 LLM 工具**

### 模型路由成熟

- 中转站 (`127.0.0.1:4000`) 按任务类型选 model
- Task type → model 映射可配置
- 异常任务降级（opus 不行 → fallback sonnet）

### Agent 军团模式

- CCC = 连接器
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
