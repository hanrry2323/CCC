# CCC — 框架说明书

> 本文件解释 CCC v0.18 的架构。面向维护者，agent 不读本文件。

---

## 一句话定义

**CCC = 6 角色看板自动化系统**（`SKILL.md` + `skills/ccc-<role>/SKILL.md` × 6），
加载到任意 IDE → 启动 6 个角色定时轮询看板。

不绑死 IDE，不绑死模型，不绑死工作目录。

---

## 概念模型

```
launchd (macOS 定时器)
  │
  ├─ product (4h):  backlog → plan.md + phases.json → planned          ── skill: ccc-product
  ├─ dev (30min):    planned → opencode write code → testing             ── skill: ccc-dev
  ├─ reviewer (2h):  testing → py_compile + diff + static check → verified  ── skill: ccc-reviewer
  ├─ tester (4h):    testing → pytest + plan 逐条验收 → verified          ── skill: ccc-tester
  ├─ ops (30min):    健康检查 + 告警 (不动 board)                        ── skill: ccc-ops
  └─ kb (23:00):     git tag + push + changelog → released               ── skill: ccc-kb

每个角色:
  1. 加载 skills/ccc-<role>/SKILL.md (角色定义 + 方法论 + 红线)
  2. 调 scripts/ccc-board.py <role> (看板操作)
  3. 写日志到 ~/.ccc/logs/role-<role>-<ts>.log
```

---

## 物理形态

```
~/program/CCC/                                  # 本目录（唯一交付物）
├── SKILL.md                                    # ★ 唯一注入 prompt（6 角色系统总纲）
├── skills/                                     # ★ 6 角色 skill 定义
│   ├── README.md                               # skill 索引
│   ├── ccc-product/SKILL.md                    # 产品经理 skill
│   ├── ccc-dev/SKILL.md                        # 开发工程师 skill
│   ├── ccc-reviewer/SKILL.md                   # 代码审查员 skill
│   ├── ccc-tester/SKILL.md                     # 测试工程师 skill
│   ├── ccc-ops/SKILL.md                        # 运维工程师 skill
│   └── ccc-kb/SKILL.md                         # 知识管理员 skill
├── README.md
├── CLAUDE.md                                   # 框架总纲（维护者用）
├── CHANGELOG.md                                # 版本历史
├── VERSION
├── LICENSE
│
├── references/
│   ├── red-lines.md                            # 12+X6 红线条目
│   └── adapters/
│       └── runtime-opencode.md
│
├── docs/
│   ├── lessons.md
│   ├── architecture.md                         # 本文件
│   ├── roadmap.md
│   ├── STRATEGY-MAP.md
│   ├── plan-spec.md
│   ├── STARTUP-BRIEF.md
│   └── adr/
│
├── templates/
│   ├── plan.plan.md
│   ├── phases.phases.json
│   ├── report.report.md
│   ├── verdict.verdict.md
│   ├── executor-prompt.template.md
│   ├── AGENTS.md
│   ├── profile.profile.md
│   └── pending-agents-suggestions.md
│
├── scripts/
│   ├── ccc-board.py                            # ★ 6 角色看板核心
│   ├── roles/                                  # ★ 6 角色 launchd 入口
│   │   ├── product.sh
│   │   ├── dev.sh
│   │   ├── reviewer.sh
│   │   ├── tester.sh
│   │   ├── ops.sh
│   │   └── kb.sh
│   ├── install-ccc-roles.sh
│   ├── ccc-exec-launcher.sh
│   ├── ccc-exec-commit.sh
│   ├── ccc-notify.sh
│   ├── ccc-hook.sh
│   ├── opencode-exec.py
│   ├── opencode-pool.py
│   ├── opencode-watchdog.sh
│   └── ...
│
└── tests/scripts/
```

---

## 看板文件 & 4 文件契约

```
<workspace>/.ccc/
├── profile.md                   # 项目档案（首次接入生成）
├── plans/<task>.plan.md         # product 产出
├── phases/<task>.phases.json    # product 产出
├── reports/<task>.report.md     # dev 产出（含 AGENTS.md 建议段）
├── verdicts/<task>.verdict.md   # reviewer/tester 产出
└── board/
    ├── backlog/
    ├── planned/
    ├── in_progress/
    ├── testing/
    ├── verified/
    ├── released/
    └── index.json
```

