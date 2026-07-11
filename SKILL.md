---
name: ccc-protocol
description: "CCC — Connect–Claude Code. A 7-role automated development pipeline with kanban board. Trigger when user says: '按 CCC 流程跑 X', 'ccc 跑一下 X', '调度一个多阶段任务', '用看板跑 X'"
---

# CCC — Connect–Claude Code (v0.26.0)

> **One SKILL, every IDE, every model.** A skill that turns any coding agent
> into a **7-role automated development system** with kanban board and skill-based
> role definitions. Loads cleanly into Trae, Cursor, Zed, VS Code, OpenCode,
> or any tool that supports system-prompt files.
>
> **含义**：**C**onnect–**C**laude **C**ode。把 Claude Code 的能力连接到
> 任何 IDE 工具，让 agent 通过看板自我调度。
>
> **v0.24.7+**：7 角色 + CCC Engine 串行驱动（v0.20.1 起取消定时轮询）+ Phase 感知调度（v0.24+）+ advisory lock + fallback quarantine（v0.24.5+）+ retry first backoff（v0.24.7+）。每个角色有独立 SKILL.md（`skills/ccc-<role>/SKILL.md`）。

---

## 启动必读（懒加载）

**只读 1 个文件**：`STARTUP-BRIEF.md`（~700 token）。

**其他文件按需 grep**，不预先全读。

```bash
# 1. 必读（启动第 1 件事）
cat STARTUP-BRIEF.md

# 2. 按需查询
grep -A 15 "## 红线 11" references/red-lines.md
grep -A 8  "## Lesson 36" docs/lessons.md
python3 scripts/ccc-board.py index     # 查看板状态
cat skills/README.md                   # 查 7 角色 skill 索引
```

**黄金规则**：
- 不读 4 文件（brief 够了）
- brief 漏了什么 → grep 那个文件

---

## 7 角色系统（唯一范式）

CCC 是 **7 角色看板自动化系统**，不再支持旧 3 角色（Plan/Exec/Verify）流程。

### 角色矩阵（v0.20.1 起 Engine 串行驱动）

| 角色 | Skill 文件 | 看板列 | Engine 触发方式 | 职责 |
|------|-----------|--------|----------------|------|
| **product** | `skills/ccc-product/SKILL.md` | backlog → planned | manual `--promote` 或 product_role() | 拆任务、写 plan、SPEC 门禁、phases.json schema 1.1 |
| **dev** | `skills/ccc-dev/SKILL.md` | planned → in_progress → testing | Engine 主循环立即串行 | 调 opencode 写代码、phase 顺序推进、retry 退避 |
| **reviewer** | `skills/ccc-reviewer/SKILL.md` | testing → verified | Engine 在 dev 完成后立即调 | LLM 语义审查、advisory lock、fallback quarantine（v0.24.5+） |
| **tester** | `skills/ccc-tester/SKILL.md` | testing → verified | Engine 在 dev 完成后立即调 | pytest + plan 逐条验收、phase-aware 测试 |
| **ops** | `skills/ccc-ops/SKILL.md` | 不动 board | Engine 空闲时运行轻度检查 | 健康检查 + 告警 |
| **kb** | `skills/ccc-kb/SKILL.md` | verified → released | Engine 在 reviewer+tester 通过后立即调 | git tag + push + changelog |
| **regress** | `skills/ccc-regress/SKILL.md` | released → backlog(回归bug) | 保留 23:30 定时或嵌 Engine | 每日回测 + 回归建 bug |

**v0.20.1 起取消 7 角色定时轮询**（X6 红线不再适用），所有角色由 CCC Engine 串行触发。
**skill 详细定义** = 对应 `skills/ccc-<role>/SKILL.md`。

### 任务流转（看板）

```
backlog → planned → in_progress → testing → verified → released
                                                              ↓ (regress 23:30)
                                                         backlog(回归bug)
```

### 触发方式（用户显式调用）

- "按 CCC 流程跑 X"
- "ccc 跑一下 X"
- "调度一个多阶段任务"
- "用看板跑 X"

**红线 12**：agent 不自主启用 CCC。用户显式触发。

### 路由决策

| 任务规模 | 处理方式 |
|---------|---------|
| 小（单文件改 1-5 行、查信息） | agent 直接处理，**不走 CCC** |
| 中（多文件 / 跨模块） | CCC 启用，指定 1-2 角色 |
| 大（多阶段 / 需完整看板流转） | CCC 启用，7 角色全链跑 |

---

## 看板文件 & 角色入口

### 4 文件契约

```
<workspace>/.ccc/
├── profile.md                   # 项目档案（首次接入生成）
├── plans/<task>.plan.md         # product 产出
├── phases/<task>.phases.json    # product 产出（JSONL, schema_version="1.1"）
├── reports/<task>.report.md     # dev 产出（含 AGENTS.md 建议段）
├── reviews/<task>.review.md     # reviewer 产出（v0.24.5+）
├── verdicts/<task>.verdict.md   # reviewer/tester 产出（≥3 probes）
├── review-locks/<task>.lock     # reviewer per-task advisory lock（v0.24.5+, O_EXCL 互斥）
└── board/                       # 看板文件（由 ccc-board.py 维护）
    ├── backlog/                 # product 读
    ├── planned/                 # dev 读
    ├── in_progress/             # dev 读
    ├── testing/                 # reviewer + tester 读
    ├── verified/                # kb 读
    ├── released/                # 终点
    └── index.json               # ops 读
```

