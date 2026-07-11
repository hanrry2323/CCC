# CCC — Connect–Claude Code

> **框架总纲**（架构 / 红线 / 工程纪律）。本文件不面向 agent，是面向维护者的总览。
> agent 只需要读 `SKILL.md` + 对应角色 `skills/ccc-<role>/SKILL.md`。

---

## 名字含义

**C**onnect — **C**laude **C**ode

CCC 把 Claude Code 的执行能力**连接到任何 IDE 工具**。它：
- 是一个 **SKILL 资产套件**（`SKILL.md` + 7 角色 `skills/`），不是 framework 代码库
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

**R 系列**（v0.24.5+ 起 alias）：R-04 reviewer 强制参与 / R-07 phases.json 原子写 / R-08 日志统一 logger / R-09 认证 GET 路径 / R-12 强制人工介入（fallback quarantine）/ R-14 audit 子进程 timeout。R- 与 X- 编号并存，详见 `references/red-lines.md`。

**X 系列**：X1 OpenCode ≤3 并发 / X2 每 phase 必杀 opencode / X3 启动前 watchdog / X4 看板流转 / X5 Engine+board-server plist 必装 / X6 角色频率（v0.20.1 起不再适用，保留索引）

**Lesson 27**: `claude -p` 是 print 模式开关，prompt 必须走 stdin。

**Lesson 28**: Verdict 强证据红线 11 的来历。

---

## 关键资产清单

| 路径 | 角色 |
|------|------|
| `SKILL.md` | 唯一注入 prompt（agent 启动时自动加载） |
| `skills/ccc-<role>/SKILL.md` × 7 | 各角色 skill 定义 |
| `references/red-lines.md` | 12+X6 红线强约束 |
| `references/board-task-schema.md` | task JSONL 格式标准（v0.19 新增，CCC-QXO 共享契约） |
| `scripts/_config.py` | 集中配置（v0.19 新增） |
| `scripts/_board_store.py` | 看板存储抽象 FileBoardStore（v0.19 新增） |
| `scripts/_executor.py` | 执行器抽象 OpenCodeExecutor（v0.19 新增） |
| `scripts/ccc-board.py` | 7 角色看板核心 |
| `scripts/ccc-engine.sh` | CCC Engine launchd 入口 (v0.20.1) |
| `scripts/ccc-board-server.py` | 看板 HTTP 服务 |
| `scripts/ccc-engine.py` | CCC Engine 串行执行主循环 (v0.20.1) |
| `scripts/ccc-engine.sh` | Engine launchd 入口 |
| `scripts/opencode-exec.py` | OpenCode CLI 执行器 |
| `scripts/opencode-pool.py` | 进程池（max 3 并发） |
| `scripts/opencode-watchdog.sh` | 残留扫描 |
| `scripts/ccc-notify.sh` | macOS 桌面通知 |
| `scripts/ccc-exec-launcher.sh` | 单 phase 启动入口 |
| `scripts/ccc-exec-commit.sh` | 单 phase 单 commit |
| `scripts/ccc-hook.sh` | 通用钩子执行器 |
| `templates/` | plan/phases/report/verdict/AGENTS 模板 |
| `tests/scripts/` | pytest 核心测试 |
| `tests/e2e/` | E2E 集成测试（v0.19 新增） |
| `.ccc/profile.md` + `.ccc/state.md` | 项目档案 + 接力索引 |
| `docs/lessons.md` | 历史教训沉淀 |
| `docs/roadmap.md` | 路线图 |
| `CHANGELOG.md` | 版本变更 |

> `ccc-precheck.sh` / `ccc-finish.sh` 已移除（不再使用）

---

## 7 角色系统 + CCC Engine（v0.20.1 架构）

**v0.18 起不再支持旧 3 角色（Plan/Exec/Verify）流程。**
**v0.20.1 起取消 7 角色定时轮询，改为 CCC Engine 串行驱动。**

### 引擎架构

```
launchd → com.ccc.engine (KeepAlive, 常驻)
  └─ ccc-engine.py 主循环:
       loop:
         in_progress 有 task 在跑?
           → 检查 .done 完成 → 立即跑 reviewer+tester+kb
         planned 有 task?
           → 启 opencode（不走定时器，即刻执行）
         无事 → sleep 5s
```

