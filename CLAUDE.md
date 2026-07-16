# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# CCC — Connect–Claude Code · Loop Engineer

> **人定意图，系统自动编排与自主执行。** Hub 是入口；任务路由工具；Skill+Prompt = 无穷角色。  
> 叙事 SSOT：`docs/VISION.md` · 启动：`STARTUP-BRIEF.md` · 版本：根目录 `VERSION`

**控制面**: `~/.ccc/control.json`（`disabled` | `ui` | `enabled` | `invent`）

**勿再对用户说**：接很多 IDE 当卖点；让用户先选固定角色。

---

## 开发命令

```bash
# Python 语法检查（必做，所有 scripts/*.py）
python -m py_compile scripts/ccc-engine.py

# Shell 语法检查（所有 *.sh）
bash -n scripts/ccc-autostart-guard.sh

# 单测（核心测试，464 case）
pytest tests/scripts/ -q --tb=short

# 单文件测试
pytest tests/scripts/test_board_store.py -v --tb=short

# 单用例（-k 支持 name 匹配）
pytest tests/scripts/test_engine.py -v -k test_phase_dependencies

# Ruff lint（CI 级）
ruff check scripts/ tests/

# E2E 集成测试
bash tests/e2e/test_pipeline_smoke.sh      # 基础流水线烟测
bash tests/e2e/test_green_pipeline_e2e.sh  # 绿通 mock 流水线
bash tests/e2e/test_f1_backlog_failover.sh # 失败计数器 + quarantine

# 自检（完整语法 + 安全扫描，提交前跑）
bash scripts/ccc-self-check.sh

# 看板状态
python3 scripts/ccc-board.py index

# 失败报告（上一笔失败）
python3 scripts/ccc-failure-report.py --last 1

# 引擎状态
bash scripts/ccc-autostart-guard.sh status

# 前端开发模式（前台 Hub + Board，不碰 launchd）
bash scripts/ccc-hub-dev.sh
```

---

## 架构概要

### Loop：Hub → Engine → 阶段能力包 → 执行器

```
Hub（定稿/转任务）→ Board
  → Engine 串行：product → planned → dev(opencode) → testing
       → reviewer+tester → verified → kb → released
```

> 「product/dev/…」= **阶段默认 Skill 包**，不是给用户点选的角色列表。见 `docs/VISION.md`。

| 阶段 | Engine 触发 | 看板列 |
|------|-------------|--------|
| product | backlog 非空；或已挂 plan 则跳过 | backlog → planned |
| dev | 串行多 phase | planned → in_progress → testing |
| reviewer | testing 门禁（verdict.md） | testing → verified |
| tester | testing 门禁 | testing → verified |
| ops | 手动/可选 | 非阻塞 |
| kb | verified 非空 | verified → released |
| regress | 23:30 / 手动 | released → backlog |

### 控制面状态机（v0.39+）

`~/.ccc/control.json` 是全局开关（SSOT）：

| 模式 | Engine | 自造任务 | 用途 |
|------|--------|----------|------|
| `disabled` | 关 | 否 | 默认，完全离线 |
| `ui` | 关 | 否 | 前端开发 |
| `enabled` | 队列消费者 | 否 | 日常生产 |
| `invent` | 全开 | 是 | 自造 evolve/audit |

```
bash scripts/ccc-autostart-guard.sh enable --start
```

### 入口架构

```
launchd(com.ccc.engine) → ccc-engine.sh → ccc-engine.py
  └→ ccc-board.py 角色函数（dev/reviewer/tester/kb）
  └→ 三层抽象：_config.py → _board_store.py(FileBoardStore) → _executor.py(OpenCodeExecutor)
```

### 前端 SPA 架构（v0.38+ 模块化重构）

**入口** → `http://localhost:7777` → `scripts/ccc-chat-server.py` → `scripts/chat_server/`

```
scripts/chat_server/            # FastAPI 模块化后端
├── app.py                      # FastAPI 工厂（CORS + Static + 5 路由）
├── config.py                   # HOST/PORT/AUTH/PROXY/BOARD_URL 配置
├── auth.py                     # Basic Auth
├── models.py                   # 数据模型
├── routers/                    # API 路由
│   ├── chat.py                 #   对话 SSE + 执行
│   ├── board.py                #   看板代理 → Board API(:7775)
│   ├── projects.py             #   项目列表
│   ├── sessions.py             #   历史会话
│   └── files.py                #   文件附件
├── services/                   # 业务逻辑
│   ├── claude_client.py        #   claude CLI 子进程
│   ├── board_client.py         #   Board API HTTP 客户端
│   └── session_store.py        #   会话持久化
└── frontend/                   # SPA 前端（hash 路由）
    ├── index.html              # SPA 壳
    ├── css/                    # 样式（5 个文件：variables/base/themes/components/shell）
    └── js/
        ├── router.js           # #/chat | #/board | #/console
        ├── app.js              # 主应用（tab 管理 + 事件）
        ├── state.js            # 全局状态
        ├── api.js              # API 客户端
        ├── components/         # 14 个 UI 组件
        └── pages/              # 页面（boardPage.js / consolePage.js）
```

