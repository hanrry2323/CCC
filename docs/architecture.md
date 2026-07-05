# CCC — 框架说明书

> 本文件解释 CCC 在 v0.5 重构后的形态。面向维护者，agent 不读本文件。

---

## 一句话定义

**CCC = 一个 SKILL 资产**（`SKILL.md`），加载到任意 IDE → 把 agent 变成三角色 pipeline。

不绑死 IDE，不绑死模型，不绑死工作目录。
工程纪律沉淀在 `references/red-lines.md`，教训沉淀在 `docs/lessons.md`。

---

## 概念模型

```
┌─────────────────────────────────────────────────────────────┐
│                    IDE Tool (Trae / Cursor / Zed)           │
│                                                             │
│  user: "按 ccc full 跑 X 任务"                              │
│    ↓                                                        │
│  [Skill 加载] ← ~/program/CCC/SKILL.md                      │
│    ↓                                                        │
│  [Agent 一次性注入 prompt]                                   │
│    ↓                                                        │
│  [Planner] ──对话多轮──> plan.md + phases.json               │
│    ↓                                                        │
│  [Executor] ←── user 显式启动（红线 12）                    │
│    ↓                                                        │
│  [报告] report.md（含 VERDICT 段引用）                       │
│    ↓                                                        │
│  [Verifier] ←── 独立 session                                  │
│    ↓                                                        │
│  [verdict.md]（≥3 probes + 真产物证据 / 红线 11）            │
│    ↓                                                        │
│  exit（任务结束，注入消息被消化）                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 物理形态

```
~/program/CCC/                                  # 本目录（唯一交付物）
├── SKILL.md                                    # ★ 唯一注入 prompt
├── README.md                                   # 项目介绍 / 30 秒上手
├── CLAUDE.md                                   # 框架总纲（维护者用）
├── AGENTS.md                                   # 子 agent 接入模板
├── CHANGELOG.md                                # 版本历史
├── VERSION                                     # 当前版本号
├── LICENSE
│
├── references/                                 # 工程纪律沉淀
│   ├── red-lines.md                            # 11 + 2 红线条目
│   └── adapters/                               # LLM CLI 适配器
│       ├── runtime-claude-p.md                 # claude -p 调用规范
│       ├── runtime-opencode.md
│       ├── runtime-cursor.md
│       ├── runtime-zcode.md
│       └── scheduler-*.md                      # 调度器适配
│
├── docs/                                       # 文档
│   ├── lessons.md                              # 框架级教训沉淀
│   ├── architecture.md                         # 本文件
│   ├── roadmap.md                              # 发展路线图
│   ├── plan-spec.md                            # plan.md 字段规范
│   ├── verification-spec.md                    # verifier ≥3 probes 规范
│   ├── execution-protocol.md                   # 执行协议
│   ├── agent-commands.md
│   └── adr/                                    # 架构决策记录
│
├── templates/                                  # 4 文件契约模板
│   ├── plan.plan.md
│   ├── phases.phases.json                      # JSONL（不嵌套）
│   ├── report.report.md                        # 含 VERDICT 引用段
│   ├── verdict.verdict.md                      # ≥3 probes 模板
│   ├── executor-prompt.template.md
│   ├── AGENTS.md                               # 子 agent prompt 模板
│   └── profile.profile.md
│
├── scripts/                                    # 机械步骤
│   ├── ccc-exec-commit.sh                      # 自动 commit（兜底）
│   ├── executor-watchdog.sh                    # 卡死检测
│   ├── ccc-hook.sh
│   ├── ccc-init.py                             # 项目 .ccc/ 初始化
│   ├── ccc-search.py
│   └── install-ccc-as-skill.sh                 # 装到 ~/.claude/skills/
│
└── examples/                                   # 实战示例
```

**被删除的**（v0.5 解耦）：

- ❌ `projects/qxo/`（迁移到 `docs/lessons.md`）
- ❌ `~/.claude/skills/ccc-protocol -> ../CCC` 之外的硬编码目录

---

## 4 文件契约（绝对路径）

```
<workspace>/.ccc/                              # 由 agent 自动创建
├── profile.md                                  # 项目档案（首次接入）
├── plans/<task>.plan.md                        # Planner 产出
├── phases/<task>.phases.json                   # Planner 产出
├── reports/<task>.report.md                    # Executor 产出（含 VERDICT 段）
├── verdicts/<task>.verdict.md                  # Verifier 产出（强证据红线 11）
└── abnormal-reports/                           # 异常记录
```

`<workspace>` 由 agent 当前对话所在目录决定。**不强制 CCC 目录**，所以 CCC 自然支持任意项目。

---

## 三角色（Protocol）

### Planner Protocol

**Inputs**:
- 用户意图（一句话任务）
- `<workspace>/.ccc/profile.md`（项目背景）
- 知识库（可选）：`~/program/CCC/docs/lessons.md` 关键 lessons

**Outputs**:
- `<workspace>/.ccc/plans/<task>.plan.md`
- `<workspace>/.ccc/phases/<task>.phases.json`

**约束**:
- 不写代码
- 不 commit
- 不写 verdict
- 行号 / 文件路径必须真实（用 grep 验证）

### Executor Protocol

**Inputs**:
- `plans/<task>.plan.md`
- `phases/<task>.phases.json`

**Outputs**:
- `<workspace>/.ccc/reports/<task>.report.md`（含 `> VERDICT:` 段）
- working tree 的 plan 范围文件改动

**约束**:
- 不写 Plan（只执行）
- 不写 verdict
- 不 commit（由 `ccc-exec-commit.sh` 兜底）
- 退出前自检：working tree 仅含 plan 文件

### Verifier Protocol

**Inputs**:
- `plans/<task>.plan.md`
- `<workspace>/.ccc/reports/<task>.report.md`

**Outputs**:
- `<workspace>/.ccc/verdicts/<task>.verdict.md`（必须真写，红线 11）

**约束**:
- ≥3 adversarial probes
- 每条 Probe：Method / Evidence / Result
- VERDICT 三选一：PASS / CONDITIONAL_PASS / FAIL
- **独立 session 调起**（避免 Executor 状态污染）

---

## 红线（11 + 2）

完整见 `references/red-lines.md`。**核心**：

| # | 一句话 |
|---|--------|
| 1 | 不改 /etc 等系统文件 |
| 2 | plan 验收必须可执行 |
| 3 | working tree 仅 plan 范围 |
| 4 | 单 phase 单 commit |
| 5 | phases.json 用 JSONL 不用嵌套 |
| 6 | 三角色不互串 |
| 7 | 启动时第一个读 profile.md |
| 8 | 不越界 commit / push |
| 9 | 卡死立即止损 |
| 10 | 禁止跨会话隐式记忆（state.md 接力） |
| **11** | Verifier 必须写 verdict 文件 |
| **12** | 禁止 agent 自主启用 CCC（用户显式） |

**配套教训**:
- **Lesson 27**：`claude -p` 是 print 模式，prompt 走 stdin
- **Lesson 28**：口头 PASS 不算 PASS，verdict 必须有产物证据

---

## 与 Loop Engineering 的关系

CCC 是 **Loop Engineering 的最小闭环实现**：

```
任务投进去
  ↓
