# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# CCC — Connect–Claude Code · Loop Engineer

> **人定意图，系统自动编排与自主执行。** 对话面（M1 Desktop + sidecar + loop-code）产 epic；编排面（Mac2017 Engine：Claude Code 扇出 + OpenCode 写码）远端开发；中间只交信息流。  
> 边界基线：`docs/product/dialogue-orchestration-boundary.md` · 叙事：`docs/VISION.md` · 启动：`STARTUP-BRIEF.md` · 版本：`VERSION`（**v0.52.1**）

**控制面**: `~/.ccc/control.json`（`disabled` | `ui` | `enabled` | `invent`）

**勿再对用户说**：接很多 IDE 当卖点；让用户先选固定角色。

---

## Hub Agent 基线硬规则（对齐基线 / 定方案时强制）

1. **控制面读完整 policy**：不只看 `mode`；必须核对 `invent_hard_disabled` / `queue_consumer_only` / `engine_allowed`。`enabled` + invent 硬关 = Engine **只消费队列**，看板空时闲置是正常，不是「等开工」。
2. **`git log -5` × 目录交叉验证**：`state.md`「最近任务」可能滞后；HEAD 有重构时回头看 `scripts/board/roles/`、`scripts/engine/` 是否已存在。
3. **热路径（CCC 本体）**：调度 → `scripts/ccc-engine.py` + `scripts/engine/`；角色 → `scripts/board/roles/`；兼容入口 → `scripts/ccc-board.py`（勿新增长逻辑）。`app/` `lib/` `db/` 是浅层附属，**不要**说成主架构。
4. **版本 SSOT**：`VERSION` > `CHANGELOG` 最新节 > README badge；不一致只报「对齐版本」类小任务。
5. **禁止越界建议**：非用户主动问闲置/省资源时，**禁止**建议降控制面到 `ui`/`disabled` 或关机。
6. **调度就绪度口径（v0.51）**：空板 + invent 硬关 → Engine **闲置正常**。新工作经 Hub 选 **业务仓** 定稿→下达；**禁止**对 CCC orch 写 epic / 投 backlog（R-15）。**不可**声称可无人值守 invent（红线 12）。
7. **业务仓迁移 / 接入 / Desktop 开项目对话**：搬完文件 ≠ 完成。强制读并执行 [`docs/product/desktop-agent-handoff.md`](docs/product/desktop-agent-handoff.md)（详步骤 [`docs/runbooks/app-migrate-register-desktop.md`](docs/runbooks/app-migrate-register-desktop.md)）：2017 `apps/<name>` → `ccc-init --register` → M1 `localWorkspaceMap` → 点项目卡进 `{id}::main`。

架构细节：`docs/architecture-core.md` · 运维页：Hub `#/ops`。

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
Hub（定稿→epic）→ backlog(大卡常驻)
  → Claude product 扇出 → planned(work×N)；epic split_status=planned
  → Engine：dev(opencode --dir) → testing → reviewer+tester → verified → kb → released
  → 全部子卡 released → epic split_status=done 沉底
  → 任子卡 abnormal → epic split_status=failed（仍留 backlog，需人处理）
```

> 「product/dev/…」= **阶段默认 Skill 包**，不是给用户点选的角色列表。见 `docs/VISION.md`。

| 阶段 | Engine 触发 | 看板列 |
|------|-------------|--------|
| product | pending epic；Claude 扇出 | 创建 planned(work)；**epic 留 backlog** |
| dev | 只调度 work | planned → in_progress → testing |
| reviewer | testing 门禁（verdict.md） | testing → verified |
| tester | testing 门禁 | testing → verified |
| ops | 手动/可选 | 非阻塞 |
| kb | verified 非空 | verified → released |
| regress | 23:30 / 手动 | released → backlog(epic) |

**epic `split_status` 五态**：`pending` → `planned` → `running` → `done`；`failed`（子卡 abnormal）。兼容别名 `active`→`running`、`blocked`→`failed`。

### 控制面状态机（v0.39+）

`~/.ccc/control.json` 是全局开关（SSOT）：

| 模式 | Engine | 自造任务 | 用途 |
|------|--------|----------|------|
| `disabled` | 关 | 否 | 默认，完全离线 |
| `ui` | 关 | 否 | 前端开发 |
| `enabled` | 只消费 **app** 队列 | 否 | 日常生产（CCC orch 不在消费名单） |
| `invent` | **已退役** | 否 | `invent_hard_disabled=true`；勿启用（历史模式名仍可能出现在 JSON） |

```
bash scripts/ccc-autostart-guard.sh enable --start
```

### 入口架构

```
launchd(com.ccc.engine) → ccc-engine.sh → ccc-engine.py
  └→ board.roles（product/dev/reviewer/…）+ board.phase
  └→ engine/{slots,active_tasks,hang,gates}
  └→ 三层抽象：_config.py → _board_store.py(FileBoardStore) → _executor.py(OpenCodeExecutor)
  └→ ccc-board.py = CLI / 兼容再导出（勿新增长角色逻辑）
