# CCC — 框架说明书

> 本文件解释 CCC v0.51.0 的架构。面向维护者，agent 不读本文件。
> 核心调度细节见 [`docs/architecture-core.md`](architecture-core.md)。

---

## 一句话定义

**CCC = Loop Engineer**（人定意图，系统自动编排与自主执行）。
三层架构：**Desktop**（SwiftUI 三栏）+ **Engine+Board**（Python 单进程串行调度 + JSONL 看板）+ **Executors**（OpenCode / Claude CLI 扇出）。

Skill + Prompt = 本次角色（无穷角色，非固定 7 个）；用户不选角色、不背 Skill。

---

## 概念模型（v0.20.1 起：单进程串行调度，已废弃 launchd 多角色并行）

```
Desktop (SwiftUI 三栏)
  │  产 epic → 写入 backlog
  ▼
ccc-engine.py (单进程主循环，launchd KeepAlive 拉起)
  │
  ├─ tick: 扫 board → 推进 backlog → planned → in_progress → testing → verified → released
  ├─ slot: MAX_CONCURRENT 并行 opencode 执行（engine/slots.py）
  ├─ hang/gates: 卡死检测 + 门禁（reviewer/tester 双门禁）
  └─ 角色实现: scripts/board/roles/{product,dev,reviewer,tester,ops,kb,regress}.py
                + audit (skills/ccc-audit/SKILL.md, 待补实现)
  │
  ▼
FileBoardStore (.ccc/board/<col>/<task>.jsonl + index.json, fcntl.flock)
  │
  ▼
Hub :7777 (chat_server, FastAPI) → Board API :7775 (ccc-board-server)
  │
  ▼
patrol-v4 (独立运维探针，每 N min 巡检存活 + 卡死 + index 一致性)

控制面: ~/.ccc/control.json
  disabled | ui | enabled | invent
  (invent 自 v0.42.3 起 INVENT_HARD_DISABLED=True, 仅作历史档位保留)
```

---

## 物理形态

```
~/program/CCC/                                  # 本目录（唯一交付物）
├── SKILL.md                                    # ★ 注入 prompt 总纲
├── skills/                                     # ★ 角色 skill 定义（7+1: product/dev/reviewer/tester/ops/kb/regress + audit）
│   ├── README.md
│   ├── ccc-product/SKILL.md
│   ├── ccc-dev/SKILL.md
│   ├── ccc-reviewer/SKILL.md
│   ├── ccc-tester/SKILL.md
│   ├── ccc-ops/SKILL.md
│   ├── ccc-kb/SKILL.md
│   ├── ccc-regress/SKILL.md
│   └── ccc-audit/SKILL.md                      # v0.51.0 (P1-9) 新增
├── README.md
├── CLAUDE.md                                   # 框架总纲（维护者用）
├── CHANGELOG.md
├── VERSION                                     # ★ 版本 SSOT (v0.51.0)
├── LICENSE
├── pyproject.toml                              # ruff + pytest 配置
├── .pre-commit-config.yaml                     # 本地 hook
├── .github/workflows/ci.yml                     # CI: version-sync / pytest / ruff / shellcheck / e2e / selfcheck
│
├── references/
│   ├── red-lines.md                            # 33 条红线（18 编号 + X8 + R7）
│   └── board-task-schema.md                    # task JSONL 格式标准
│
├── docs/
│   ├── lessons.md
│   ├── architecture.md                         # 本文件
│   ├── architecture-core.md                    # Engine/Board 调度核心说明
│   ├── CONTROL.md                              # 控制面四态机
│   ├── roadmap.md
│   ├── STRATEGY-MAP.md
│   └── STARTUP-BRIEF.md
│
├── templates/                                  # 4 文件契约模板（plan/phases/report/verdict/AGENTS）
│
├── scripts/
│   ├── _config.py                              # 集中配置（Config dataclass）
│   ├── _board_store.py                         # ★ FileBoardStore（.jsonl + flock + index.json）
│   ├── _executor.py                            # ★ OpenCodeExecutor + _sanitized_env
│   ├── _ccc_control.py                         # 控制面状态机（INVENT_HARD_DISABLED=True）
│   ├── _utils.py                               # now_iso / sanitize_id 等（SSOT）
│   ├── _cost_telemetry.py                      # FinOps 成本遥测 + 轮转
│   ├── ccc-engine.py                           # ★ 单进程主循环（v0.20.1+ 替代多 launchd）
│   ├── engine/                                 # 引擎运行时（slots/active_tasks/hang/gates）
│   ├── board/                                  # Board package
│   │   ├── roles/                              # ★ 角色实现下沉处
│   │   │   ├── product.py / dev.py / reviewer.py
│   │   │   ├── tester.py / ops.py / kb.py / regress.py
│   │   │   └── common.py
│   │   ├── phase.py / store_ops.py / context.py
│   │   └── slots.py                            # OpenCodeCountProxy
│   ├── ccc-board.py                            # CLI + 兼容再导出（角色实现已下沉 board/roles/）
│   ├── ccc-board-server.py                     # Board HTTP API :7775
│   ├── ccc                                     # CLI 入口
│   ├── ccc-patrol-v4.py                        # 独立运维探针
│   ├── ccc-self-check.sh                       # 自检
│   ├── ccc-exec-commit.sh                       # Executor 退出后自动 commit
│   ├── ccc-notify.sh / ccc-hook.sh
│   ├── chat_server/                            # Hub :7777 (FastAPI)
│   │   ├── auth.py / config.py
│   │   ├── routers/                            # desktop/board/projects/ops
│   │   └── services/session_store.py
│   ├── install-engine-plist.sh                 # launchd 安装
│   └── check-version-sync.py                   # F-VER-01 版本一致性
│
├── src-tauri/                                  # Desktop 桌面端（SwiftUI 三栏）
│   ├── Cargo.toml / tauri.conf.json            # 版本同步 0.51.0
│   └── src/
│       ├── menu.rs / server.rs                 # Tauri sidecar 启动 chat_server
│       └── main.rs
│
└── tests/
    ├── scripts/                                # 单元测试
    ├── e2e/                                    # 流水线集成测试
    └── integration/                            # 真实 git 仓库集成
```