### v0.24+ Phase 感知追加

Engine 主循环对当前 task 读 `<task>.phases.json`（JSONL, schema_version="1.1"），
按 phase 边界调度：

```
phases.json → _resolve_phase_dependencies()
  → 分类 executable / blocked / skipped 三态
  → executable phase 进入 _current_running_phase()
  → dev_role_launch / dev_role_relaunch / dev_role_check_complete
  → phase all_terminal → reviewer_role (advisory lock + fallback quarantine)
  → phase all_verified → kb_role
```

失败传染：`_check_phase_failures()` 检测 phase 失败 → 标记 phase failed → 跳过依赖它的后续 phase → task 全 phase failed 时 Engine 移 abnormal。

### 角色映射（Engine 内部串行调用）

| 角色 | Engine 触发方式 | 看板列 |
|------|----------------|--------|
| product | 手动 `--promote`（无变更） | backlog → planned |
| dev | Engine 自动串行（无定时） | planned → in_progress → testing |
| reviewer | Engine 在 dev 完成后立即调 | testing → verified |
| tester | Engine 在 dev 完成后立即调 | testing → verified |
| ops | Engine 空闲时运行轻度检查 | 所有列（非阻塞） |
| kb | Engine 在 reviewer+tester 通过后立即调 | verified → released |
| regress | 保留独立定时（23:30）或嵌在 Engine 内 | released → backlog |

**Engine + board-server 装上** = `bash scripts/install-ccc-roles.sh`（红线 X5）。

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
| 大（多阶段 / 需完整看板） | CCC skill 启用，全链跑 | CCC Engine 自动串行 |

**红线 12**：agent 不自主启用 CCC。用户显式触发。

---

## 4 文件契约路径

```
<workspace>/.ccc/
├── profile.md              # 项目档案（首次接入生成）
├── plans/<task>.plan.md    # product 产出
├── phases/<task>.phases.json  # product 产出（JSONL, schema_version="1.1"，支持 depends_on）
├── reports/<task>.report.md   # dev 产出
├── reviews/<task>.review.md   # reviewer 产出（v0.24.5+）
├── verdicts/<task>.verdict.md # reviewer/tester 产出（≥3 probes）
├── review-locks/<task>.lock   # reviewer per-task advisory lock（v0.24.5+）
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

## 角色入口架构（v0.20.1）

```
launchd plist (com.ccc.engine, KeepAlive)
  → scripts/ccc-engine.sh
      → python3 scripts/ccc-engine.py --workspace <path>
          └→ ccc-board.py 角色函数:
              dev_role_launch() / reviewer_role() / tester_role() / kb_role()
```

**v0.19 架构升级**：`ccc-board.py` 内部依赖三层抽象：

```
ccc-board.py → _config.py (配置) + _board_store.py (存储) + _executor.py (执行)
```

所有存储操作收口到 `FileBoardStore`，执行操作收口到 `OpenCodeExecutor`。

---

## 默认预算

| 类型 | Phase 数 | USD |
|------|---------|-----|
| 调研 / 审计 | 6 | 200 |
| 修复 / 重构 | 1-3 | 30-50 |
| 简单文件操作 | 1 | 20 |
| push / 部署 | 1 | 5-30 |

---

## 与 qxo 的关系（独立发展，共享契约）

CCC 与 QXO **独立发展，不互相依赖**。

- **CCC** 做"极简的 Prompt 资产"——CCC Engine + 看板流水线，SKILL.md + 脚本，不绑任何项目。
- **QXO** 做"可扩展的 AI 中台"——FastAPI + React + Tauri，LoopEngine + EventBus。

两者互通通过 `references/board-task-schema.md` 定义的 task JSONL 格式实现：
- QXO 可按标准格式往 `backlog/` 写入任务
- CCC 产出的 report / verdict 也可被 QXO 读取

v0.5 起 CCC 与 qxo 代码解耦，v0.19 完成**存储抽象 + 共享契约**的正式定义。

---

## 版本

```
cat ~/program/CCC/VERSION
```

详细历史见 `CHANGELOG.md`。当前：`v0.24.7`（v0.25.0 release commit 10 同步）。
