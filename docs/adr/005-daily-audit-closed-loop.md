# ADR-005 — Daily-Audit Closed Loop (持续化产出平台)

## 状态

Proposed (2026-07-02, 来自 V9.S0 daily-snapshot 资源洪水事件)

## 决策

把 CCC 从"1 次 task runner"升级为**持续化产出平台**，加 daily-audit 闭环：

```
每日循环:
  plan (Planner) → dispatch (Executor) → execute → journal (自动日报)
                                                         ↓
                          next plan 改进 ← audit report ← daily-audit agent
```

## 背景

2026-07-02 V9.S0 daily-snapshot 资源洪水事件：
- 每日 50+ commit → dispatch 50+ Claude task → 55×300MB ≈ 16.5GB → 8GB M1 崩盘
- 修法：dispatch 限流 (Semaphore 3) + journal only (不重跑 auto items)
- 后续追问：日报本身写出来后，**谁读？读什么？读了干什么？**

**当前缺口**：
- qx-observer daily-snapshot (V9.S0)：**生成日报**（commit → journal）
- **没有 audit agent**：没人读日报，没人查 bug，没人反馈给明天的 plan

**用户洞察**：
> 这个功能，其实是 ccc 的延升，每日我们计划，投递好几十个任务，执行完了，每日复盘很重要；但是更重要的是，让一个独立的 agent 工具，去读一遍这个日报；按做过的事情，再去跑一次；1、查 bug；2、给 planer 一个报告。

## 设计

### 跟 qxo daily-snapshot 关系（避免重叠）

| 维度 | qx daily-snapshot (V9.S0) | CCC daily-audit (ADR-005) |
|------|---------------------------|---------------------------|
| 角色 | **生成日报** | **消费日报** |
| 输入 | git commits | journal file `~/Desktop/日报/YYYY-MM-DD-auto.md` |
| 输出 | journal file | audit report `.ccc/audit/YYYY-MM-DD.audit.md` |
| 时间 | 每日扫 commit 时 | 每日 22:00 cron（晚于所有 dispatch）|
| 责任 | 把"做过什么"记录下来 | 把"做得怎样"反馈给明天的 plan |
| 状态 | 已实现（修过 bug）| **Proposed** |

**两者关系（R3 修正 — 来自对抗性评估）**：

之前说"上下游关系，不是重叠" — **不够准确**。

**真因**：当前 qxo self-loop 自己就在做"复盘"（worktree 清理 + lesson 沉淀 + dispatch 自循环）。**daily-audit 的正确定位不是"CCC 升级"，而是"qxo self-loop 不够时的备份方案"**。

**判断流程**：
1. qxo self-loop 跑 1-2 周
2. 观察 self-loop 是否能产出有效 plan 改进
3. 如果够 → ADR-005 不实施（qxo 已经有这能力）
4. 如果不够 → 启用独立 audit agent（即本 ADR）

**当前**：qxo self-loop 还在跑，**先观察再决定**。

### daily-audit skill 设计（SKILL.md ≤500 行）

| 段 | 内容 | 来源 |
|----|------|------|
| 1. **plan vs actual** | 今日 plan 任务 vs 实际完成（gap）| journal + BACKLOG diff |
| 2. **failure 分类** | dispatch fail / executor 卡死 / verifier 拒绝 / journal 缺失 | journal + report.md + verdict.md |
| 3. **lesson 沉淀** | 今日新 lessons → 候选 commit | docs/lessons.md diff |
| 4. **bug 清单** | 已暴露 + 潜在风险（按严重度排序）| agent 推理 |
| 5. **改进建议** | 明天 plan 该怎么改（v0.1 草稿）| 综合判断 |
| 6. **红线条目** | 关键决策点（需人类 5 min review）| 红线标记 |

### 4 条硬约束（自指回路红线）

