# CCC Code Wiki — Connect-Claude Code

> **版本**: v0.20.0  
> **最后更新**: 2026-07-09  
> **文档目的**: 为开发者提供完整的项目架构、模块职责、关键API、依赖关系和运行方式说明

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [目录结构](#3-目录结构)
4. [主要模块职责](#4-主要模块职责)
5. [关键类与函数说明](#5-关键类与函数说明)
6. [依赖关系](#6-依赖关系)
7. [项目运行方式](#7-项目运行方式)
8. [配置说明](#8-配置说明)
9. [测试体系](#9-测试体系)
10. [红线约束](#10-红线约束)

---

## 1. 项目概述

### 1.1 项目定位

**CCC (Connect-Claude Code)** 是一个 **7角色看板自动化开发系统**。它不是传统意义上的框架代码库，而是一套 **prompt资产套件 + 工程纪律沉淀**，将任何编码代理（coding agent）转变为具备完整软件开发流程的自动化系统。

### 1.2 核心理念

```
CCC = 1 个 SKILL.md（总纲）
      + 7 个角色 SKILL.md
      + 12+X6 红线约束
      + 看板（board/）
      + 7 launchd plist 周期跑
```

### 1.3 核心特性

- **跨IDE兼容**: 可加载到 Trae、Cursor、Zed、VS Code、OpenCode 等任何支持 system-prompt 文件的工具
- **7角色流水线**: product → dev → reviewer → tester → ops → kb → regress
- **看板驱动**: 任务在 6 列看板中流转，不可跳列
- **强约束保障**: 20+ 条红线确保系统稳定性和安全性
- **独立模型路由**: 通过 `ANTHROPIC_BASE_URL` 中转站按任务类型自动选模型

### 1.4 任务流转

```
backlog → planned → in_progress → testing → verified → released
                                                              ↓ (regress 23:30)
                                                         backlog(回归bug)
```

---

## 2. 整体架构

### 2.1 三层架构（v0.19起）

```
┌──────────────────────────────────────┐
│        7 个角色函数                   │  ← L3: 业务逻辑层
│  product_role / dev_role /           │     不知道存储实现、不知道执行器实现
│  reviewer_role / tester_role /       │     只调 BoardStore + Executor 接口
│  ops_role / kb_role / regress_role   │
└───────────┬──────────────┬───────────┘
            │              │
    ┌───────▼──────┐ ┌────▼────────┐
    │ BoardStore   │ │ Executor    │  ← L2: 抽象接口层
    │ create_task  │ │ execute()   │     只定义契约，不实现
    │ move_task    │ │             │
    │ list_tasks   │ │             │
    └───────┬──────┘ └─────┬───────┘
            │              │
    ┌───────▼──────────────▼───────────┐
    │  FileBoardStore   OpenCodeExec   │  ← L1: 当前实现层
    │  (.jsonl + flock)  (CLI 子进程)  │     可替换（数据库 / Docker）
    └──────────────────────────────────┘
```

### 2.2 架构优势

- **存储层可替换**: `FileBoardStore` → `PostgresBoardStore`，角色代码完全不需要修改
- **执行器可替换**: `OpenCodeExecutor` → `ContainerExecutor`，角色代码完全不需要修改
- **配置集中**: 所有参数从 `Config` 对象读取，不在代码中硬编码
- **关注点分离**: 业务逻辑、抽象接口、具体实现三层解耦

### 2.3 物理部署架构

```
launchd (macOS 定时器)
  │
  ├─ product (4h):  backlog → plan.md + phases.json → planned
  ├─ dev (10min):    planned → opencode write code → testing
  ├─ reviewer (2h):  testing → py_compile + static check → verified
  ├─ tester (4h):    testing → pytest + plan 逐条验收 → verified
  ├─ ops (30min):    健康检查 + 告警 (不动 board)
  ├─ regress (23:30): released → backlog (回归回测 + 建 bug)
  └─ kb (23:00):     git tag + push + changelog → released

每个角色:
  1. 加载 skills/ccc-<role>/SKILL.md (角色定义 + 方法论 + 红线)
  2. 调 scripts/ccc-board.py <role> (看板操作)
  3. 写日志到 ~/.ccc/logs/role-<role>-<ts>.log
```

---

## 3. 目录结构

```
/workspace/
├── SKILL.md                          # ★ 唯一注入 prompt（7角色系统总纲）
├── README.md                         # 项目说明
├── STARTUP-BRIEF.md                  # 启动必读（~200 token）
├── CLAUDE.md                         # 框架总纲（维护者用）
├── CHANGELOG.md                      # 版本变更日志
├── VERSION                           # 当前版本号
├── LICENSE
│
├── skills/                           # ★ 7角色 skill 定义
│   ├── README.md                     # 7角色 skill 索引
│   ├── ccc-product/SKILL.md          # 产品经理
│   ├── ccc-dev/SKILL.md              # 开发工程师
│   ├── ccc-reviewer/SKILL.md         # 代码审查员
│   ├── ccc-tester/SKILL.md           # 测试工程师
│   ├── ccc-ops/SKILL.md              # 运维监控
│   ├── ccc-kb/SKILL.md               # 知识管理员
│   └── ccc-regress/SKILL.md          # 回测工程师
│
├── scripts/                          # ★ 核心脚本
│   ├── _config.py                    # 集中配置（Config 类）
│   ├── _board_store.py               # 看板存储抽象（FileBoardStore）
│   ├── _executor.py                  # 执行器抽象（OpenCodeExecutor）
│   ├── ccc-board.py                  # ★ 7角色看板核心
│   ├── ccc-board-server.py           # 看板 HTTP 服务
│   ├── ccc                           # CLI 入口
│   ├── ccc-init.py                   # 项目初始化
│   ├── ccc-search.py                 # 搜索工具
│   ├── ccc-status.sh                 # 状态查看
│   ├── ccc-notify.sh                 # macOS 桌面通知
│   ├── ccc-hook.sh                   # 通用钩子
│   ├── ccc-exec-launcher.sh          # 单 phase 启动入口
│   ├── ccc-exec-commit.sh            # 单 phase 单 commit
│   ├── opencode-exec.py              # OpenCode CLI 执行器
│   ├── opencode-pool.py              # 进程池（max 3 并发）
│   ├── opencode-watchdog.sh          # 残留扫描
│   ├── opencode-runner.sh            # OpenCode 运行器
│   ├── install-ccc-roles.sh          # 一键装 7 plist
│   ├── install-board-plist.sh        # 看板 plist 安装
│   ├── install-ccc-scheduler.sh      # 调度器安装
│   ├── flywheel-scan.sh              # 飞轮扫描
│   ├── roles/                        # 7角色 launchd 入口
│   │   ├── product.sh
│   │   ├── dev.sh
│   │   ├── reviewer.sh
│   │   ├── tester.sh
│   │   ├── ops.sh
│   │   ├── kb.sh
│   │   └── regress.sh
│   └── ccc-board-ui/                 # 看板前端 UI
│       └── index.html
│
├── templates/                        # 4文件契约模板
│   ├── plan.plan.md                  # plan 模板
│   ├── phases.phases.json            # phases 模板
│   ├── report.report.md              # report 模板
│   ├── verdict.verdict.md            # verdict 模板
│   ├── AGENTS.md                     # AGENTS 模板
│   ├── pending-agents-suggestions.md # 待审批建议模板
│   ├── ccc-config.sh                 # 配置模板
│   ├── .ccc-profile.md               # 项目档案模板
│   └── hooks/                        # 钩子模板
│       ├── pre-commit.sh
│       ├── post-exec.sh
│       └── on-error.sh
│
├── references/                       # 参考资料
│   ├── red-lines.md                  # ★ 12+X6 红线强约束
│   ├── board-task-schema.md          # task JSONL 格式标准
│   ├── file-contract.md              # 文件契约
│   └── adapters/
│       └── runtime-opencode.md       # OpenCode 适配器
│
├── docs/                             # 文档
│   ├── architecture.md               # 架构说明书
│   ├── arch-overview.md              # 架构总览
│   ├── STRATEGY-MAP.md               # 战略地图
│   ├── roadmap.md                    # 路线图
│   ├── lessons.md                    # 教训沉淀
│   ├── plan-spec.md                  # Plan 规范
│   ├── verification-spec.md          # 验证规范
│   ├── execution-protocol.md         # 执行协议
│   ├── resilience-design.md          # 弹性设计
│   ├── dev-workflow.md               # 开发工作流
│   ├── engineer-flow.md              # 工程师流程
│   ├── USAGE.md                      # 使用指南
│   ├── config.md                     # 配置说明
│   ├── TROUBLESHOOTING.md            # 故障排除
│   ├── E2E-DEMO.md                   # E2E 演示
│   ├── CONTRIBUTING.md               # 贡献指南
│   ├── GLOSSARY.md                   # 术语表
│   ├── idempotent-commit.md          # 幂等提交
│   ├── handoff-checklist.md          # 交接清单
│   ├── handoff-report.md             # 交接报告
│   └── adr/                          # 架构决策记录
│       ├── 001-protocol-layer.md
│       ├── 002-runtime-adapter.md
│       ├── 003-scheduler-adapter.md
│       ├── 004-multi-platform-orchestration.md
│       └── 005-daily-audit-closed-loop.md
│
├── tests/                            # 测试
│   ├── scripts/                      # pytest 单元测试
│   │   ├── test_ccc_exec_commit_smoke.py
│   │   ├── test_ccc_exec_commit_idempotency.py
│   │   ├── test_ccc_exec_commit_jsonl_smoke.py
│   │   ├── test_ccc_init_search_smoke.py
│   │   ├── test_ccc_status_smoke.py
│   │   ├── test_bug_fixes_v012.py
│   │   ├── test_opencode_pool_max_parallel.py
│   │   ├── test_opencode_pool_kill_residual.py
│   │   └── test_opencode_watchdog_cleanup.py
│   └── e2e/                          # 端到端测试
│       └── test_pipeline_smoke.sh
│
├── .ccc/                             # 运行时数据（工作区内）
│   ├── profile.md                    # 项目档案
│   ├── state.md                      # 接力索引
│   ├── metrics.json                  # 运行指标
│   ├── board/                        # 看板文件
│   │   ├── backlog/                  # 待办
│   │   ├── planned/                  # 已计划
│   │   ├── in_progress/              # 开发中
│   │   ├── testing/                  # 测试中
│   │   ├── verified/                 # 已验证
│   │   ├── released/                 # 已发布
│   │   ├── abnormal/                 # 异常隔离
│   │   ├── events/                   # 事件历史
│   │   ├── index.json                # 状态总览
│   │   └── .board.lock               # 文件锁
│   ├── plans/                        # plan 文件
│   ├── phases/                       # phases 文件
│   ├── reports/                      # 报告文件
│   ├── verdicts/                     # 验收文件
│   └── pids/                         # 运行时 PID
│
└── .github/
    └── workflows/
        └── ci.yml                    # CI 配置
```

---

## 4. 主要模块职责

### 4.1 配置模块 (`_config.py`)

**文件**: [_config.py](file:///workspace/scripts/_config.py)

**职责**: 集中管理所有 CCC 配置参数，提供环境变量覆盖机制。

**核心类**: `Config` (dataclass)

| 配置项 | 类型 | 默认值 | 环境变量 | 说明 |
|--------|------|--------|----------|------|
| `ccc_home` | Path | 自动计算 | - | CCC 根目录 |
| `workspace` | Path | ccc_home | `CCC_WORKSPACE` | 工作区路径 |
| `model` | str | `"loop/flash"` | `OPENCODE_MODEL` | 默认模型 |
| `default_timeout` | int | 600 | `CCC_TIMEOUT` | phase 默认超时（秒） |
| `hook_timeout` | int | 30 | `CCC_HOOK_TIMEOUT` | 钩子超时（秒） |
| `max_retry` | int | 5 | `CCC_MAX_RETRY` | 最大重试次数 |
| `max_stale_hours` | int | 6 | `CCC_STALE_HOURS` | in_progress 超时阈值（小时） |
| `opencode_max_parallel` | int | 3 | - | OpenCode 最大并发数 |
| `board_port` | int | 7777 | `BOARD_PORT` | 看板 HTTP 服务端口 |
| `board_host` | str | `"127.0.0.1"` | `BOARD_HOST` | 看板 HTTP 服务地址 |

### 4.2 看板存储模块 (`_board_store.py`)

**文件**: [_board_store.py](file:///workspace/scripts/_board_store.py)

**职责**: 提供看板存储抽象层，当前实现为基于 JSONL 文件系统的 `FileBoardStore`。

**核心类**: `FileBoardStore`

**看板列定义** (`COLUMNS`):

| 列名 | 说明 |
|------|------|
| `backlog` | 待办收件箱 |
| `planned` | 已计划（有 plan + phases） |
| `in_progress` | 开发执行中 |
| `testing` | 待测试/验收 |
| `verified` | 已验证通过 |
| `released` | 已发布 |
| `abnormal` | 异常隔离 |

**列流转白名单** (`COLUMN_TRANSITIONS`):

| 目标列 | 允许的源列 |
|--------|-----------|
| `planned` | `backlog` |
| `in_progress` | `planned` |
| `testing` | `in_progress` |
| `verified` | `testing` |
| `released` | `verified` |
| `backlog` | `released`, `in_progress`, `abnormal` |
| `abnormal` | `in_progress`, `testing`, `verified`, `released` |

**核心方法**:

| 方法 | 说明 |
|------|------|
| `create_task(data, column)` | 创建新任务（含ID唯一性校验 + 文件锁） |
| `list_tasks(column)` | 列出某列所有任务（共享读锁） |
| `move_task(task_id, from_col, to_col)` | 移动任务（文件锁 + 原子写入 + 白名单约束） |
| `update_index()` | 更新 index.json 状态总览 |
| `quarantine(task_id, reason)` | 将任务移入异常列 |
| `get_timeline(task_id)` | 获取任务时间线事件 |

**技术保障**:
- **文件锁**: 使用 `fcntl.flock` 防止竞态条件（macOS/Linux）
- **原子写入**: 临时文件 + `os.replace` 防止部分写入
- **事件溯源**: 所有移动操作记录到 `events/<task_id>.events.jsonl`

### 4.3 执行器模块 (`_executor.py`)

**文件**: [_executor.py](file:///workspace/scripts/_executor.py)

**职责**: 提供执行器抽象，当前实现为 OpenCode CLI 子进程调用。

**核心类**:
- `Executor` (协议基类)
- `OpenCodeExecutor` (具体实现)

**执行结果结构** (`ExecResult`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `phase_id` | str | phase 标识 |
| `exit_code` | int | 退出码 |
| `stdout` | str | 标准输出 |
| `stderr` | str | 标准错误 |
| `duration_s` | float | 执行时长（秒） |
| `pid` | int | 进程 PID |
| `killed` | bool | 是否被强制终止 |

**核心方法**: `execute(phase_id, prompt, timeout, cwd, model)`

**OpenCode 路径解析优先级**:
1. `OPENCODE_BIN` 环境变量
2. `shutil.which("opencode")`（PATH 中查找）
3. `~/.npm-global/bin/opencode`（npm 全局安装路径）

**超时处理机制** (红线 X2):
1. 超时后先发送 `SIGTERM`
2. 5 秒后仍未退出则发送 `SIGKILL`
3. 使用 `killpg` 级联终止整个进程组（含孙子进程）

### 4.4 看板核心模块 (`ccc-board.py`)

**文件**: [ccc-board.py](file:///workspace/scripts/ccc-board.py)

**职责**: 7 角色业务逻辑的核心实现，所有角色都通过此模块操作看板。

**7 角色函数**:

| 角色函数 | 频率 | 看板操作 | 职责 |
|----------|------|----------|------|
| `product_role()` | 4h | backlog → planned | 拆任务、写 plan、SPEC 门禁 |
| `dev_role()` | 10min | planned → in_progress → testing | 调 opencode 写代码 |
| `reviewer_role()` | 2h | testing → verified | py_compile 静态检查 + 范围核对 |
| `tester_role()` | 4h | testing → verified | pytest + plan 验收项逐条验证 |
| `ops_role()` | 30min | 不动 board | 健康检查 + stale 检测 + 告警 |
| `kb_role()` | 每天 23:00 | verified → released | git tag + push + changelog + 收集建议 |
| `regress_role()` | 每天 23:30 | released → backlog | 每日回测 + 回归建 bug |

**辅助函数**:
- `create_task(data, column)`: 创建任务
- `list_tasks(column)`: 列出任务
- `move_task(task_id, from_col, to_col)`: 移动任务
- `update_index()`: 更新索引
- `_parse_plan_scope(task_id)`: 从 plan.md 解析文件白名单
- `_extract_agents_suggestions()`: 提取 AGENTS.md 建议
- `approve_agents()`: 审批 AGENTS.md 建议
- `batch_process(lines)`: 批量处理 create/move 操作
- `_backoff_seconds(retry)`: 指数退避计算
- `_quarantine(task_id, reason)`: 异常隔离

### 4.5 看板 HTTP 服务 (`ccc-board-server.py`)

**文件**: [ccc-board-server.py](file:///workspace/scripts/ccc-board-server.py)

**职责**: 提供 REST API + 前端 UI，默认绑定 `127.0.0.1:7777`。

**API 端点**:

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api` | API 信息 |
| GET | `/api/board` | 看板状态（所有列任务 + 计数） |
| GET | `/api/config` | 配置信息（列、颜色、角色等） |
| GET | `/api/tasks/<id>` | 单个任务详情 |
| GET | `/api/tasks/<id>/events` | 任务事件流 |
| GET | `/api/timeline` | 最近事件时间线 |
| GET | `/api/roles` | 7 角色执行状态 |
| GET | `/api/logs` | 角色执行日志 |
| POST | `/api/tasks` | 创建新任务 |
| POST | `/api/tasks/move` | 移动任务 |

**特性**:
- 支持多 workspace（自动发现 CCC / qxo 等）
- CORS 支持（`Access-Control-Allow-Origin: *`）
- 纯 Python 标准库实现，无额外依赖

### 4.6 OpenCode 进程池 (`opencode-pool.py`)

**文件**: [opencode-pool.py](file:///workspace/scripts/opencode-pool.py)

**职责**: 使用 `asyncio.Semaphore` 限制 OpenCode 并发数 ≤ 3（红线 X1）。

**核心机制**:
- `asyncio.Semaphore(MAX_PARALLEL)` 控制并发
- `run_in_executor` 包装同步执行器
- `asyncio.gather` 批量执行，支持异常隔离
- SIGTERM 信号处理，优雅取消

**退出码**:
- 0: 全部成功
- 4: 部分失败
- 1: 超过并发上限
- 2: tasks 文件不存在
- 3: tasks 格式错误
- 130: 被取消（Ctrl+C）

### 4.7 OpenCode 执行器 (`opencode-exec.py`)

**文件**: [opencode-exec.py](file:///workspace/scripts/opencode-exec.py)

**职责**: 单 phase 的 OpenCode CLI 执行，提供异步 `run_opencode` 函数。

**退出码**:

| 退出码 | 说明 |
|--------|------|
| 0 | phase 执行成功 |
| 10 | opencode 二进制不存在 |
| 11 | prompt 文件不存在 |
| 12 | watchdog 检查失败 |
| 20 | opencode exec 超时（已被 kill） |
| 30 | opencode exec 异常崩溃 |
| 非0 | opencode 本身非零退出 |

**核心函数**: `run_opencode(phase_id, prompt_text, timeout, cwd, cmd, opencode_bin)`

**长 prompt 处理**:
- prompt ≤ 200 字符: 直接作为 positionals 参数
- prompt > 200 字符: 写入临时文件，用 `--file` 附件方式传递（Lesson 33）

### 4.8 Commit 工具 (`ccc-exec-commit.sh`)

**文件**: [ccc-exec-commit.sh](file:///workspace/scripts/ccc-exec-commit.sh)

**职责**: Executor 退出后自动执行 git commit，替代 LLM 做机械操作。

**特性**:
- **幂等性**: 已填 commit hash 的 phase 自动 skip
- **格式兼容**: 支持 JSON / JSONL / 数组 三种 phases.json 格式
- **scope 检查**: 多 phase 改同一文件时检测重叠并阻断
- **自动标记**: commit message 自动追加 `ccc-task-id=<id>`
- **sidecar 存储**: task_id 存储在 `.task_id` 附属文件，不污染 phases.json

**用法**:
```bash
ccc-exec-commit.sh <workspace> <task>              # 处理所有待 commit phase
ccc-exec-commit.sh <workspace> <task> --phase N    # 仅处理指定 phase
```

### 4.9 角色入口脚本 (`scripts/roles/*.sh`)

每个角色对应一个 launchd 入口脚本，负责：
1. 设置 `CCC_ROLE` / `CCC_ROLE_SKILL` 环境变量
2. 修复 launchd 环境 PATH 问题
3. 加载对应 skill 并记录日志
4. 调用 `ccc-board.py <role>` 执行

**示例** ([dev.sh](file:///workspace/scripts/roles/dev.sh)):
```bash
export CCC_ROLE=dev
export CCC_ROLE_SKILL=${CCC_HOME}/skills/ccc-dev/SKILL.md
export PATH="/Users/apple/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
python3 "$CCC_HOME/scripts/ccc-board.py" "$CCC_ROLE"
```

### 4.10 Skills 模块 (`skills/`)

**文件**: [skills/README.md](file:///workspace/skills/README.md)

7 个角色各有独立的 SKILL.md，定义了每个角色的职责、方法论、红线约束。

| 角色 | 目录 | 核心职责 |
|------|------|----------|
| product | `ccc-product/` | 需求拆解、计划制定、SPEC 门禁 |
| dev | `ccc-dev/` | 代码实现、调用 OpenCode |
| reviewer | `ccc-reviewer/` | 静态代码审查、范围核对 |
| tester | `ccc-tester/` | 动态测试、验收验证 |
| ops | `ccc-ops/` | 健康监控、异常告警 |
| kb | `ccc-kb/` | 版本发布、知识沉淀 |
| regress | `ccc-regress/` | 回归测试、bug 发现 |

### 4.11 模板模块 (`templates/`)

提供 4 文件契约的标准模板：

| 模板文件 | 产出角色 | 用途 |
|----------|----------|------|
| `plan.plan.md` | product | 执行计划 + 文件白名单 + 验收项 |
| `phases.phases.json` | product | 分阶段执行计划 |
| `report.report.md` | dev | 执行报告 + AGENTS.md 建议 |
| `verdict.verdict.md` | reviewer/tester | 验收结论 + 证据 |

---

## 5. 关键类与函数说明

### 5.1 Config 类

**位置**: [_config.py#L12-L80](file:///workspace/scripts/_config.py#L12-L80)

```python
@dataclass
class Config:
    ccc_home: Path           # CCC 根目录
    workspace: Path          # 工作区路径
    model: str               # 默认模型
    default_timeout: int     # 默认超时（秒）
    hook_timeout: int        # 钩子超时（秒）
    max_retry: int           # 最大重试次数
    max_stale_hours: int     # 任务滞留阈值（小时）
    opencode_max_parallel: int  # 最大并发数
    board_port: int          # HTTP 服务端口
    board_host: str          # HTTP 服务地址
```

**使用方式**:
```python
from _config import Config
cfg = Config()
print(cfg.model)  # "loop/flash"
```

**设计要点**:
- 所有字段有默认值
- 环境变量优先级高于默认值
- `__post_init__` 中自动读取环境变量覆盖

### 5.2 FileBoardStore 类

**位置**: [_board_store.py#L105-L345](file:///workspace/scripts/_board_store.py#L105-L345)

**核心方法详解**:

#### `create_task(data, column="backlog") -> bool`

创建新任务。包含以下校验：
- 必填字段检查（`id`）
- 列名合法性校验
- ID 唯一性校验（全列扫描）

写入操作：
1. 获取排他文件锁
2. 检查 ID 是否已存在
3. 填充元数据（created_at、updated_at、status）
4. 原子写入 JSONL 文件
5. 记录事件到 events 目录

#### `move_task(task_id, from_col, to_col) -> bool`

移动任务。包含以下校验：
- 列流转白名单检查（`COLUMN_TRANSITIONS`）
- 源列中任务存在性检查

移动操作：
1. 获取排他文件锁
2. 读取源任务
3. 更新 status 和 updated_at
4. 原子写入目标列
5. 删除源列文件
6. 记录移动事件

#### `quarantine(task_id, reason) -> None`

将任务移入异常列。
- 自动搜索任务所在列
- 添加 `abnormal` 和 `automated` 标签
- 标题前缀 `[ABNORMAL]`
- 记录异常原因到 note 字段

### 5.3 OpenCodeExecutor 类

**位置**: [_executor.py#L82-L199](file:///workspace/scripts/_executor.py#L82-L199)

**核心方法**: `execute(phase_id, prompt, timeout, cwd, model) -> ExecResult`

**执行流程**:
1. 解析 opencode 可执行文件路径
2. 处理 prompt（短 prompt 直传，长 prompt 写临时文件）
3. 启动子进程（`start_new_session=True` 创建新进程组）
4. 写入 PID 文件
5. 等待执行完成或超时
6. 超时处理：TERM → 5s → KILL（进程组级联终止）
7. 清理 PID 文件和临时文件
8. 返回结构化结果

### 5.4 dev_role 函数

**位置**: [ccc-board.py#L282-L562](file:///workspace/scripts/ccc-board.py#L282-L562)

开发角色主循环，是最复杂的角色函数。

**执行流程**:

```
Step 1: 检查 in_progress 列（重试逻辑）
  ├─ 有卡住任务
  │   ├─ 读取 retry 计数和 retry_at
  │   ├─ 检查 .done 文件（防退避死锁）
  │   ├─ 退避期内 → 跳过，去 planned
  │   ├─ 达到最大重试 → 异常隔离 + 建紧急 bug
  │   └─ 更新 retry 计数，继续执行
  └─ 无卡住任务 → 去 Step 2

Step 2: 从 planned 列取任务
  ├─ 迭代所有 planned 任务
  ├─ 跳过缺 plan/phases 的（移入异常）
  └─ 找到第一个合法任务 → 挪到 in_progress

Step 3: 执行任务
  ├─ 检查 .done 文件（已完成则直接处理结果）
  ├─ 检查 PID 文件（运行中则跳过本轮）
  └─ 启动 opencode-runner.sh 后台执行
```

**异常隔离机制**:
- 达到 `MAX_RETRY`（默认5次）自动移入 abnormal
- 同时在 backlog 创建紧急修复任务
- 指数退避：`60 * 2^retry` 秒，封顶 3600s

### 5.5 product_role 函数

**位置**: [ccc-board.py#L214-L279](file:///workspace/scripts/ccc-board.py#L214-L279)

产品经理角色，负责拆解任务。

**两种模式**:
1. **列表模式**: 列出 backlog 中所有待处理任务
2. **Promote 模式** (`--promote <task_id>`): 
   - 调用 Claude API 生成 plan.md + phases.json
   - API 不可用时使用 fallback plan
   - 将任务从 backlog 挪到 planned

**Plan 生成输入**:
- 项目档案 (profile.md)
- 任务信息 (id, title, description)
- Plan 模板
- 历史 plan 参考（最近2个）

### 5.6 ops_role 函数

**位置**: [ccc-board.py#L732-L849](file:///workspace/scripts/ccc-board.py#L732-L849)

运维监控角色，执行健康检查。

**检查项**:

| 检查项 | 说明 |
|--------|------|
| Stale 检测 | in_progress 超过 6h 未更新 → 移入 abnormal |
| 孤儿 PID 清理 | 清理不存在进程的 PID 文件及关联文件 |
| abnormal 列上报 | 报告异常列任务数量和原因 |
| git ahead 检查 | 检查本地领先远端的 commit 数 |
| launchd 自检 | 检查 7 个角色 plist 是否存活 |
| 日志清理 | 删除 >30 天的 role 日志 |
| 指标收集 | 写入 `.ccc/metrics.json` |

### 5.7 kb_role 函数

**位置**: [ccc-board.py#L876-L986](file:///workspace/scripts/ccc-board.py#L876-L986)

知识管理员角色，负责发布归档。

**执行流程**:
1. 遍历 verified 列任务
2. 创建 git tag: `board-<task_id>`
3. git push tag 到 origin
4. 追加 CHANGELOG.md 条目
5. 提取 report/verdict 中的 AGENTS.md 建议
6. 将任务挪到 released
7. 去重后写入 `pending-agents-suggestions.md`

### 5.8 regress_role 函数

**位置**: [ccc-board.py#L989-L1093](file:///workspace/scripts/ccc-board.py#L989-L1093)

回测工程师角色，每日回归测试。

**回测内容**:
1. **py_compile 检查**: 所有 Python 文件语法检查
2. **git diff 检查**: 检查是否有意外改动

**发现回归时**:
1. 创建新 bug 任务到 backlog
2. 原任务加 `regression` 标签并移回 backlog
3. 发送 macOS 桌面通知（L2 级别）
4. 写入回测日报到 `.ccc/reports/regression-<date>.md`

---

## 6. 依赖关系

### 6.1 内部模块依赖

```
ccc-board.py
  ├── _config.py          (Config)
  └── _board_store.py     (FileBoardStore)

ccc-board-server.py
  ├── _config.py          (Config)
  └── _board_store.py     (FileBoardStore, COLUMNS)

opencode-pool.py
  └── _executor.py        (OpenCodeExecutor)

opencode-exec.py
  └── _executor.py        (resolve_opencode)

_executor.py
  └── _config.py          (Config)

_board_store.py
  └── (无内部依赖)
```

### 6.2 外部依赖

#### 系统依赖

| 依赖 | 版本要求 | 用途 | 必需性 |
|------|----------|------|--------|
| Python | ≥ 3.8 | 核心脚本运行 | ✅ 必需 |
| bash | ≥ 3.0 | Shell 脚本 | ✅ 必需 |
| git | 任意 | 版本控制 | ✅ 必需 |
| launchd | macOS | 定时调度 | ✅ macOS 必需 |
| fcntl | - | 文件锁（Python 标准库） | ✅ 必需 |

#### 外部工具

| 工具 | 用途 | 必需性 |
|------|------|--------|
| opencode CLI | 代码执行器 | ✅ 必需 |
| claude CLI | product 角色 plan 生成 | ⚠️ 可选（有 fallback） |
| pytest | tester 角色测试 | ⚠️ 项目相关 |
| macOS Notification Center | 桌面通知 | ⚠️ macOS 可选 |

#### Python 标准库（无第三方依赖）

`os`, `sys`, `json`, `subprocess`, `asyncio`, `argparse`, `pathlib`, `dataclasses`, `datetime`, `tempfile`, `signal`, `re`, `time`, `http.server`, `urllib.parse`, `typing`

> **注意**: CCC 核心脚本完全基于 Python 标准库，无需 pip install 任何第三方包。

### 6.3 数据流依赖

```
用户输入
  ↓
backlog (task.jsonl)
  ↓ product 角色
plan.md + phases.json
  ↓ dev 角色
in_progress (task.jsonl) + .pid + .prompt.md
  ↓ opencode 执行
report.md + .done + .exitcode
  ↓ dev 角色
testing (task.jsonl)
  ↓ reviewer / tester 角色
verdict.md
  ↓ verified (task.jsonl)
  ↓ kb 角色
released (task.jsonl) + git tag + CHANGELOG
  ↓ regress 角色
backlog (回归 bug)
```

---

## 7. 项目运行方式

### 7.1 快速开始

```bash
# 1. 安装 7 个 launchd plist
bash scripts/install-ccc-roles.sh

# 2. 创建任务到 backlog
python3 scripts/ccc-board.py --batch <<EOF
{"action":"create","id":"my-first-task","title":"测试任务","description":"这是一个测试"}
EOF

# 3. 手动触发 product 角色拆解
python3 scripts/ccc-board.py product --promote my-first-task

# 4. 查看看板状态
python3 scripts/ccc-board.py index
```

### 7.2 7 角色自动运行

安装 launchd plist 后，7 个角色会按设定频率自动运行：

| 角色 | 频率 | launchd Label |
|------|------|---------------|
| product | 每 4 小时 | `com.ccc.product` |
| dev | 每 10 分钟 | `com.ccc.dev` |
| reviewer | 每 2 小时 | `com.ccc.reviewer` |
| tester | 每 4 小时 | `com.ccc.tester` |
| ops | 每 30 分钟 | `com.ccc.ops` |
| kb | 每天 23:00 | `com.ccc.kb` |
| regress | 每天 23:30 | `com.ccc.regress` |

### 7.3 手动运行单个角色

```bash
# 运行 product 角色
python3 scripts/ccc-board.py product

# 运行 dev 角色
python3 scripts/ccc-board.py dev

# 运行所有角色（顺序执行）
for role in product dev reviewer tester ops kb regress; do
  python3 scripts/ccc-board.py $role
done
```

### 7.4 启动看板 UI

```bash
# 启动 HTTP 服务（默认 http://127.0.0.1:7777）
python3 scripts/ccc-board-server.py

# 自定义端口
python3 scripts/ccc-board-server.py --port 8080
```

### 7.5 看板操作 CLI

```bash
# 查看看板状态
python3 scripts/ccc-board.py index

# 批量操作（从 stdin 读 JSONL）
python3 scripts/ccc-board.py --batch <<EOF
{"action":"create","id":"task-1","title":"新任务"}
{"action":"move","id":"task-1","from":"backlog","to":"planned"}
EOF

# 批量操作（从文件读）
python3 scripts/ccc-board.py --batch --file tasks.jsonl
```

### 7.6 CCC 初始化新项目

```bash
# 在新项目中初始化 .ccc/ 目录
python3 scripts/ccc-init.py /path/to/new-project
```

### 7.7 日志位置

```
~/.ccc/logs/
  ├── role-product-<timestamp>.log
  ├── role-dev-<timestamp>.log
  ├── role-reviewer-<timestamp>.log
  ├── role-tester-<timestamp>.log
  ├── role-ops-<timestamp>.log
  ├── role-kb-<timestamp>.log
  └── role-regress-<timestamp>.log

~/.ccc/opencode-pids/    # OpenCode 进程 PID
~/.ccc/alerts/           # 告警记录
```

---

## 8. 配置说明

### 8.1 环境变量配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `CCC_WORKSPACE` | CCC 根目录 | 工作区路径 |
| `CCC_TIMEOUT` | 600 | phase 默认超时（秒） |
| `CCC_HOOK_TIMEOUT` | 30 | 钩子超时（秒） |
| `CCC_MAX_RETRY` | 5 | 最大重试次数 |
| `CCC_STALE_HOURS` | 6 | 任务滞留阈值（小时） |
| `OPENCODE_MODEL` | `loop/flash` | 默认模型 |
| `OPENCODE_BIN` | 自动查找 | opencode 可执行文件路径 |
| `BOARD_HOST` | `127.0.0.1` | 看板服务地址 |
| `BOARD_PORT` | 7777 | 看板服务端口 |
| `AGENT_PLANNER_BASE_URL` | `http://127.0.0.1:4000` | Claude API 中转站 |

### 8.2 配置优先级

```
环境变量 > Config 类默认值
```

所有配置通过 `Config` 类统一管理，在 `__post_init__` 中读取环境变量覆盖默认值。

### 8.3 项目级配置

每个工作区的 `.ccc/` 目录下包含项目级配置：

| 文件 | 说明 |
|------|------|
| `profile.md` | 项目档案（技术栈、目录结构、规范） |
| `state.md` | 接力索引（最近任务、状态） |
| `AGENTS.md` | Agent 指南（项目专属规则） |
| `metrics.json` | 运行时指标 |

---

## 9. 测试体系

### 9.1 测试目录结构

```
tests/
├── scripts/                    # pytest 单元测试
│   ├── test_ccc_exec_commit_smoke.py
│   ├── test_ccc_exec_commit_idempotency.py
│   ├── test_ccc_exec_commit_jsonl_smoke.py
│   ├── test_ccc_init_search_smoke.py
│   ├── test_ccc_status_smoke.py
│   ├── test_bug_fixes_v012.py
│   ├── test_opencode_pool_max_parallel.py
│   ├── test_opencode_pool_kill_residual.py
│   └── test_opencode_watchdog_cleanup.py
└── e2e/
    └── test_pipeline_smoke.sh  # 完整流水线冒烟测试
```

### 9.2 运行测试

```bash
# 运行所有单元测试
python3 -m pytest tests/scripts/ -v

# 运行单个测试文件
python3 -m pytest tests/scripts/test_ccc_exec_commit_smoke.py -v

# 运行冒烟测试
bash tests/e2e/test_pipeline_smoke.sh
```

### 9.3 CI/CD

**配置文件**: [.github/workflows/ci.yml](file:///workspace/.github/workflows/ci.yml)

GitHub Actions 持续集成，确保代码质量。

---

## 10. 红线约束

**文件**: [red-lines.md](file:///workspace/references/red-lines.md)

CCC 系统有 20 条红线约束，违反任何一条即记 Critical 违规。

### 10.1 核心红线（必记）

| # | 红线 | 一句话 | 级别 |
|---|------|--------|------|
| 1 | 不动系统文件 | 不修改 /etc、~/.env、密钥等 | Critical |
| 2 | 验收必须可执行 | 自然语言 + 可选命令 | Warning |
| 3 | 不超出 plan 范围 | 白名单外不动 | Critical |
| 4 | 单 phase 单 commit | 不跨 phase、不攒 commit | Warning |
| 5 | phases.json 必写全 | 单 phase 也至少写 1 行 | Warning |
| 6 | 角色不互串 | product 不写代码，reviewer 不写 plan | Critical |
| 7 | 启动顺序固定 | 先读框架总纲，再读项目档案 | Info |
| 8 | 每步必 commit | 不攒改动 | Warning |
| 9 | Executor 卡死立即止损 | kill + 决策是否重试 | Warning |
| 10 | 禁止跨会话隐式记忆 | 所有状态落文件 | Critical |
| **11** | Verdict 必须有文件 | 口头 PASS 不算 PASS | **Critical** |
| **12** | 禁止 agent 自主启用 CCC | 用户显式触发 | **Critical** |
| 13 | 禁止未使用路线代码 | 死代码必须删 | Warning |
| X1 | OpenCode 最多 3 并发 | 内存敏感，硬约束 | Warning |
| X2 | 每 phase 必杀 opencode | 防止残留进程 | Critical |
| X3 | 启动前必跑 watchdog | 残留扫描，开机自检 | Critical |
| **X4** | 每 phase 必走看板流转 | 不可跳列 | **Critical** |
| X5 | 7 角色 plist 必装 | 缺一个 = 流程断链 | Critical |
| X6 | 角色频率不许改 | 频率 = 老板拍板 | Critical |

### 10.2 OpenCode 进程管理红线（X1-X3）

- **X1**: 全局 opencode 进程 ≤ 3（`opencode-pool.py` 硬限制）
- **X2**: 每个 phase 结束必杀进程（先 TERM，5s 后 KILL，进程组级联）
- **X3**: 启动前必须跑 `opencode-watchdog.sh` 扫描残留

### 10.3 看板系统红线（X4-X6）

- **X4**: 任务必须逐列流转，不可跳列
- **X5**: 7 个 launchd plist 必须全部安装
- **X6**: 角色执行频率不可随意修改

---

## 附录

### A. 常用命令速查

```bash
# 看板状态
python3 scripts/ccc-board.py index

# 手动跑某角色
python3 scripts/ccc-board.py dev

# 拆解任务
python3 scripts/ccc-board.py product --promote <task_id>

# 看板 UI
python3 scripts/ccc-board-server.py

# 查看时间线
python3 scripts/ccc-board.py timeline

# 审批 AGENTS 建议
python3 scripts/ccc-board.py approve-agents
```

### B. 文件契约速查

```
<workspace>/.ccc/
├── profile.md              # 项目档案
├── state.md                # 接力索引
├── plans/<task>.plan.md    # 执行计划
├── phases/<task>.phases.json  # 阶段计划
├── reports/<task>.report.md   # 执行报告
├── verdicts/<task>.verdict.md # 验收结论
└── board/                  # 看板（JSONL 文件）
    ├── backlog/
    ├── planned/
    ├── in_progress/
    ├── testing/
    ├── verified/
    ├── released/
    ├── abnormal/
    ├── events/             # 事件历史
    └── index.json          # 状态总览
```

### C. 相关文档索引

| 文档 | 路径 | 受众 |
|------|------|------|
| 启动必读 | [STARTUP-BRIEF.md](file:///workspace/STARTUP-BRIEF.md) | 所有 Agent |
| 红线清单 | [references/red-lines.md](file:///workspace/references/red-lines.md) | 所有角色 |
| 架构说明 | [docs/architecture.md](file:///workspace/docs/architecture.md) | 维护者 |
| 战略地图 | [docs/STRATEGY-MAP.md](file:///workspace/docs/STRATEGY-MAP.md) | 产品/架构 |
| 教训沉淀 | [docs/lessons.md](file:///workspace/docs/lessons.md) | 所有角色 |
| 路线图 | [docs/roadmap.md](file:///workspace/docs/roadmap.md) | 维护者 |
| Plan 规范 | [docs/plan-spec.md](file:///workspace/docs/plan-spec.md) | product |
| 验证规范 | [docs/verification-spec.md](file:///workspace/docs/verification-spec.md) | reviewer/tester |
| 任务格式标准 | [references/board-task-schema.md](file:///workspace/references/board-task-schema.md) | 集成者 |
| Skills 索引 | [skills/README.md](file:///workspace/skills/README.md) | 所有角色 |

---

*本文档基于 CCC v0.20.0 生成，最后更新于 2026-07-09。*