---

## 三层架构（v0.51.0）

```
┌─────────────────────────────────────────────────────────┐
│  L3: Desktop 桌面端 (SwiftUI 三栏 + Tauri sidecar)       │
│  src-tauri/ · 启动 chat_server.py :7777                  │
│ 产 epic → 写 backlog · 监控 board 状态 · 不写角色逻辑    │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / IPC
┌────────────────────────▼────────────────────────────────┐
│  L2: Engine + Board (Python)                            │
│  ┌────────────────────┐  ┌─────────────────────────────┐ │
│  │ ccc-engine.py      │  │ chat_server (Hub :7777)    │ │
│  │  + engine/slots.py │  │  + ccc-board-server :7775 │ │
│  │  + engine/active_  │  │  + auth.py (Basic + IP)    │ │
│  │    tasks.py        │  │                            │ │
│  │  + hang/gates      │  │  Dashboard cache (3s TTL) │ │
│  └─────────┬──────────┘  └─────────────┬─────────────┘ │
│            │                             │               │
│  ┌─────────▼─────────────────────────────▼─────────────┐ │
│  │  board/roles/{product,dev,reviewer,tester,         │ │
│  │               ops,kb,regress}.py + common.py        │ │
│  │  + board/phase.py / store_ops.py / context.py       │ │
│  └─────────┬───────────────────────────────────────────┘ │
│            │                                              │
│  ┌─────────▼──────────────────────────────────────────┐  │
│  │  _board_store.py (FileBoardStore, JSONL + flock)   │  │
│  │  _config.py / _utils.py / _ccc_control.py          │  │
│  │  _cost_telemetry.py (10MB 轮转 + 3 个 .gz 备份)    │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ subprocess + _sanitized_env
┌────────────────────────▼────────────────────────────────┐
│  L1: Executors (扇出)                                    │
│  opencode (主) / claude CLI (Planner) / 自定义           │
│  MAX_CONCURRENT 并行；slot 由 engine/slots.py 管理       │
│  _executor.py 抽象 → 可替换为 ContainerExecutor           │
└──────────────────────────────────────────────────────────┘
```

### 核心优势