```

### 前端 SPA 架构（v0.38+ 模块化重构；架构对齐 2026-07-19）

**入口** → `http://localhost:7777` → `scripts/ccc-chat-server.py` → `scripts/chat_server/`

```
scripts/chat_server/            # FastAPI 模块化后端
├── app.py                      # FastAPI 工厂（CORS + Static + 路由）
├── config.py                   # HOST/PORT/AUTH/PROXY/BOARD_URL 配置
├── auth.py                     # Basic Auth
├── models.py                   # 数据模型
├── routers/                    # API 路由
│   ├── desktop.py              #   Desktop 专用：transfer / flow / threads（M1 主路径）
│   ├── board.py                #   看板代理 → Board API(:7775)
│   ├── ops.py                  #   运维聚合
│   ├── projects.py             #   项目列表
│   ├── sessions.py             #   历史会话（兼容）
│   └── files.py                #   文件附件
├── services/                   # 业务逻辑
│   ├── claude_client.py        #   claude CLI 子进程（M1 sidecar 用，Hub 不再用）
│   ├── board_client.py         #   Board API HTTP 客户端
│   └── session_store.py        #   会话持久化
└── frontend/                   # SPA 前端（hash 路由；运维/兼容，非产品主入口）
    ├── index.html              # SPA 壳
    ├── css/                    # 样式
    └── js/
        ├── router.js           # #/board | #/console | #/ops（#/chat 已删）
        ├── app.js              # 主应用
        ├── state.js            # 全局状态
        ├── api.js              # API 客户端
        ├── components/         # UI 组件
        └── pages/              # boardPage / consolePage / opsPage
```

**架构对齐**：对话主入口 = **M1 Desktop + sidecar `:7788` + arm64 loop-code**；Hub `/api/chat` 路由已删；网页 SPA 仅运维/兼容（看板/运维已迁入 Desktop）。

| 端口 | 服务 | 说明 |
|------|------|------|
| 7788 | CCC Agent Sidecar | **M1 对话热路径**（Desktop → sidecar → loop-code → MiniMax） |
| 7777 | CCC Hub | API host：transfer / flow / board / ops（Mac2017） |
| 7775 | Board API | 看板 REST（仅 127.0.0.1，Hub 反代） |
| 7778 | CCC Cockpit | **deprecated** → Hub `#/ops` → Desktop 运维 |

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
| `scripts/ccc-engine.py` | Engine 主循环（调度面） |
| `scripts/engine/` | slot / active_tasks / hang / gates |
| `scripts/board/roles/` | 角色实现（product/dev/…） |
| `scripts/ccc-board.py` | CLI + 再导出（兼容层） |
| `scripts/_ccc_control.py` | 控制面状态机（~/.ccc/control.json） |
| `scripts/_board_store.py` | FileBoardStore 看板存储抽象 |
| `scripts/_executor.py` | OpenCodeExecutor 执行器 |
| `scripts/_failure_ledger.py` | 失败账本（failures.jsonl） |
| `scripts/_claude_cli.py` | claude CLI 运行时路径解析 |
| `scripts/_config.py` | 集中配置（Config dataclass） |
| `scripts/ccc-chat-server.py` | CCC Hub 后端（Chat + Board 代理） |
| `scripts/ccc-board-server.py` | 看板 HTTP 服务 |
| `scripts/ccc-autostart-guard.sh` | 控制面 CLI |
| `scripts/ccc-failure-report.py` | 失败报告 CLI |
| `references/red-lines.md` | 18 红线 + X 系列(8) + R 系列(7) |
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

| 通道 | 用途 | 上游（直连） |
|------|------|--------------|
| Claude / loop-code | 对话 + product/reviewer | **MiniMax** `https://api.minimaxi.com/anthropic`（`MiniMax-M3`） |
| OpenCode | 后台写码（dev） | **讯飞** `xfyun/code`（`~/.config/opencode`）；备用智谱 `zhipu/flash` |

逻辑名 `flash`/`code` 在直连 MiniMax 时由 `_claude_cli.resolve_anthropic_model` 映射为 `MiniMax-M3`。  
~~ai-loop-router `:4000/:4002` 已退役。~~ 详见 `docs/deploy/topology.md` · `docs/executors/overview.md`。

---

## 与 qxo 的关系

独立发展、共享 `board-task-schema.md` 定义的 task JSONL 契约。
CCC 不依赖 QXO 代码，QXO 可写标准 backlog 投递。
