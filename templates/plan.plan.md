# Plan: [<task> — 简短描述]

> 撰写：ccc-product | 执行：ccc-dev（[执行方式]）

---

## 当前代码状态

<!-- v0.23 强制：Plan 必须包含此段，描述当前代码结构的关键发现 -->
<!-- 示例：项目有 3 个核心模块（auth/api/db），当前 API 路由集中在 server.py，模型在 models/ 下 -->
<!-- 目的：确保 dev 执行时有足够的代码上下文，不因缺乏结构认知而跑偏 -->

[分析当前代码结构——入口文件、核心模块、主要路由/模型/组件、待改动点。]
- 入口/核心文件：[路径清单]
- 当前结构要点：[2-5 条，与本次改动相关的代码现状]
- 待改动点：[与 task 目标有关的具体代码位置]

---

## 范围

- **目标**：[一句话任务目标]
- **只改文件**：[白名单文件路径数组]
- **不改文件**：[黑名单文件路径数组]
- **执行方式**：`manual` / `auto` / `loop` / `goal`（四选一）
- **Phase 数**：[正整数。单 phase 也写 1]

---

## 改动 1：[简短标题]

### 做什么
[自然语言描述功能意图。说清「为什么做这个」和「预期效果」。1-3 段]

### 怎么做
[具体文件名 + 行号 + 改动方向。越精确越好]
[**不写具体 shell 命令**——Executor 自行决定如何实现]

### 验收清单

<!-- v0.21 强制：reviewer LLM 按此逐条核对 -->

- [ ] 验收条件 1：xxx
- [ ] 验收条件 2：xxx
- [ ] 边界场景：xxx
- [ ] 错误处理：xxx
- [ ] 安全相关：xxx（如有）

### 验收
[自然语言验收意图 + 可选参考命令]

- [验收条件 1]（参考：`shell-command-here`）
- [验收条件 2]

---

## 改动 2：[多 phase 时复制此结构]

### 做什么
### 怎么做
### 验收

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | [一句话] | `type(scope): description (phase 1/N)` |
| 2 | [一句话] | `type(scope): description (phase 2/N)` |

规则：每个 phase 一个独立 commit，message 含 phase 编号。

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] 全部测试通过
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（不跳阶段更新）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤（可选 — Planner 兜底）

完成后的建议、后续方向、或需要用户决策的事项。

---

## 写法提醒（红线 0 · 自然语言驱动）

| ❌ 不要这样写 | ✅ 要这样写 |
|---|---|
| 步骤 1: `git push origin main` | 把本地 main 推到 origin，让外部 clone 拿得到（参考：`git push origin main`） |
| 步骤 2: `python3 -c "import json"` | 验证 phases.json 是合法 JSON（参考：`python3 -c "import json; ..."`） |
| `grep -n "manifesto" AGENTS.md` | 确认 AGENTS.md 不再引用 docs/manifesto.md（参考：`grep manifesto AGENTS.md`） |

详细规则：`docs/plan-spec.md` §"参考命令"使用边界