---

## 各角色协议

### Product Protocol

- **输入**: backlog task（用户需求）
- **输出**: plan.md + phases.json + 挪 planned
- **门禁**: SPEC（每个 subtask 必须 Specific / Programmatically evaluable / Explicit scope / Constrained）
- **约束**: 不写代码，不写 verdict

### Dev Protocol

- **输入**: plan.md + phases.json（from planned）
- **输出**: 代码改动 + report.md + 挪 testing
- **方法**: 逐 phase 推进，每 phase 单独 commit
- **约束**: 不超过 plan 范围，不写 plan/verdict

### Reviewer Protocol

- **输入**: testing task（from 看板）
- **输出**: py_compile + git diff 核对 + 通过→verified
- **约束**: **只读不写**（有写权限就会去修，破坏并行隔离）

### Tester Protocol

- **输入**: testing task
- **输出**: pytest 结果 + plan 验收逐条核对 + 通过→verified
- **约束**: 不做 plan 里的验收项跳过

### Ops Protocol

- **输入**: 无（只看不写 board）
- **输出**: 健康报告 + 告警
- **约束**: 只告警不处理

### KB Protocol

- **输入**: verified task
- **输出**: git tag + push + changelog 追加 + 挪 released
- **约束**: 不删 tag，不直接写 AGENTS.md

---

## 角色启动链

```
launchd (macOS)
  │
  └── /bin/bash scripts/roles/<role>.sh
        │
        ├── export CCC_ROLE=<role>
        ├── export CCC_ROLE_SKILL=skills/ccc-<role>/SKILL.md
        ├── echo "[skill] loaded: ..." >> log
        │
        └── python3 scripts/ccc-board.py <role>
              │
              ├── read/set env (CCC_ROLE)
              ├── read .ccc/board/<col>/
              ├── execute role logic
              └── write result + move columns
```

---

## 工程质量闭环

### 双门禁验收

reviewer + tester 同时扫 testing 列：

1. **reviewer（静态门禁）**: py_compile + git diff 范围核对 → 通过则 verified
2. **tester（动态门禁）**: pytest + plan 验收逐条执行 → 通过则 verified

两者任一通过即算 verified（多冗余通道）。

### AGENTS.md 积累

1. dev 在 report 中写 `> **AGENTS.md 建议:**`
2. kb 归档时收集到 `templates/pending-agents-suggestions.md`
3. 人类审批后写入 `.ccc/AGENTS.md`
4. **禁止 agent 直接写入**

---

## 红线（12 + X6）

完整见 `references/red-lines.md`。核心：

| # | 一句话 |
|---|--------|
| 1-5 | 改文件限制、验收、commit 规范 |
| **6** | 角色不互串（核心架构约束） |
| 7-10 | 启动顺序、commit 纪律、卡死止损、无隐式记忆 |
| **11** | Verdict 必须写文件（≥3 probes） |
| **12** | 禁止 agent 自主启用 CCC |

---

## 维护者清单

新改 CCC 时检查清单：

- [ ] 改了 `references/red-lines.md` → 同步加 Lesson
- [ ] 改了 `skills/` 下任何 SKILL.md → 索引 `skills/README.md` 同步
- [ ] 加新模板到 `templates/` → 索引同步
- [ ] 改了 4 文件契约路径 → 本文件 + SKILL.md 同步
- [ ] 改了角色脚本 → 跑 `bash -n` 验证语法
- [ ] 跑过 1 次 `ccc-board.py <role>` 验证机械逻辑
- [ ] `CHANGELOG.md` 加 entry

---

## 相关文件

- `SKILL.md` — 注入 prompt（总纲）
- `skills/README.md` — 6 角色 skill 索引
- `CLAUDE.md` — 框架总纲（维护者）
- `references/red-lines.md` — 红线细则
- `docs/roadmap.md` — 发展路线图
- `docs/lessons.md` — 教训沉淀
- `CHANGELOG.md` — 版本历史
