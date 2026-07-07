---
name: ccc-protocol
description: "CCC — Connect–Claude Code. A Planner → Executor → Verifier pipeline for multi-phase coding tasks. Trigger when user says: '按 CCC 流程跑 X', '用 plan-execute-verify 模式', 'ccc 跑一下 X', '调度一个多阶段任务', '按 ccc full 跑'"
---

# CCC — Connect–Claude Code (v1.6)

> **One SKILL, every IDE, every model.** A skill that turns any coding agent
> into a 6-role multi-agent pipeline. Loads cleanly into Trae,
> Cursor, Zed, VS Code, OpenCode, or any tool that supports system-prompt
> files.
>
> **含义**：**C**onnect–**C**laude **C**ode。把 Claude Code 的能力连接到
> 任何 IDE 工具，让 agent 自己调度自己。
>
> **v0.16 起 范式转变**：CCC 从 3 角色（Plan/Exec/Verify）扩到 **6 角色
> 定时开发系统**（product / dev / reviewer / tester / ops / kb），用任务看板
> 流转。**所有 cloud agent 启动第一件事** = 读 `docs/STRATEGY-MAP.md`。

---

## 启动必读（红线 7 + 战略地图）

任何 agent 启动时按以下顺序读：

1. **`docs/STRATEGY-MAP.md`** — 战略地图（v0.16 6 角色 + 看板 + 全部资产）
2. **`references/red-lines.md`** — 13+2+X3+X4/X5/X6 红线（v0.17 加 3 条）
3. **`docs/lessons.md`** — 36 条教训（避免重复踩坑）
4. **`.ccc/state.md`**（项目侧）— 接力索引

**没读 STRATEGY-MAP.md = 没读 CCC**（v0.17 强制）。

## 触发（用户显式调用）

下列任意一句命中即触发本 skill：

- "按 CCC 流程跑 X 任务"
- "用 plan-execute-verify 模式"
- "ccc 跑一下 X"
- "调度一个多阶段任务"
- "按 ccc full 跑"
- **"按 CCC 跑 X"**（v0.15b 入口，6 角色会自动接）

**默认不触发**。agent 不自主判断是否启用 CCC——避免意识漂移
（参见 `references/red-lines.md` 红线 12：禁止 agent 自主启用 CCC）。

### 路由决策（用户拍板，agent 不替决）

| 任务规模 | 处理方式 |
|---------|---------|
| 小（单文件改 1-5 行、查信息、调试 1 个 bug） | agent 直接处理，**不走 CCC** |
| 中（多文件 / 跨模块 / 要 plan + phases） | CCC skill 启用，单或双 phase |
| 大（多阶段 / 跨会话 / 要独立 Verifier） | CCC skill 强制，完整 4 文件契约 |

---

## 注入内容

本 SKILL 一次性注入以下内容到当前 agent 的 prompt：

1. **三角色纪律** — Planner / Executor / Verifier 严格分离
2. **4 文件契约** — plans / phases / reports / verdicts 路径与字段
3. **红线清单** — 红线清单 — 见 `references/red-lines.md`（v0.5 起累积共 18 条，含历史编号映射）+ Lesson 27/28
4. **完成定义** — 不写假报告、不口头 PASS
5. **退出标准** — report.md + verdict.md 双产出，引用关系正确

注入消息在任务结束后被消化，**不影响下次对话**。

---

## 三角色

```
Planner → Executor → Verifier
   ↑          │          │
   └────── 修订循环 ─────┘
       (CONDITIONAL_PASS)
```

- **Planner**（你 + agent 对话）：出 `.ccc/plans/<task>.plan.md` + `phases/<task>.phases.json`
- **Executor**（agent 自主执行）：按 plan 改 working tree + 写 `reports/<task>.report.md`
- **Verifier**（**独立 session** 调起）：写 `verdicts/<task>.verdict.md`，≥3 adversarial probes
- 角色一旦开始，**边界不可跨越**：Planner 不写 verdict，Verifier 不写 plan

---

## 4 文件契约（绝对路径 = `<workspace>/.ccc/`）

```
<workspace>/.ccc/
├── profile.md                              # 项目档案（首次接入生成）
├── plans/<task>.plan.md                     # Planner 产出
├── phases/<task>.phases.json                # Planner 产出（JSONL）
├── reports/<task>.report.md                 # Executor 产出，含 > VERDICT: 段
├── verdicts/<task>.verdict.md               # Verifier 产出（红线 11 强制）
└── abnormal-reports/                        # 异常 / 红线违反记录
```

> **path of truth**: `<workspace>` = agent 当前对话所在的项目根目录。
> agent 自动读 `<workspace>/.ccc/profile.md` 拿到项目背景。

---

## 完成定义（agent 必须满足才能退出）

1. **Planner**: plan.md + phases.json 双写完，触发词是用户显式说出
2. **Executor**: report.md 已写 + `> VERDICT:` 段已加引用（占位路径） + working tree 仅含 plan 范围文件
3. **Verifier**: verdict.md 真文件存在（红线 11 强证据） + ≥3 adversarial probes + VERDICT 三选一
4. **退出前自检**: `git status --short` 仅新增计划文件

---

## Planner 启动顺序（红线 7 + 10 强制 · 机器化门控）

按以下顺序启动,缺一即视为启动失败:

```
0. 读 .ccc/state.md    ← 红线 10: 唯一允许的"上下文输入"
1. 读 .ccc/profile.md  ← 项目背景 + 红线清单
2. 读 templates/plan.plan.md（plan 格式规范）
3. 跑 bash scripts/ccc-precheck.sh  ← 5 项前置门控
4. 写 .ccc/plans/<task>.plan.md + .ccc/phases/<task>.phases.json
5. 写 executor-prompt 文件,准备启动 Executor
6. 启动 Executor (claude -p, stdin 喂 prompt, Lesson 27)
```

