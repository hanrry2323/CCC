# 4 文件契约详解 — CCC 文件桥接协议

CCC 协议通过 4 个文件在不同 agent 间传递状态。每个任务 `<task>` 对应 `<项目>/.ccc/` 下 4 文件。

---

## 路径约定

| 文件 | 路径模板 | 创建者 | 消费者 |
|------|----------|--------|--------|
| Plan | `.ccc/plans/<task>.plan.md` | Planner | Executor |
| Phases | `.ccc/phases/<task>.phases.json` | Planner | Executor + Mavis 跟踪 |
| Report | `.ccc/reports/<task>.report.md` | Executor | Verifier |
| Verdict | `.ccc/verdicts/<task>.verdict.md` | Verifier | Mavis + Planner |

**命名规则**：`<task>` 用 kebab-case（如 `audit-frontend-and-locate-loopcode`），与用户任务描述一一对应。

---

## 1. plan.md — 任务执行计划

**路径**：`.ccc/plans/<task>.plan.md`

### 必含字段

| 字段 | 说明 | 示例 |
|------|------|------|
| 范围-目标 | 一句话任务目标 | "审计前端代码 + 桌面端源码定位" |
| 范围-只改文件 | 白名单文件列表 | `app/`, `frontend/`, `src-tauri/` |
| 范围-不改文件 | 黑名单文件列表 | `.env`, `data/` |
| 范围-执行方式 | `manual` / `auto` / `loop` / `goal` | `auto` |
| 范围-Phase 数 | 正整数 | `3` |
| 改动 N | 三段式：做什么 / 怎么做 / 验收 | 见下方说明 |
| Commit 计划 | 表格含 Phase + 改动 + commit message | (每 phase 一行) |
| 全局验收清单 | checkbox 列表 | 编译检查 / 测试 / 范围 / commit 结构 |

### 可选字段

| 字段 | 说明 |
|------|------|
| 后续步骤 | 完成后的可选建议（Planner 兜底） |
| 提示/注意事项 | 跨文件影响、依赖关系、特殊环境要求 |

### 改动 N 三段式结构

```markdown
## 改动 1：[标题]

### 做什么
[功能意图，1-3 段自然语言]

### 怎么做
[具体文件 + 行号 + 改动方向]
[**不写具体 shell 命令**]

### 验收
[自然语言意图 + 可选参考命令]
- [验收条件 1]（参考：`shell-command`）
- [验收条件 2]（参考：`shell-command`）
```

验收条目写"意图为主，命令为辅"。命令仅作参考，禁止用命令替代自然语言描述。

---

## 2. phases.json — 阶段状态

**路径**：`.ccc/phases/<task>.phases.json`

**格式**：JSON Lines（每行一个独立 JSON 对象，不包裹数组）

```jsonl
{"phase": 1, "status": "pending", "subtasks": {"1.1": "pending", "1.2": "pending"}, "commit": null, "notes": ""}
{"phase": 2, "status": "pending", "subtasks": {"2.1": "pending"}, "commit": null, "notes": ""}
```

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `phase` | integer | ✅ | 阶段编号，从 1 开始 |
| `status` | string | ✅ | `pending` / `in_progress` / `done` / `failed` |
| `subtasks` | object | ✅ | 子任务字典，键名随意，值同为 status |
| `commit` | string\|null | ✅ | 该 phase 对应 commit hash（完成后填入） |
| `notes` | string | ✅ | 备注：失败原因 / 重试次数 / 跳过说明 |

### 红线

1. **每个 plan 都必须写 phases.json**——单 phase 改动至少写 1 行 phase 1（不写 = 没做完整）
2. **不许跳阶段更新**：`pending → done` 必须经过 `in_progress`
3. **独立 commit**：每个 phase 执行后必须独立写 commit，不准跨 phase 挤在一个 commit 里
4. **failed 不删除行**：标记 `"failed"`，写 notes 说明原因，继续后续 phase

### 更新流程

```
Planner 创建: status = "pending"  × N
Executor 逐个推进: pending → in_progress → done (填 commit hash)
```

---

## 3. report.md — 执行报告

**路径**：`.ccc/reports/<task>.report.md`

### 内容要点

| 段 | 要求 |
|----|------|
| 执行摘要 | 一句话做了什么，附 commit 汇总表 |
| 验收结果 | 每条原计划验收的检查结果（✅/❌） |
| 改动文件清单 | 每个文件路径 + 改动类型 (新增/修改/删除) |
| Commit 列表 | commit hash + message + phase 编号 |
| 未完成项 | 异常记录、跳过原因、重试次数 |
| 回滚指令 | `git revert HEAD~N..HEAD` 等 |

### 验收结果每行格式

```markdown
| 检查项 | 结果 |
|--------|------|
| plan 所有改动已实施 | ✅ |
| 验收条件 N | ✅ ❌ |
| 仅 plan 声明文件被修改 | ✅ ❌ |
```

---

## 4. verdict.md — 验收结论

**路径**：`.ccc/verdicts/<task>.verdict.md`

### 三级严重度

| 级别 | 含义 | 动作 |
|------|------|------|
| **Critical** | 必须修；功能错误/安全漏洞/越界改动 | 阻止继续，必须修复 |
| **Warning** | 建议修；虽不致命但风险/效率/风格问题 | CONDITIONAL_PASS 时驱动 v2 修订 |
| **Info** | 可选了解；偏离不严重但值得记录 | 记录备查，不驱动修订 |

### VERDICT 三选一

verdict.md 末尾 **MUST** 输出以下三者之一（单独一行）：

```
VERDICT: PASS
VERDICT: CONDITIONAL_PASS
VERDICT: FAIL
```

### 各段结构

```markdown
## 裁决
PASS / CONDITIONAL_PASS / FAIL

## 逐项核对
### 1. 文件范围
表：plan 要求 → 实际 diff → 结果

### 2. 改动内容
表：每行 diff vs plan 要求 → 结果

### 3. 验收检查
表：plan 验收项 → 验证方式 → 结果

### 4. Commit
表：hash → 预期改动 → 实际 message → 结果

### 5. Report 交叉核对
Report 自报项与独立验证结果一致，无虚报

## Critical（必须修）
| # | 文件 | 问题 |

## Warning（建议修）
| # | 文件 | 问题 |

## Info（可选了解）
| # | 说明 |
```
