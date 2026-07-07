# CCC — Connect–Claude Code

> **框架总纲**（架构 / 红线 / 工程纪律）。本文件不面向 agent，是面向维护者的总览。
> agent 只需要读 `SKILL.md`。

---

## 名字含义

**C**onnect — **C**laude **C**ode

CCC 把 Claude Code 的执行能力**连接到任何 IDE 工具**。它：
- 是一个 **SKILL 资产**（`SKILL.md`），不是 framework 代码库
- 能加载到 Trae / Cursor / Zed / VS Code / OpenCode 任意工具
- 配合 IDE 定时任务 + 知识飞轮 = **最小化的 Loop Engineering**

详细定位见 `README.md`，详细路线见 `docs/roadmap.md`。

---

## 工程纪律（11 条红线 + 2 条教训）

完整版：`~/program/CCC/references/red-lines.md`

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
| **12** | 禁止 agent 自主启用 CCC | 用户显式触发（Lesson 28 配套） |
| **X1** | OpenCode 进程池最多 3 并发 | v0.8：M1 8GB 内存敏感 |
| **X2** | 每 phase 必杀 opencode 进程 | v0.8：finally + watchdog 兜底 |
| **X3** | OpenCode 启动前必跑残留 watchdog | v0.8：launcher Step 1 |

**Lesson 27**: `claude -p` 是 print 模式开关，prompt 必须走 stdin（**别写成 `claude -p "..."`**）。

**Lesson 28**: Verdict 强证据红线 11 的来历 + 工程教训。

---

## 关键资产清单

| 路径 | 角色 |
|------|------|
| `SKILL.md` | 唯一注入 prompt（agent 启动时自动加载） |
| `references/red-lines.md` | 13+2+X3 红线强约束（v0.8 新增 OpenCode 进程红线 X1/X2/X3） |
| `scripts/ccc-precheck.sh` | 5 项前置门控（红线 7+10） |
| `scripts/ccc-finish.sh` | 5 项后置门控 |
| `scripts/opencode-exec.py` | **OpenCode CLI 执行器**（v0.8 替换 claude 直接调用） |
| `scripts/opencode-pool.py` | **OpenCode 进程池**（max 3 并发，红线 X1） |
| `scripts/opencode-watchdog.sh` | **OpenCode 残留扫描**（红线 X2/X3） |
| `scripts/ccc-notify.sh` | **macOS 桌面通知**（升级链 L1/L2/L3） |
| `scripts/ccc-hook.sh` | **通用钩子**（pre-exec / post-exec / on-error） |
| `scripts/ccc-exec-launcher.sh` | 单 phase 启动入口 |
| `scripts/ccc-exec-commit.sh` | 单 phase 单 commit（红线 4+8） |
| `scripts/ccc` | CLI wrapper |
| `scripts/ccc-init.py` + `ccc-search.py` + `ccc-status.sh` + `ccc-task-done.sh` | 基础运维 |
| `templates/` | 4 文件契约模板（plan/phases/report/verdict/executor-prompt/AGENTS） |
| `tests/scripts/` | pytest 核心测试 |
| `scripts/flywheel-scan.sh` | **飞轮扫描**（v0.9b 简化版，红线 18 强制人工 review） |
| `scripts/ccc-queue.sh` | **队列执行器**（v0.9b 多 phase + 失败升级） |
| `references/adapters/runtime-opencode.md` | **OpenCode 执行器契约**（v0.8 重写） |
| `.ccc/profile.md` + `.ccc/state.md` | 项目档案 + 接力索引（红线 7+10） |
| `docs/lessons.md` | 历史教训沉淀（含 lesson 30：验收数字规则） |
| `docs/roadmap.md` | 路线图（v0.5 → v1.0） |
| `CHANGELOG.md` | 版本变更 |

---

## 6 角色（v0.16 起）/ 3 角色旧路由

### 6 角色（v0.16 当前范式）

| 角色 | 频率 | 扫哪列 | 干 |
|------|------|--------|-----|
| product | 4h | backlog | 写 plan.md + phases.json，挪 planned |
| dev | 30min | planned | 调 opencode 写代码，挪 testing |
| reviewer | 2h | testing | py_compile 静态检查，挪 verified |
| tester | 4h | testing | pytest，挪 verified |
| ops | 30min | 所有列 | 健康检查 + 告警 |
| kb | 23:00 | verified | git tag + push，挪 released |

**频率 = 老板拍板，不许改**（红线 X6）。
**6 plist 装上** = `bash scripts/install-ccc-roles.sh`（红线 X5）。

### 任务流转（看板）

```
backlog → planned → in_progress → testing → verified → released
```

详细见 `docs/STRATEGY-MAP.md`（v0.17 起必读第一文件）。

### 旧 3 角色路由（兼容）

| 任务规模 | 处理方式 | 谁 |
|---------|---------|----|
| 小（单文件 1-5 行 / 调试 / 查信息） | agent 直接处理 | — |
| 中（多文件 / 跨模块） | CCC skill 启用 | agent + user |
| 大（多阶段 / 跨会话） | CCC skill 强制 | agent + user + 独立 verifier |

**用户决策权**：agent 不替用户判断。**红线 12** 强制"agent 不自主启用 CCC"。

---

## 4 文件契约路径

```
<workspace>/.ccc/
├── profile.md              # 项目档案（首次接入生成）
├── plans/<task>.plan.md    # Planner 产出
├── phases/<task>.phases.json  # Planner 产出（JSONL）
├── reports/<task>.report.md   # Executor 产出（含 > VERDICT: 引用段）
├── verdicts/<task>.verdict.md # Verifier 产出（≥3 probes，强证据）
└── abnormal-reports/         # 异常 / 红线违反
```

`<workspace>` = agent 当前项目根。**agent 自动**用当前工作目录，不强约定。

---

## 默认预算

| 类型 | Phase 数 | USD |
|------|---------|-----|
| 调研 / 审计 | 6 | 200 |
| 修复 / 重构 | 1-3 | 30-50 |
| 简单文件操作 | 1 | 20 |
| push / 部署 | 1 | 5-30 |

---

## 工程纪律配套扩展

| 扩展位 | 当前 |
|-------|------|
| 跨工具调用 | SKILL 已可移植（自然支持） |
| 跨模型路由 | `ANTHROPIC_BASE_URL` 中转站 |

SKILL 文件是**唯一注入 prompt**，**所有工程纪律沉淀在 references/ 和 docs/**。
v0.5+ 路线（IDE 定时任务 / 知识飞轮 / 跨设备集群）已在 v0.7-slim 精简移除，不再预留。

---

## 与 qxo 的关系（已解耦）

早期 CCC 内部嵌入 qxo 子项目（`projects/qxo/`）。**v0.5 起彻底解耦**：
- `projects/qxo/` 删除
- 教训沉淀迁到根 `docs/lessons.md`
- CCC = 通用 SKILL，不再绑任何特定项目

---

## 版本

```
cat ~/program/CCC/VERSION
```

详细历史见 `CHANGELOG.md`。当前：`0.5.0`。