| 端口 | 服务 | 说明 |
|------|------|------|
| 7777 | CCC Hub | SPA 前端（默认 `#/chat` 对话页） |
| 7775 | Board API | 看板 REST（仅 127.0.0.1，Hub 反代） |
| 7778 | CCC Cockpit | 可选旧总控（Cockpit，非 SPA） |

`scripts/ccc-board-ui/` 仅含跳转页 → Hub :7777（已废弃）。

---

## 看板 4 文件契约

```
<workspace>/.ccc/
├── profile.md                  # 项目档案（首次接入生成）
├── state.md                    # 接力索引
├── board/                      # 看板文件
│   ├── backlog/ / planned/ / in_progress/ / testing/ / verified/ / released/
│   └── index.json
├── plans/<tid>.plan.md         # product 产出
├── phases/<tid>.phases.json    # product 产出（JSONL, schema_version="1.1"）
├── reports/<tid>.report.md     # dev 产出
├── reports/<tid>.review.md     # reviewer 产出
├── verdicts/<tid>.verdict.md   # reviewer/tester 产出（≥3 probes）
├── review-locks/<tid>.lock     # reviewer per-task advisory lock
├── stats/                      # 可观测性
│   ├── events.jsonl            # 事件流
│   ├── failures.jsonl          # 失败账本（v0.40+）
│   ├── summary.json            # 聚合
│   └── upstream-probe.jsonl    # upstream 探针（v0.40.1+）
└── quarantines/<tid>/          # 归档包 + reason.txt
```

---

## 关键资产

| 路径 | 角色 |
|------|------|
| `SKILL.md` | 注入 prompt 总纲（agent 启动时自动加载） |
| `skills/ccc-<role>/SKILL.md` × 7 | 各角色 skill 定义 |
| `scripts/ccc-engine.py` | Engine 串行执行主循环 |
| `scripts/ccc-board.py` | 看板与阶段能力调度 |
| `scripts/_ccc_control.py` | 控制面状态机（~/.ccc/control.json） |
| `scripts/_board_store.py` | FileBoardStore 看板存储抽象 |
| `scripts/_executor.py` | OpenCodeExecutor 执行器 |
| `scripts/_failure_ledger.py` | 失败账本（failures.jsonl） |
| `scripts/_claude_cli.py` | claude CLI 运行时路径解析 |
| `scripts/_config.py` | 集中配置（Config dataclass） |
| `scripts/ccc-chat-server.py` | CCC Hub 后端（Chat + Board 代理） |
| `scripts/ccc-board-server.py` | 看板 HTTP 服务 |
| `scripts/ccc-cockpit.py` | 旧总控（可选） |
| `scripts/ccc-autostart-guard.sh` | 控制面 CLI |
| `scripts/ccc-failure-report.py` | 失败报告 CLI |
| `references/red-lines.md` | 12 红线 + X 系列 |
| `references/board-task-schema.md` | Board Protocol v1（跨 IDE 契约） |
| `docs/CONTROL.md` | 控制面文档 |
| `docs/observability.md` | 可观测性 / 埋点文档 |
| `docs/STRATEGY-MAP.md` | 战略地图（角色启动必读） |
| `templates/` | plan/phases/report/verdict/AGENTS 模板 |

---

## 工程红线（摘要）

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
| **11** | Verdict 必须写 verdict 文件 | 口头 PASS 不算（Lesson 28） |
| **12** | 禁止 agent 自主启用 CCC | 用户显式触发 |

完整版含 R-/X- 别名 → `references/red-lines.md`。

---

## 模型通道

| 通道 | 用途 | 模型 |
|------|------|------|
| `flash` | 主会话交互 | MiniMax-M3 等（:4000 中转站） |
| `code` | 后台自动任务（dev/opencode） | 讯飞 astron-code / DeepSeek（:4002） |

子进程统一 `--model flash`（wrapper 入口统一），详见 `docs/model-tier-strategy.md`。

---

## 与 qxo 的关系

独立发展、共享 `board-task-schema.md` 定义的 task JSONL 契约。
CCC 不依赖 QXO 代码，QXO 可写标准 backlog 投递。
