---
name: ccc-protocol
description: "CCC — Connect–Claude Code. A 7-role automated development pipeline with kanban board. Trigger when user says: '按 CCC 流程跑 X', 'ccc 跑一下 X', '调度一个多阶段任务', '用看板跑 X'"
---

# CCC — Connect–Claude Code (v0.18)

> **One SKILL, every IDE, every model.** A skill that turns any coding agent
> into a **7-role automated development system** with kanban board and skill-based
> role definitions. Loads cleanly into Trae, Cursor, Zed, VS Code, OpenCode,
> or any tool that supports system-prompt files.
>
> **含义**：**C**onnect–**C**laude **C**ode。把 Claude Code 的能力连接到
> 任何 IDE 工具，让 agent 通过看板自我调度。
>
> **v0.18**：每个角色有独立 SKILL.md（`skills/ccc-<role>/SKILL.md`），职责、
> 方法论、红线全部单独配置。详细参照 `skills/README.md`。

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

### 角色矩阵

| 角色 | Skill 文件 | 看板列 | 频率 | 职责 |
|------|-----------|--------|------|------|
| **product** | `skills/ccc-product/SKILL.md` | backlog → planned | 4h | 拆任务、写 plan、SPEC 门禁 |
| **dev** | `skills/ccc-dev/SKILL.md` | planned → in_progress → testing | 10min | 调 opencode 写代码 |
| **reviewer** | `skills/ccc-reviewer/SKILL.md` | testing → verified | 2h | 只读静态检查 + 范围核对 |
| **tester** | `skills/ccc-tester/SKILL.md` | testing → verified | 4h | pytest + plan 逐条验收 |
| **ops** | `skills/ccc-ops/SKILL.md` | 不动 board | 30min | 健康检查 + 告警 |
| **kb** | `skills/ccc-kb/SKILL.md` | verified → released | 23:00 | git tag + push + changelog |
| **regress** | `skills/ccc-regress/SKILL.md` | released → backlog(回归bug) | 23:30 | 每日回测 + 回归建 bug |

**频率 = 老板拍板，不许改**（红线 X6）。
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
├── phases/<task>.phases.json    # product 产出（JSONL）
├── reports/<task>.report.md     # dev 产出（含 AGENTS.md 建议段）
├── verdicts/<task>.verdict.md   # reviewer/tester 产出（≥3 probes）
└── board/                       # 看板文件（由 ccc-board.py 维护）
    ├── backlog/                 # product 读
    ├── planned/                 # dev 读
    ├── in_progress/             # dev 读
    ├── testing/                 # reviewer + tester 读
    ├── verified/                # kb 读
    ├── released/                # 终点
    └── index.json               # ops 读
```

### 角色入口

每个角色由 launchd plist 周期调用 `scripts/roles/<role>.sh`，该脚本：
1. 设置 `CCC_ROLE` / `CCC_ROLE_SKILL` 环境变量
2. 加载对应 `skills/ccc-<role>/SKILL.md`
3. 调 `scripts/ccc-board.py <role>` 执行机械逻辑

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
| `references/red-lines.md` | 12 + X6 红线强约束 |
| `scripts/ccc-board.py` | 7 角色看板核心 |
| `scripts/ccc-board-server.py` | 看板 HTTP 服务 |
| `scripts/roles/<role>.sh` × 7 | 各角色 launchd 入口 |
| `scripts/install-ccc-roles.sh` | 一键装 7 plist |
| `scripts/ccc-exec-launcher.sh` | 单 phase 启动入口 |
| `scripts/ccc-exec-commit.sh` | 单 phase 单 commit |
| `scripts/ccc-notify.sh` | macOS 桌面通知 |
| `scripts/ccc-hook.sh` | 通用钩子 |
| `scripts/opencode-exec.py` | OpenCode CLI 执行器 |
| `scripts/opencode-pool.py` | 进程池 |
| `scripts/opencode-watchdog.sh` | 残留扫描 |
| `scripts/opencode-runner.sh` | OpenCode 运行器 |
| `templates/` | plan/phases/report/verdict/AGENTS 模板 |
| `tests/scripts/` | pytest 核心测试 |
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

详细历史见 `CHANGELOG.md`。当前：`0.18.0`。