**门控脚本** (v1.2.0 新增):
- `scripts/ccc-precheck.sh` — 5 项前置门控: 读 state.md / 读 profile.md / 范围白名单 / plan 路径 / watchdog
- `scripts/ccc-finish.sh` — 5 项后置门控: report 已写 / ≥3 probes / VERDICT 引用 / 范围检查 / 单 phase 单 commit

**失败兜底**: 门控脚本 exit 非零 → 必须修复后重跑,**禁止跳过**。

---

## 强制 watchdog（红线 9 配套 · v1.2.0 新增）

任何 Executor 启动前**必须**先跑:

```bash
bash scripts/executor-watchdog.sh || { echo "[caller] watchdog failed, exit"; exit 1; }
```

退出码:
- `0` = 健康可启动
- `1` = warning,让 caller 决定
- `2` = 严重,放弃
- `3` = 已自动清理(--force-kill 模式)

**禁越界**: 跳过 watchdog 启动 Executor = 红线 9 触犯。

---

## 闭环:`ccc commit` 替代手动 git commit（v1.2.0 新增）

Planner **不直接 `git commit`**,必须走:

```bash
# Executor 退出后,Planner 自动跑:
ccc commit <workspace> <task>           # 处理所有待 commit phase
ccc commit <workspace> <task> --phase N # 仅指定 phase
```

**理由**:
- 自动化 commit hash 回写 phases.json
- 机器化检查"单 phase 单 commit" + 范围白名单 + ccc-task-id 前缀
- 幂等性: 已填 hash 的 phase 自动 skip (红线 15 配套)

**禁越界**: Planner 手动 `git add` + `git commit` = 红线 4/8 触犯,应改用 `ccc commit`。

---

## 红线（详见 `references/red-lines.md`）

| # | 红线 | 一句话 |
|---|------|--------|
| 1 | 不动系统文件 | /etc、~/.env、密钥不改 |
| 2 | 验收必须可执行 | 自然语言 + 可选命令 |
| 3 | 不超出 plan 范围 | 白名单外不动 |
| 4 | 单 phase 单 commit | 兜底 commit 由脚本做 |
| 5 | phases.json 必写全 | JSONL，不嵌套 |
| 6 | Planner/Verifier 不互串 | 边界硬性 |
| 7 | 启动顺序固定 | 读 profile.md 第一 |
| 8 | 每步必 commit | exec-commit 兜底 |
| 9 | Executor 卡死立即止损 | kill + Planner 接管 |
| 10 | 禁止跨会话隐式记忆 | state.md 强制接力 |
| **11** | Verifier 必须写 verdict 文件 | 口头 PASS 不算 PASS（Lesson 28） |
| **12** | 禁止 agent 自主启用 CCC | 用户显式触发 |

**Lesson 27**:`claude -p` 是 print 模式开关，prompt 必须走 stdin。

---

## 不在本 SKILL 范畴（明确不约束）

- 工作目录（agent 自动决定）
- IDE / CLI 选择（用户决定）
- 模型选择（由用户或中转站决定）
- 跨工具调用（plugin 模式扩展）
- 跨设备集群（Phase 4 路线）

---

## 调用样例

用户对话：

> "按 ccc full 跑 qb 项目的 X 任务"

Agent（加载 SKILL 后）的行为：

1. 读 `<workspace>/.ccc/profile.md`（项目背景）
2. 提议 plan 草稿，与用户多轮 review
3. 写 `.ccc/plans/qb-x.plan.md` + `.ccc/phases/qb-x.phases.json`
4. 启动 Executor（agent 自主或调度 `claude -p`）
5. Executor 完成后写 `.ccc/reports/qb-x.report.md`
6. 启动 Verifier（独立 session）写 `.ccc/verdicts/qb-x.verdict.md`
7. 三角色对账，全部 deliver 后退出

---

## CCC 与现有资产的关系

| 资产 | 在 CCC 中的角色 |
|------|----------------|
| `~/program/CCC/templates/` | 4 文件契约的模板 |
| `~/program/CCC/references/` | 红线 / 适配器 / lessons 引用 |
| `~/program/CCC/scripts/` | 机械步骤（commit / watchdog） |
| **本 SKILL.md** | **唯一注入的 prompt 资产** |

本 SKILL 是 prompt 资产，不是 framework 代码库。**所有工程纪律沉淀在 `references/red-lines.md` 和 `docs/lessons.md`**，本文件只是入口。

---

## 配套扩展（v0.8）

> v0.8 重构：CCC 执行端从 claude CLI 改为 **OpenCode CLI**（CLI 模式，不用 serve/HTTP）。
> 详细执行器契约见 `references/adapters/runtime-opencode.md`。
>
> **三件配套**：
> - `scripts/opencode-exec.py` — CLI 执行器（单 phase）
> - `scripts/opencode-pool.py` — 进程池（max 3 并发，红线 X1）
> - `scripts/opencode-watchdog.sh` — 残留扫描（红线 X2/X3）
>
> **通知**：升级链走 `scripts/ccc-notify.sh`（macOS 桌面通知 + 告警存档）。**不接**飞书/邮件。
>
> **钩子**：`scripts/ccc-hook.sh` 提供 pre-exec / post-exec / pre-commit / on-error 4 个点。

- **跨工具**：SKILL 不绑 IDE，可在 Trae / Cursor / Zed / OpenCode 间移植
- **模型路由**：通过 `ANTHROPIC_BASE_URL=http://127.0.0.1:4000` 选模型（opencode exec 时显式 `--model flash`）
