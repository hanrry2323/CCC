# 案例 — qx-observer audit-frontend 三轮修订流程 (2026-07-01)

## 背景

qx-observer 是 CCC 框架的主要消费方。2026-07-01 任务：
**前端代码审计 + loop-code 桌面端源码定位 + 陈旧/缺失/重复端口盘点**。

## 任务目标

跑 6 phases 调研，输出 ≥50KB 完整报告，沉淀为 qx-observer 前端 + 后端 + 桌面端蓝图。

## 时间线

| 版本 | 模型/方法 | 报告大小 | Verifier 结果 |
|------|-----------|----------|--------------|
| v0 | minimax/Mavis（**已废弃**，v0.3 时期） | 54 KB | — 用户判定 minimax ≠ Claude，备份隔离 |
| v1 | claude-p (claude Code CLI 走 ai-loop-router :4000) | 57 KB | CONDITIONAL_PASS — 7 Warning + 5 Info (0 Critical) |
| v2 | claude-p REVISED | 57 KB | **PASS** — 0C/0W/2I |

## 关键 commit (qx-observer 仓)

- `14045b7` — v1 审计报告初稿 (Phase 1/3)
- `9502cfc` — 修订 v2: dead API 分析扩展至 direct fetch 调用 (Phase 2/3)
- `88923cc` — 最终修订版 REVISED (Phase 3/3)
- `bac2fc2` — phases.json commit hash 更新收尾

## 三轮修订核心改动

1. **5 个 False Positive 死代码清除**: Verifier 抓出 service/*.ts 中被动态引用的"死代码", 修订 v2 做 grep 全网 + 动态 import 反查
2. **端口 7788 (NexusCore) 补充**: v1 漏记, v2 补
3. **Dead API 估值 68 → 53**: v1 仅 grep service/*.ts, v2 扩 direct fetch 覆盖 17 文件

## 3 个关键决策

1. **minimax 报告不可信 → 必跑 claude-p 重写** (触发 Lesson 19 红线 9)
2. **Verifier 抓 FP 后必修订 v2, 不能只让报告挂 CONDITIONAL_PASS**
3. **修订 v2 必做 direct fetch 覆盖, 不光跑 service/*.ts grep**

## 教训要点 (沉淀为 Lesson 20)

1. **调研任务必须用 claude-p 走 ai-loop-router, minimax ≠ Claude**
2. **Verifier 必先独立验收, 抓死代码 FP + 方法论盲区**
3. **三轮修订 (v0→v1→v2) 比一次性手写更有价值**

## 如何用本 SKILL.md 跑通此 example

### 启动位置

项目根：`~/program/qx-observer`

### 按 SKILL.md Procedure 执行

1. **Planner**: 读 `~/program/CCC/CLAUDE.md` + `qx-observer/.ccc/profile.md`
   写 plan 到 `.ccc/plans/audit-frontend-and-locate-loopcode.plan.md`
   含 6 phases、文件白名单（`app/ frontend/ src-tauri/`）、执行方式 `auto`、预算 200 USD

2. **Executor**: `claude -p "$(cat /tmp/audit-executor.txt)" --permission-mode bypassPermissions --max-budget-usd 200`
   按 plan 逐 phase 执行、逐 phase commit、更新 phases.json
   完成后写 `.ccc/reports/audit-frontend-and-locate-loopcode.report.md`

3. **Verifier**: 同上启动，但 prompt 要求 ≥3 adversarial probes
   写 `.ccc/verdicts/audit-frontend-and-locate-loopcode.verdict.md`
   含 VERDICT: PASS / CONDITIONAL_PASS / FAIL

4. **循环**: Verdict CONDITIONAL_PASS → 写 `fix-conditional-pass-warnings` plan → 重跑 Executor → 再验收至 PASS

### 完整文件链路

```
.ccc/
├── plans/audit-frontend-and-locate-loopcode.plan.md
├── phases/audit-frontend-and-locate-loopcode.phases.json
├── reports/audit-frontend-and-locate-loopcode.report.md
├── verdicts/audit-frontend-and-locate-loopcode.verdict.md
└── verdicts/fix-conditional-pass-warnings.verdict.md
```

## 关联文件

- 总报告: `~/program/qx-observer/.ccc/reports/audit-frontend-and-locate-loopcode.report.md` (REVISED 2026-07-01)
- 旧 verdict: `~/program/qx-observer/.ccc/verdicts/audit-frontend-and-locate-loopcode.verdict.md` (CONDITIONAL_PASS)
- 新 verdict: `~/program/qx-observer/.ccc/verdicts/fix-conditional-pass-warnings.verdict.md` (PASS)
- 跨项目 Lesson 20: `~/program/CCC/projects/qxo/lessons.md`
- 项目 Lesson 表: `~/program/qx-observer/docs/lessons.md`
