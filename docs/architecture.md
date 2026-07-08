# CCC — 框架说明书

> 本文件解释 CCC v0.19 的架构。面向维护者，agent 不读本文件。

---

## 一句话定义

**CCC = 7 角色看板自动化系统**（`SKILL.md` + `skills/ccc-<role>/SKILL.md` × 7），
加载到任意 IDE → 启动 7 个角色定时轮询看板。

不绑死 IDE，不绑死模型，不绑死工作目录。

---

## 概念模型

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

## 物理形态

```
~/program/CCC/                                  # 本目录（唯一交付物）
├── SKILL.md                                    # ★ 唯一注入 prompt（7 角色系统总纲）
├── skills/                                     # ★ 7 角色 skill 定义
│   ├── README.md
│   ├── ccc-product/SKILL.md
│   ├── ccc-dev/SKILL.md
│   ├── ccc-reviewer/SKILL.md
│   ├── ccc-tester/SKILL.md
│   ├── ccc-ops/SKILL.md
│   ├── ccc-kb/SKILL.md
│   └── ccc-regress/SKILL.md
├── README.md
├── CLAUDE.md                                   # 框架总纲（维护者用）
├── CHANGELOG.md
├── VERSION
├── LICENSE
│
├── references/
│   ├── red-lines.md                            # 12+X6 红线条目
│   └── board-task-schema.md                    # task JSONL 格式标准（v0.19 新增）
│
├── docs/
│   ├── lessons.md
│   ├── architecture.md                         # 本文件
│   ├── roadmap.md
│   ├── STRATEGY-MAP.md
│   └── STARTUP-BRIEF.md
│
├── templates/                                  # 4 文件契约模板
│
├── scripts/
│   ├── _config.py                              # ★ 集中配置（v0.19 新增）
│   ├── _board_store.py                         # ★ 看板存储抽象（v0.19 新增）
│   │   └── FileBoardStore (.jsonl 实现)
│   ├── _executor.py                            # ★ 执行器抽象（v0.19 新增）
│   │   └── OpenCodeExecutor (CLI 实现)
│   ├── ccc-board.py                            # ★ 7 角色看板核心（v0.19 精简, 依赖上述 3 模块）
│   ├── ccc-board-server.py                     # HTTP 看板服务（v0.19 导入 FileBoardStore）
│   ├── ccc                                     # CLI 入口
│   ├── roles/                                  # 7 角色 launchd 入口
│   ├── opencode-exec.py                        # OpenCode CLI 执行器（保留 CLI 入口）
│   ├── opencode-pool.py                        # 进程池（v0.19 导入 OpenCodeExecutor）
│   ├── opencode-watchdog.sh
│   ├── ccc-exec-launcher.sh
│   ├── ccc-exec-commit.sh
│   ├── ccc-notify.sh
│   └── ccc-hook.sh
│
└── tests/
    ├── scripts/                                # 原有单元测试
    ├── scripts/test_board_store.py             # BoardStore 测试（v0.19 新增）
    ├── scripts/test_executor.py                # Executor 测试（v0.19 新增）
    └── e2e/
        └── test_pipeline_smoke.sh              # 完整流水线集成测试（v0.19 新增）
```

---

## 三层架构（v0.19 起）

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

### 核心优势

- **存储层换数据库**：`FileBoardStore` → `PostgresBoardStore`，角色代码不改
- **执行器换容器**：`OpenCodeExecutor` → `ContainerExecutor`，角色代码不改
- **配置集中**：所有参数从 `Config` 对象读取，不在代码中硬编码

---

## 7 角色协议

详见 `STARTUP-BRIEF.md` §2。

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

## 红线（12 + X6）

完整见 `references/red-lines.md`。新增 v0.19 红线补充：
- **Phase F**: task JSONL 格式必须按 `references/board-task-schema.md` 标准生成
- 违反此条导致 QXO 无法读入 → Critical

---

## 维护者清单

新改 CCC 时检查：

- [ ] 改了 `references/red-lines.md` → 同步加 Lesson
- [ ] 改了 `skills/` 下任何 SKILL.md → 索引 `skills/README.md` 同步
- [ ] 改了存储层 (`_board_store.py`) → 跑 `test_board_store.py`
- [ ] 改了执行器 (`_executor.py`) → 跑 `test_executor.py`
- [ ] 改了角色代码 (`ccc-board.py`) → 跑 E2E 测试
- [ ] `CHANGELOG.md` 加 entry
- [ ] `VERSION` 加一

---

## 相关文件

- `SKILL.md` — 注入 prompt（总纲）
- `CLAUDE.md` — 框架总纲（维护者）
- `references/red-lines.md` — 红线细则
- `references/board-task-schema.md` — task JSONL 格式标准
- `docs/roadmap.md` — 发展路线图
- `docs/lessons.md` — 教训沉淀
- `CHANGELOG.md` — 版本历史