| # | 约束 | 原因 |
|---|------|------|
| 1 | **audit agent ≠ dispatch agent** | 防"自己审自己"失败偏见（必须独立 session + 独立 prompt） |
| 2 | **必须 ai-loop-router 通路** | 不能 fallback minimax（失去三角色分离 = 同模型偏见）|
| 3 | **必须 `--max-budget-usd 5`** | audit 每日跑，预算失控风险（相对 Executor 200 USD）|
| 4 | **必须对抗性审计** | "audit 说没 bug" ≠ "真没 bug" — 留 5 min 给人类 review 红线条目 |

### 4 文件契约扩展

```
existing:
  plan.md (规划)        — Planner 写
  phases.json (执行)    — Planner / Executor 更新
  report.md (产出)      — Executor 写
  verdict.md (验收)     — Verifier 写

new (v0.5.0):
  audit.md (复盘)       — audit agent 写
                          路径: .ccc/audit/YYYY-MM-DD.audit.md
                          时机: 每日 22:00 cron
                          下游: 喂入 next plan 改进
```

### 三种下游方案（我推 **C 混合**）

| 方案 | 描述 | 优 | 缺 |
|------|------|----|----|
| A | **全自动**：audit → 自动写明天 plan + commit | 省人类时间 | 高风险 bug 漏处理 |
| B | **全人工**：audit → 推人类 → 人类写 plan | 安全 | 每天 5-10 min |
| **C ✅** | **混合**：audit 自动修简单 bug + 推人类决策复杂项 + plan v0.1 草稿 | 平衡 | 设计复杂 |

**C 细节**：
- 自动：写明天 plan 的草稿（v0.1），人类 OK 后 commit
- 推送：关键决策点（红线条目）→ 飞书/钉钉/桌面通知，5 min review
- 自动：低风险 bug 修复直接 commit，高风险红线条目阻塞

## 后果

**正面**：
- CCC 从"1 次 task runner"升级为"持续化产出平台"
- 每日复盘 = 软件工程"学习飞轮"，昨天的 bug 自动变成明天的改进
- 跨项目可复用：任何 dispatch → journal → next plan 场景都适用
- 与 ADR-004 multi-platform orchestration 一致（audit agent 也可跨 platform）

**负面**：
- 每日 1 个新 cron job + 新 skill + 新文件契约
- 5 文件契约（plan/phases/report/verdict/audit）增加复杂度
- audit 自己的 bug 也要 audit（递归问题）

**风险与缓解**：

| 风险 | 缓解 |
|------|------|
| 自指回路（dispatch 写日报，agent 读日报）| audit agent 独立 session + 独立 prompt + ai-loop-router |
| 资源失控（每日 audit 又调 AI）| `--max-budget-usd 5` + audit 只读不写（只写 audit.md 1 个文件）|
| 漏 bug（agent 没看到）| 红线条目强制人类 review |
| dispatch 链死了 audit 也死 | audit cron 独立于 dispatch（直接读 journal 文件）|
| audit 自己 bug 递归 | audit 自己也产出 audit-of-audit（v0.6.0）|

## 实施路径

- **v0.4.0** (2-3 月)：先实现 ADR-004 multi-platform orchestration
- **v0.5.0** (3-6 月)：本 ADR — daily-audit skill + cron + 4 文件契约扩展
- **v0.6.0** (6-9 月)：audit-of-audit（递归）+ 跨平台 audit agent
- **v1.0.0** (6-12 月)：飞书/钉钉通知 + cost/quality dashboard

## 当前优先级

**低**：
- qxo daily-snapshot (V9.S0) 已实现且已修过 bug
- 当前聚焦 qx-observer 功能（V9.S1/S2/S3/S4 阶段）
- daily-audit 跟 qxo **上游重叠**（journal 文件就是 daily-snapshot 写的），不需独立实施
- 先用 qxo 自己 daily-snapshot 的产出观察 1-2 周，评估是否真的需要独立 audit agent
- 若 qxo 的 self-loop 自我复盘足够 → ADR-005 可能不需要
- 若 qxo 自我复盘不够 → 再回到本 ADR 实施

## 备注

- 本 ADR 是 v0.5.0 **Proposed**，不立即实施
- 用户明确：当前重要的是 qx，不是 CCC v0.5.0
- 写 ADR 仅为记录设计意图，避免未来重新探索