- **存储层换数据库**：`FileBoardStore` → `PostgresBoardStore`，角色代码不改
- **执行器换容器**：`OpenCodeExecutor` → `ContainerExecutor`，角色代码不改
- **配置集中**：所有参数从 `Config` 对象读取，不在代码中硬编码
- **控制面单点切换**：`~/.ccc/control.json` 一行决定 disabled/ui/enabled/invent
- **崩溃恢复**：`engine-active-tasks.json` 持久化 + PID 存活校验（单次 ps 全表查询）

---

## 7+1 角色协议

详见 `STARTUP-BRIEF.md` §2 与 `skills/ccc-<role>/SKILL.md`。

v0.51.0 起：7 个核心角色（product/dev/reviewer/tester/ops/kb/regress）+ audit（待补实现）。
Skill + Prompt 即角色，不限于这 8 个；用户可临时拼装任意角色。

---

## 看板文件 & 4 文件契约

```
<workspace>/.ccc/
├── profile.md                   # 项目档案（首次接入生成）
├── plans/<task>.plan.md         # product 产出
├── phases/<task>.phases.json    # product 产出
├── reports/<task>.report.md     # dev 产出（含 AGENTS.md 建议段）
├── verdicts/<task>.verdict.md   # reviewer/tester 产出
└── board/                       # 看板文件
    ├── backlog/
    ├── planned/
    ├── in_progress/
    ├── testing/
    ├── verified/
    ├── released/
    └── index.json
```

task JSONL 格式标准见 `references/board-task-schema.md`。

---

## 与 QXO 的关系

CCC 和 QXO **独立发展，不互相依赖**。两者的互通通过文件格式共享契约实现：
- `references/board-task-schema.md` 定义了 task JSONL 的标准格式
- QXO 可按此格式往 CCC 的 `.ccc/board/backlog/` 写入任务
- CCC 产出的 report / verdict 也可被 QXO 读取

CCC 做"极简的 Prompt 资产"；QXO 做"可扩展的 AI 中台"。各自专注。

---

## 工程质量闭环

### 双门禁验收

reviewer + tester 同时扫 testing 列：
1. **reviewer（静态门禁）**: py_compile + git diff 范围核对 → 通过则 verified
2. **tester（动态门禁）**: pytest + plan 验收逐条执行 → 通过则 verified

两者任一通过即算 verified（多冗余通道）。

---

## 红线（33 条 = 18 编号 + X8 + R7）

完整见 `references/red-lines.md`。CCC v0.51.0 红线集：
- 18 条编号红线（核心安全/契约/边界）
- X 系列 8 条（扩展场景：成本/可观测性/契约校验）
- R 系列 7 条（回归红线）

新增 v0.51.0 关注点：
- **F-VER-01**: `VERSION` 与 package.json/Cargo.toml/tauri.conf.json/SKILL.md/CLAUDE.md/README.md 必须一致（CI 强制）
- **F-SEC-05**: board-server 鉴权不允许 `CCC_BOARD_ALLOW_LOCAL_NO_TOKEN` 跳过分支（已移除）
- **F-CON-02**: active_tasks 持久化文件不允许 finally unlink（已移除）

---

## 维护者清单

新改 CCC 时检查：

- [ ] 改了 `references/red-lines.md` → 同步加 Lesson
- [ ] 改了 `skills/` 下任何 SKILL.md → 索引 `skills/README.md` 同步
- [ ] 改了存储层 (`_board_store.py`) → 跑 `tests/scripts/test_board_store.py`
- [ ] 改了执行器 (`_executor.py`) → 跑 `tests/scripts/test_executor.py`
- [ ] 改了角色代码 (`scripts/board/roles/`) → 跑 E2E 测试
- [ ] 改了版本号 → 跑 `python scripts/check-version-sync.py`（CI 必过）
- [ ] 改了 CI 工作流 → 本地 `bash scripts/ccc-self-check.sh` 通过
- [ ] `CHANGELOG.md` 加 entry
- [ ] `VERSION` 加一 → 自动校验 7 处一致性

---

## 相关文件

- `SKILL.md` — 注入 prompt（总纲）
- `CLAUDE.md` — 框架总纲（维护者）
- `references/red-lines.md` — 红线细则
- `references/board-task-schema.md` — task JSONL 格式标准
- `docs/roadmap.md` — 发展路线图
- `docs/lessons.md` — 教训沉淀
- `CHANGELOG.md` — 版本历史
