# CCC GLOSSARY — 30+ 核心术语

> CCC 全部术语的中文一句话定义。便于新 contributor / agent 快速对照术语表。
> 来源：SKILL.md / references/red-lines.md / docs/lessons.md / docs/roadmap.md 沉淀。

---

## A. 三角色

### Planner — 计划者
负责写 `.ccc/plans/<task>.plan.md` + `.ccc/phases/<task>.phases.json`。
**红线 6**：Planner 不写 verdict，Verifier 不写 plan。

### Executor — 执行者
按 plan 改 working tree + 写 `.ccc/reports/<task>.report.md`。
**触发方式**：`claude -p "<prompt>"` 独立 session 跑（**不是 IDE 内 agent**）。

### Verifier — 验证者
独立 session 跑 ≥3 adversarial probes + 写 `.ccc/verdicts/<task>.verdict.md`（**≥50 行红线 11**）。

---

## B. 4 文件契约

### Plan — 计划文件
`.ccc/plans/<task>.plan.md`，含 范围 / 改动 N / Commit 计划 / 全局验收清单。

### Phases — 阶段状态
`.ccc/phases/<task>.phases.json` JSON Lines，每行一个 phase 对象（`phase/status/subtasks/commit/notes`）。
**红线 5**：必写全，单 phase 至少 1 行。

### Reports — 执行报告
`.ccc/reports/<task>.report.md`，Executor 输出，含真实 stdout + verification。

### Verdicts — 验收结论
`.ccc/verdicts/<task>.verdict.md`（≥50 行），Verifier 输出，含 ≥3 probes + VERDICT 三选一。

---

## C. 5 核心机制

### Dispatcher — 派单器
`scripts/ccc-dispatch.py`，读 plan → 输出三元组（node_id, model_tier, est_cost_seconds），PoC 模式等人工 stdin 'yes'。

### Cluster Bus — 集群总线
`scripts/cluster-bus.py`，FastAPI，5 endpoints，30s 心跳 / 90s TTL，60s JSON checkpoint。

### Heartbeat — 心跳协议
30s POST `/api/node/heartbeat`，90s 超时判定 node dead。来源 clawmed-ai T1.2。

### Capability — 能力标签
L1（基础）/ L2（LLM）/ L3（专用）三档。dispatcher 按 capability overlap + load score 选节点。

### Cluster Doctor — 诊断工具
`tools/cluster-doctor.sh`，5 段输出（bus/nodes/heartbeat/matrix/verdict），4 exit codes。

---

## D. 4 关键路径

### CCC_HOME
`~/program/CCC/`，CCC 主工程根，含 SKILL.md / scripts/ / references/。

### `<workspace>`
agent 当前工作的项目根。`.ccc/` 在 `<workspace>` 下。

### `.ccc/`
每项目一个目录，含 plans / phases / reports / verdicts / abnormal-reports / dispatches。

### `/tmp/abc.bundle / .ccc-cluster-bus.json`
跨设备 git sync 用 `git bundle` + base64 stream，bus 60s checkpoint。

---

## E. 核心 red lines (12 条)

### 红线 1 — 不动系统文件
`~/.env` `/etc/hosts` 等不动。

### 红线 2 — 验收必须可执行
plan 中验收自然语言 + 命令示例。

### 红线 3 — 不超出 plan 文件范围
白名单外不动。

### 红线 4 — 单 phase 单 commit
攒 commit 不允许。

### 红线 5 — phases.json 必写全
JSON Lines，**不嵌套**，每 phase 至少 1 行。

### 红线 6 — Planner / Verifier 不互串
Planner 不 verdict，Verifier 不 plan。

### 红线 7 — 启动顺序固定
先 CCC CLAUDE.md → 后项目 profile.md。

### 红线 8 — 每步必 commit
不攒 commit，working tree 改动必须本 phase 内 commit。

### 红线 9 — Executor 卡死止损
watchdog 4 检查 + 4 exit codes。

### 红线 10 — 禁止跨会话隐式记忆
state.md 接力 + 显式 grep。

### 红线 11 — Verifier 必须写 verdict 文件（≥50 行）
**口头 PASS ≠ PASS** Lesson 28。

### 红线 12 — 禁止 agent 自主启用 CCC
用户显式触发。

### 红线 13 — 禁止无 watchdog 启 IDE 定时任务
v0.6 scheduler 必须 watchdog-passed。

### 红线 14 — 飞轮候选必须人工 review
flywheel-scan.py 只写 candidate 到 abnormal-reports/。

### 红线 15 — 跨设备 commit 幂等性
commit message 含 `ccc-task-id=<uuid>`。

### 红线 16 — 算力路由显式感知设备状态
ping before dispatch。

### 红线 17 — (废除 — agent 互调已禁)
trace TTL — 不再用。

### 红线 18 — 能力标签默认开启
clwmmed v3.1 失败教训。

### 红线 19 — 跨设备独立 verifier
Mavis / Claude Code Trae / Mac2017 verifier session。

### 红线 20 — bash v3 portability
avoid `bash -c '\$VAR'` 单引号嵌套。

---

## F. 路线图阶段

### v0.5 — Connect–Claude Code SKILL 重构
2026-07-06，含义 = **C**onnect–**C**laude **C**ode。

### v0.6 — IDE 定时任务
ccc-scheduler.sh + ccc-task-done.sh。

### v0.7 — 知识飞轮
flywheel-scan.py + red line 14 强制人工 gate。

### v1.0 — 跨设备集群
cluster-bus + ccc-dispatch + cluster-protocol + tests + yaml + doctor。

### v1.1 — Engineering Foundation
24 task plan（本计划）。

---

## G. 借鉴来源术语

### clawmed-ai
`/Users/apple/program/projects/clawmed-ai/`，提供 heartbeat 协议 + capability tag + 失败教训。

### agentmesh
GitHub 6 个项目，2025-11 同期爆发。共识：TCP service registration + capability routing。

### Anthropic 2026 mesh paper
Motwani et al, "Communications-Effective Multi-Agent Coordination for Multi-Phase Tasks"。

### agentmesh-labs / mesha-framework / rusty-robot / Abinesh / FMs-sys
agentmesh 命名 GitHub 项目群。

### ai-loop-router
`~/program/ai-loop-router/`，`:4000` 中转站，按 model tier 选上游。

---

## H. 借鉴反模式（anti-pattern）

### 6 个 agentmesh 项目无 auth
6/6 项目**没做认证**，CCC 反借鉴必须 mTLS（红线 19 实装）。

### clwmmed v3.1 capability 注释掉
能力匹配代码被注释掉没启用，CCC 强制默认开启（红线 18）。

### 凭印象复述上一会话
会话级记忆不可靠。state.md + 显式 grep（红线 10）。

### 口头 PASS verifier
Trae 实测自证，CCC 强制 verifier 写文件（红线 11）。

---

## I. 关键版本

### v0.1.0 — Internal Prototype
2026-06-30。

### v0.3.0 — 三角色 + 4 文件契约
2026-07-01。

### v0.5.0 — Connect–Claude Code SKILL 重构
2026-07-06。

### v1.0.0 — Automation Open
2026-07-06。

---

## 相关文件

- [SKILL.md](../SKILL.md) — 注入 prompt
- [references/red-lines.md](../references/red-lines.md) — 13 红线细则
- [docs/lessons.md](../docs/lessons.md) — 30 教训
- [docs/roadmap.md](../docs/roadmap.md) — 发展路线
- [docs/USAGE.md](USAGE.md) — 3 类用户指南
- [docs/CONTRIBUTING.md](CONTRIBUTING.md) — dev workflow
