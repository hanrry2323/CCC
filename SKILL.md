---
name: ccc-protocol
description: "CCC — Connect–Claude Code. A 7-role automated development pipeline with kanban board. Trigger when user says: '按 CCC 流程跑 X', 'ccc 跑一下 X', '调度一个多阶段任务', '用看板跑 X'"
---

# CCC — Connect–Claude Code (v0.38.0)

> **One SKILL, every IDE, every model.** A skill that turns any coding agent
> into a **7-role automated development system** with kanban board and skill-based
> role definitions. Loads cleanly into Trae, Cursor, Zed, VS Code, OpenCode,
> or any tool that supports system-prompt files.
>
> **含义**：**C**onnect–**C**laude **C**ode。把 Claude Code 的能力连接到
> 任何 IDE 工具，让 agent 通过看板自我调度。

---

## 启动必读（懒加载）

**只读 1 个文件**：`STARTUP-BRIEF.md`（~700 token），其他文件按需 grep。

```bash
# 1. 必读（启动第 1 件事）
cat STARTUP-BRIEF.md

# 2. 按需查询
grep -A 15 "## 红线 11" references/red-lines.md
grep -A 8  "## Lesson 36" docs/lessons.md
cat skills/README.md        # 查 7 角色 skill 索引
cat .ccc/board/index.json   # 查看板状态
```

---

## 7 角色系统（唯一范式）

角色各自定义在 `skills/ccc-<role>/SKILL.md`，由 CCC Engine 串行驱动（v0.20.1+）。

| 角色 | Skill 文件 | 看板列 | 职责 |
|------|-----------|--------|------|
| **product** | `skills/ccc-product/SKILL.md` | backlog → planned | 拆任务、写 plan、SPEC 门禁 |
| **dev** | `skills/ccc-dev/SKILL.md` | planned → in_progress → testing | 调 opencode 写代码 |
| **reviewer** | `skills/ccc-reviewer/SKILL.md` | testing → verified | LLM 语义审查 |
| **tester** | `skills/ccc-tester/SKILL.md` | testing → verified | pytest + 逐条验收 |
| **ops** | `skills/ccc-ops/SKILL.md` | 不动 board | 健康检查 + 告警 |
| **kb** | `skills/ccc-kb/SKILL.md` | verified → released | git tag + push + changelog |
| **regress** | `skills/ccc-regress/SKILL.md` | released → backlog(回归bug) | 每日回测 |

**任务流转**：
```
backlog → planned → in_progress → testing → verified → released
                                                              ↓ (regress)
                                                         backlog(回归bug)
```

**触发方式**（红线 12：agent 不自主启用，用户显式触发）：
- "按 CCC 流程跑 X" / "ccc 跑一下 X"
- "调度一个多阶段任务" / "用看板跑 X"
- 小（单文件改 1-5 行）→ agent 直接处理，不走 CCC

---

## 红线（详见 `references/red-lines.md`）

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
| **11** | Verdict 必须有文件 | 口头 PASS 不算 PASS |
| **12** | 禁止 agent 自主启用 CCC | 用户显式触发 |

> **Lesson 27**：`claude -p` 是 print 模式，prompt 走 stdin。**Lesson 28**：口头 PASS 不算 PASS，verdict 必须有产物证据。

---

## 关键资产清单

| 路径 | 说明 |
|------|------|
| `skills/ccc-<role>/SKILL.md` × 7 | 各角色 skill 定义 |
| `templates/executor-prompt.template.md` | 执行器 prompt 模板（含 6 条自检） |
| `references/red-lines.md` | 红线强约束 |
| `scripts/ccc-engine.py` / `ccc-board.py` | Engine 主循环 + 看板核心 |
| `scripts/_config.py` / `_board_store.py` / `_executor.py` | 配置、存储、执行抽象 |
| `tests/scripts/` | pytest 核心测试 |
| `docs/lessons.md` | 历史教训 |
| `STARTUP-BRIEF.md` | **启动必读（SSOT）** |

---

## 命名含义

**CCC** = **C**onnect — **C**laude **C**ode。不再有其他扩写含义。

当前版本见 `VERSION`。历史见 `CHANGELOG.md`。