CCC skill 自动拆解（Planner）
  ↓
CCC skill 自动调度（Executor）
  ↓
CCC skill 自动验收（Verifier + 红线 11）
  ↓
质量飞轮沉淀（quality_flywheel + Lesson）
  ↓
IDE 定时任务唤起下一轮（v0.6 路线）
```

详见 `docs/roadmap.md`。

---

## 设计哲学（为什么不绑死工具）

CCC 选 SKILL 形态而非 framework 代码库的 4 个理由：

| 决策 | 理由 |
|------|------|
| **不是 framework 代码库** | 维护成本最低，跨 IDE 最容易 |
| **不绑 IDE** | Trae / Cursor / Zed / VS Code 都能用同一份 SKILL |
| **不绑模型** | 通过 `ANTHROPIC_BASE_URL` 路由中转站，按任务选 model |
| **不绑工作目录** | agent 当前目录即项目根，自然迁移 |

---

## 维护者清单

新改 CCC 时检查清单：

- [ ] 改了 `references/red-lines.md` → 同步加 Lesson
- [ ] 改了 SKILL.md → 检查 SKILL 还能加载（Trae / Cursor 各试一次）
- [ ] 加新模板到 templates/ → README.md 链接同步
- [ ] 改了 4 文件契约路径 → docs/architecture.md 同步
- [ ] 跑过 1 个真实任务 → CHANGELOG.md 加 entry

---

## 相关文件

- `SKILL.md` — 注入 prompt（唯一交付）
- `CLAUDE.md` — 框架总纲
- `references/red-lines.md` — 红线细则
- `docs/roadmap.md` — 发展路线图
- `docs/lessons.md` — 教训沉淀
- `CHANGELOG.md` — 版本历史
