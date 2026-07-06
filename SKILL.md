# CCC — Connect–Claude Code (v1.1)

> **One SKILL, every IDE, every model.** A skill that turns any coding agent
> into a Planner → Executor → Verifier pipeline. Loads cleanly into Trae,
> Cursor, Zed, VS Code, OpenCode, or any tool that supports system-prompt
> files.
>
> **含义**：**C**onnect–**C**laude **C**ode。把 Claude Code 的能力连接到
> 任何 IDE 工具，让 agent 自己调度自己。

---

## 触发（用户显式调用）

下列任意一句命中即触发本 skill：

- "按 CCC 流程跑 X 任务"
- "用 plan-execute-verify 模式"
- "ccc 跑一下 X"
- "调度一个多阶段任务"
- "按 ccc full 跑"

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
3. **红线清单** — 11 条硬约束（见 `references/red-lines.md`）+ Lesson 27/28
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

## 配套扩展（v0.5+ 路线）

- **IDE 定时任务**：cron / launchd 自动唤起 CCC 跑下一阶段
- **知识飞轮**：`quality_flywheel.py` 对接报告，沉淀 lessons 自动丰富红线
- **跨设备**：CCC cluster bus / ssh 调用 qb / feiniu / M1 集群（v1.0 路线）
- **跨工具**：SKILL 不绑 IDE，可在 Trae / Cursor / Zed 间移植
- **模型路由**：通过 `ANTHROPIC_BASE_URL=http://127.0.0.1:4000` 选模型
