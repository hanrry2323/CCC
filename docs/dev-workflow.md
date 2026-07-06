# CCC Dev Workflow

> **我（Claude）→ 你（老板）**：三角色自动跑流程，你只在 milestone 拍板。

---

## 1. 角色定义

```
你（老板） ─── 产品 & 方向制定者
    │
    ▼
我（Claude）── 架构师 & 执行者
    │
    ├── Planner     ─── 拆 plan + phases.json
    ├── Executor    ─── 写代码 + 验证 + report
    └── Verifier    ─── 独立检查 + verdict
```

**你的职责**：
- 拍方向、定优先级、决定 milestone
- review plan 和 verdict（不 review 每行代码）
- 在"做大决策"时介入（新依赖 / sudo / 方向摇摆 / 花钱）

**我的职责**：
- 出 plan → 执行 → 验证 → commit 全自动
- 小决策自己做，大决策问老板
- 做错了直接修，不辩解

---

## 2. Task 生命周期

```
[老板] 说"做一个 X"
    │
    ▼
[Planner] 出 plan.md + phases.json
    │   ← 老板 review（可选）
    ▼
[Executor] 按 phases 执行
    │   ├── phase 1: do + verify + commit
    │   ├── phase 2: do + verify + commit
    │   └── ...
    ▼
[Verifier] 写 verdict.md
    │
    ▼
[老板] 验收 or 提下一项
```

### 自动动作

| 阶段 | 自动 | 不自动 |
|------|------|--------|
| Plan | 拆解 + 拆 phases | ⚠️ 超出范围 / 新依赖 |
| Execute | 写代码 + 跑测试 + commit | ⚠️ sudo / 改 .env |
| Verify | 运行 verdict 脚本 + 写文件 | ⚠️ verdict 不通过时不 commit |
| Commit | `git add -A && git commit` | ⚠️ 超过 plan 范围不 commit |

---

## 3. 文件契约

| 文件 | 谁写 | 位置 |
|------|------|------|
| plan.md | Planner | `.ccc/plans/<task>.plan.md` |
| phases.json | Planner | `.ccc/phases/<task>.phases.json` |
| report.md | Executor | `.ccc/reports/<task>.report.md` |
| verdict.md | Verifier | `.ccc/verdicts/<task>.verdict.md` |

### 红线（自动遵守）

| # | 红线 | 谁查 |
|---|------|------|
| 2 | 验收必须可执行 | Verifier |
| 4 | 单 phase 单 commit | Executor |
| 8 | 每步必 commit | Executor |
| 11 | Verifier 必须写 verdict 文件 | CI / pre-commit |

---

## 4. 你介入的时机

| 场景 | 怎么做 | 原因 |
|------|--------|------|
| **新方向** | 说"做 X" | 我执行 |
| **方向摇摆** | 说"原方向不变" / "转做 Y" | 我不自行转向 |
| **新依赖** | 同意/拒绝 | 红线 3: 不引入未授权依赖 |
| **sudo / 系统配置** | 同意/拒绝 | 红线 1: 不动系统文件 |
| **花钱** | 决定预算 | 按默认预算或超出时 |
| **发现方向错了** | 说我直接说"这个不行，因为…" | 我不分析利弊让你选 |
| **review plan** | 看 plan.md 前几行 | 只确认范围，不 review 细节 |
| **review verdict** | 看 verdict.md | 只确认通过/不通过 |

---

## 5. 移交后的任务分工

### 你做
- 在 Trae 内加载 CCC skill（一次配置）
- 拍 direction / milestone
- review handoff-report.md 签字
- 决定 T12/T15/T19 是否继续

### 我做（自动）
- 日常开发（fix/feature/refactor）
- 测试 + CI + pre-commit
- 沉淀教训到 `docs/lessons.md`
- 决策记录到 `DESIGN-VALIDATION.md`

### 我们共同做
- milestone 收尾 review
- 架构讨论
- 风险决策

---

## 6. 快速开始（新 task）

```bash
# 我自动做：
1. 读 plan → 拆 phases
2. 每 phase: code → test → commit
3. 写完 report + verdict

# 你需要做的：
收到"已投递"通知后，等 task 完成的通知回调。
不轮询。
```

---

## 附录：Commit Convention

```
<type>(<scope>): <subject>

<body>（可选）

Verification:
  - <evidence>: <result>
```

**type**: feat / fix / docs / test / refactor / release / chore
**scope**: ccc / scripts / docs / tests / ci
