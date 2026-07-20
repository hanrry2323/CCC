# CCC Profile — CCC (Connect–Claude Code) 本体项目

> 任务启动时 **强制先读本文件**（红线 7：启动顺序固定，profile.md 第一），再读 `.ccc/state.md`。

## 项目元信息

- **项目根**: `/Users/apple/program/CCC`
- **仓库**: CCC 本体（Hub + Engine + Skill 资产）
- **分支**: main
- **当前版本**: 见根目录 `VERSION`（**v0.52.0 Hub-Shell Wave1-2 freeze**）
- **舰队手册**: `docs/milestones/m1-ten-workspaces.md` · 卫生命令 `scripts/ccc-workspace-doctor.py`
- **语言/技术栈**: Python 3.11+（Engine / Hub / Board）+ Bash 脚本 + 前端 SPA（`scripts/chat_server/`）

## 项目定位

CCC = **Loop Engineer**：人定意图（Hub），系统自动编排与自主执行（Engine）。

- **Hub**（`:7777`）是入口：对齐 → 定稿 → 转任务（写入 **epic** 到 `backlog`）
- **Engine**（`com.ccc.engine`）串行消费：product 扇出 work → dev → reviewer/tester → kb
- **Skill + Prompt = 本次角色**（阶段能力包，不是给用户点选的「7 角色超市」）

叙事 SSOT：`docs/VISION.md` · 启动：`STARTUP-BRIEF.md` · 协议：`SKILL.md` / `CLAUDE.md`

## 关键资产清单

| 路径 | 角色 |
|------|------|
| `SKILL.md` / `CLAUDE.md` | 协议与 Claude 认知（Hub 注入 CLAUDE.md） |
| `docs/VISION.md` | 产品叙事 SSOT |
| `docs/architecture-core.md` | Engine/Board 分层与维护热点 |
| `references/red-lines.md` | 红线强约束 |
| `references/board-task-schema.md` | epic/work + 五态契约 |
| `scripts/ccc-engine.py` | **调度面**：Loop 主循环（维护热点；运行时见 `scripts/engine/`） |
| `scripts/board/roles/` | **角色实现面**：product/dev/reviewer/…（新逻辑落这里） |
| `scripts/ccc-board.py` | 兼容入口：CLI + 再导出（勿新增长角色逻辑） |
| `scripts/board/` | context / phase / store / slots 拆包 |
| `scripts/ccc-board-server.py` | 看板 HTTP（`:7775`） |
| `scripts/ccc-chat-server.py` → `scripts/chat_server/` | Hub SPA |
| `scripts/_product_fanout.py` | Claude 扇出 work |
| `scripts/_workspace_isolation.py` | 看板仓 ↔ 编排仓隔离 |
| `scripts/opencode-exec.py` | OpenCode 执行器（强制 `--dir`） |
| `skills/ccc-*/` | 阶段能力包 |
| `templates/` | plan/phases/report/verdict/AGENTS 模板 |
| `tests/scripts/` | pytest 核心测试 |
| `.ccc/profile.md` + `.ccc/state.md` | 本档案 + 接力索引（红线 7+10） |

### 改哪里（一句话）

- 改**角色行为** → `scripts/board/roles/`
- 改**调度 / tick / hang / slot** → `scripts/ccc-engine.py` 或 `scripts/engine/`
- 改**看板 HTTP** → `ccc-board-server.py`；改 **Hub UI** → `chat_server/frontend/`

## 看板语义（现行）

```
Hub 定稿 → backlog(epic 常驻)
  → product 扇出 → planned(work×N)
  → Engine 只调度 work → … → released
  → 子卡全 released → epic split_status=done 沉底
```

| 字段 | 含义 |
|------|------|
| `card_kind` | `epic`（待办大卡）/ `work`（流转小卡） |
| `split_status` | 五态：`pending` → `planned` → `running` → `done`；任子卡 abnormal → `failed` |
| 列 | backlog / planned / in_progress / testing / verified / released / abnormal |

## 4 文件契约路径

```
.ccc/
├── profile.md              # 本文件
├── state.md                # 接力索引（红线 10）
├── plans/<task>.plan.md
├── phases/<task>.phases.json
├── reports/<task>.report.md
├── verdicts/<task>.verdict.md  # 红线 11 强证据
└── board/                  # 七列 JSONL
```

## 已知约束

- **绝不动**: `/etc/*`, `~/.env`, `~/.aws/*`（红线 1）
- **必须走 .ccc/**: plan/report/verdict 必须在目标仓 `.ccc/` 内；**git commit 必须在任务 `--dir` 仓**（仓隔离）
- **commit 规则**: 单 phase 单 commit（红线 4 + 8）；message 含 task_id
- **卡死止损**: kill + 下一阶段/角色接管（红线 9）
- **阶段不互串**: product 不写业务代码；reviewer 不写 plan（红线 6）
- **不自主启用 CCC**: 用户显式触发（红线 12）
- **Hub 对齐基线**：`state.md` 最近任务可能滞后；必须交叉 `git log` + control（invent 硬关 / queue-only）。空板 + invent 关 ≠ 应降控制面；禁止建议 ui/disabled/关机（除非用户问闲置）

## 工具链版本

- Python 3.11+
- Bash / zsh
- Claude Code CLI（Hub 对话）+ OpenCode（Engine 执行）

## 工程纪律（适用本项目）

1. 不写假报告 — VERDICT 段必须引用真 verdict.md
2. 不口头 PASS — verdict.md 真文件存在才算 PASS（红线 11）
3. 不跨会话隐式记忆 — 必落文件（红线 10）
4. 不自主启用 CCC — 用户显式触发（红线 12）
