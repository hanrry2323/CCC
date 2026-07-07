# CCC — Connect–Claude Code

> **框架总纲**（架构 / 红线 / 工程纪律）。本文件不面向 agent，是面向维护者的总览。
> agent 只需要读 `SKILL.md` + 对应角色 `skills/ccc-<role>/SKILL.md`。

---

## 名字含义

**C**onnect — **C**laude **C**ode

CCC 把 Claude Code 的执行能力**连接到任何 IDE 工具**。它：
- 是一个 **SKILL 资产套件**（`SKILL.md` + 6 角色 `skills/`），不是 framework 代码库
- 每个角色有独立 skill 定义（`skills/ccc-<role>/SKILL.md`）
- 能加载到 Trae / Cursor / Zed / VS Code / OpenCode 任意工具

详细定位见 `README.md`，详细路线见 `docs/roadmap.md`。

---

## 工程纪律（12 条核心红线 + X1-X6）

完整版：`~/program/CCC/references/red-lines.md`

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
| **11** | Verdict 必须写 verdict 文件 | 口头 PASS 不算 PASS（Lesson 28） |
| **12** | 禁止 agent 自主启用 CCC | 用户显式触发 |

**X 系列**：X1 OpenCode ≤3 并发 / X2 每 phase 必杀 opencode / X3 启动前 watchdog / X4 看板流转 / X5 7 plist 必装 / X6 角色频率不许改

**Lesson 27**: `claude -p` 是 print 模式开关，prompt 必须走 stdin。

**Lesson 28**: Verdict 强证据红线 11 的来历。

---

## 关键资产清单

| 路径 | 角色 |
|------|------|
| `SKILL.md` | 唯一注入 prompt（agent 启动时自动加载） |
| `skills/ccc-<role>/SKILL.md` × 6 | 各角色 skill 定义 |
| `references/red-lines.md` | 12+X6 红线强约束 |
| `scripts/ccc-board.py` | 6 角色看板核心 |
| `scripts/roles/<role>.sh` × 6 | 各角色 launchd 入口 |
| `scripts/ccc-precheck.sh` | 前置门控 |
| `scripts/ccc-finish.sh` | 后置门控 |
| `scripts/opencode-exec.py` | OpenCode CLI 执行器 |
| `scripts/opencode-pool.py` | 进程池（max 3 并发） |
| `scripts/opencode-watchdog.sh` | 残留扫描 |
| `scripts/ccc-notify.sh` | macOS 桌面通知 |
| `scripts/ccc-exec-launcher.sh` | 单 phase 启动入口 |
| `scripts/ccc-exec-commit.sh` | 单 phase 单 commit |
| `templates/` | plan/phases/report/verdict/AGENTS 模板 |
| `tests/scripts/` | pytest 核心测试 |
| `.ccc/profile.md` + `.ccc/state.md` | 项目档案 + 接力索引 |
| `docs/lessons.md` | 历史教训沉淀 |
| `docs/roadmap.md` | 路线图 |
| `CHANGELOG.md` | 版本变更 |

---

## 6 角色系统（唯一范式）

**v0.18 起不再支持旧 3 角色（Plan/Exec/Verify）流程。**

### 角色矩阵

| 角色 | 频率 | 看板列 | 职责 |
|------|------|--------|------|
| product | 4h | backlog → planned | 拆任务、写 plan、SPEC 门禁 |
| dev | 10min | planned → in_progress → testing | 调 opencode 写代码 |
| reviewer | 2h | testing → verified | 只读静态检查 + 范围核对 |
| tester | 4h | testing → verified | pytest + plan 逐条验收 |
| ops | 30min | 所有列 | 健康检查 + 告警 |
| kb | 23:00 | verified → released | git tag + push + changelog |
| regress | 23:30 | released → backlog(回归bug) | 每日回测 + 回归建 bug |

**频率 = 老板拍板，不许改**（红线 X6）。
**7 plist 装上** = `bash scripts/install-ccc-roles.sh`（红线 X5）。

### 任务流转

```
backlog → planned → in_progress → testing → verified → released
```

详细见 `docs/STRATEGY-MAP.md`。

### 用户路由决策

| 任务规模 | 处理方式 | 谁 |
|---------|---------|----|
| 小（单文件 1-5 行 / 调试 / 查信息） | agent 直接处理 | — |
| 中（多文件 / 跨模块） | CCC skill 启用，指定角色 | agent + user |
| 大（多阶段 / 需完整看板） | CCC skill 启用，全链跑 | 6 角色自动流转 |

**红线 12**：agent 不自主启用 CCC。用户显式触发。

---

## 4 文件契约路径

```
<workspace>/.ccc/
├── profile.md              # 项目档案（首次接入生成）
├── plans/<task>.plan.md    # product 产出
├── phases/<task>.phases.json  # product 产出（JSONL）
├── reports/<task>.report.md   # dev 产出
├── verdicts/<task>.verdict.md # reviewer/tester 产出（≥3 probes）
└── board/                    # 看板文件
    ├── backlog/
    ├── planned/
    ├── in_progress/
    ├── testing/
    ├── verified/
    ├── released/
    └── index.json
```

---

## 角色入口架构

```
launchd plist
  → scripts/roles/<role>.sh
      → export CCC_ROLE=<role>
      → export CCC_ROLE_SKILL=skills/ccc-<role>/SKILL.md
      → log skill frontmatter
      → python3 scripts/ccc-board.py <role>
```

---

## 默认预算

| 类型 | Phase 数 | USD |
|------|---------|-----|
| 调研 / 审计 | 6 | 200 |
| 修复 / 重构 | 1-3 | 30-50 |
| 简单文件操作 | 1 | 20 |
| push / 部署 | 1 | 5-30 |

---

## 与 qxo 的关系（已解耦）

v0.5 起 CCC 与 qxo 完全解耦。CCC = 通用 SKILL，不绑任何项目。

---

## 版本

```
cat ~/program/CCC/VERSION
```

详细历史见 `CHANGELOG.md`。当前：`0.18.0`。