### 角色入口（v0.20.1 起 Engine 串行驱动）

```
launchd → com.ccc.engine (KeepAlive, 常驻)
  └─ ccc-engine.py 主循环:
       loop:
         in_progress 有 task 在跑?
           → 检查 .done 完成 → 立即跑 reviewer+tester+kb
         planned 有 task?
           → 读 phases.json → 按 phase 边界调度 → 启 opencode
         无事 → sleep 5s
```

Engine 内部直接调 `ccc-board.py` 的角色函数：
- `dev_role_launch / relaunch / check_complete`
- `reviewer_role`（advisory lock + fallback quarantine）
- `tester_role`
- `kb_role`
- `ops_role`（空闲时）

---

## 红线（详见 `references/red-lines.md`）

| # | 红线 | 一句话 |
|---|------|--------|
| 1 | 不动系统文件 | /etc、~/.env、密钥不改 |
| 2 | 验收必须可执行 | 自然语言 + 可选命令 |
| 3 | 不超出 plan 范围 | 白名单外不动 |
| 4 | 单 phase 单 commit | 兜底 commit 由脚本做 |
| 5 | phases.json 必写全 | JSONL，不嵌套 |
| 6 | 角色不互串 | product 不写代码，reviewer 不写 plan |
| 7 | 启动顺序固定 | 读 state.md + profile.md 第一 |
| 8 | 每步必 commit | exec-commit 兜底 |
| 9 | 卡死立即止损 | kill + 下一个角色接管 |
| 10 | 禁止跨会话隐式记忆 | state.md 强制接力 |
| **11** | Verdict 必须有文件 | 口头 PASS 不算 PASS |
| **12** | 禁止 agent 自主启用 CCC | 用户显式触发 |

**配套教训**：
- **Lesson 27**：`claude -p` 是 print 模式，prompt 走 stdin
- **Lesson 28**：口头 PASS 不算 PASS，verdict 必须有产物证据

---

## 关键资产清单

| 路径 | 角色 |
|------|------|
| `SKILL.md` | 唯一注入 prompt |
| `skills/ccc-<role>/SKILL.md` × 7 | 各角色 skill 定义 |
| `references/red-lines.md` | 12 + X6 + R-04/07/08/09/12/14 红线强约束 |
| `scripts/_config.py` | 集中配置（v0.19+） |
| `scripts/_board_store.py` | FileBoardStore 存储抽象（v0.19+, _acquire_lock 30s 强清 v0.24.6+） |
| `scripts/_executor.py` | OpenCodeExecutor 执行器抽象（v0.19+） |
| `scripts/ccc-board.py` | 7 角色看板核心（含 _review_one_task v0.24.5+ 抽取） |
| `scripts/ccc-board-server.py` | 看板 HTTP 服务（GET/POST 都校验 token v0.24.6+） |
| `scripts/ccc-engine.py` | CCC Engine 串行主循环（v0.20.1+, phase 感知 v0.24+） |
| `scripts/ccc-engine.sh` | Engine launchd 入口 |
| `scripts/install-ccc-roles.sh` | 一键装 Engine + board-server plist |
| `scripts/ccc-exec-launcher.sh` | 单 phase 启动入口 |
| `scripts/ccc-exec-commit.sh` | 单 phase 单 commit |
| `scripts/ccc-notify.sh` | macOS 桌面通知（L1/L2/L3） |
| `scripts/ccc-hook.sh` | 通用钩子 |
| `scripts/opencode-exec.py` | OpenCode CLI 执行器（prompt 写 ~/.ccc/prompts/ v0.24.7+） |
| `scripts/opencode-pool.py` | 进程池（max 3 并发） |
| `scripts/opencode-watchdog.sh` | 残留扫描 |
| `templates/` | plan/phases/report/verdict/AGENTS 模板 |
| `tests/scripts/` | pytest 核心测试（92 passed + v0.25 新增 ~15 case） |
| `tests/e2e/` | E2E bash harness（v0.19+, v0.25 新增 phase_aware.sh） |
| `.ccc/state.md` | 接力索引（红线 10） |
| `docs/lessons.md` | 历史教训 |
| `docs/roadmap.md` | 路线图 |
| `CHANGELOG.md` | 版本变更 |

---

## 命名含义

**CCC** = **C**onnect — **C**laude **C**ode

不再代表 Connect–Claude-Code 三个字母以外的东西。没有"3C"扩写含义。

---

## 版本

```
cat ~/program/CCC/VERSION
```

详细历史见 `CHANGELOG.md`。当前：`v0.26.0`。
