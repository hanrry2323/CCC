# Plan: readme-zcode-update (README 加入 ZCode adapter v1.2.1 章节)

> **任务 ID**: `readme-zcode-update`
> **目标**: 在 CCC 根 README.md 加入 ZCode adapter v1.2.1 章节,作为新增 adapter 的对外公告
> **日期**: 2026-07-06

---

## 1. 任务描述

**输入**: 用户要求"真调用 Claude code 执行一个测试任务"

**本任务专注要求 2**: 真调一次 `claude -p` 跑一个有意义的微任务

**期望产出**:
- `README.md` 新增 ZCode adapter 段
- `.ccc/reports/readme-zcode-update.report.md`(Executor 产物)
- `.ccc/verdicts/readme-zcode-update.verdict.md`(独立 Verifier session 产物)

---

## 2. 三角色边界(红线 6)

| 角色 | Session | 实现 |
|------|---------|------|
| **Planner** | 当前 ZCode 对话 | 本 plan + phases |
| **Executor** | 独立 `claude -p` 子进程 | 改 README.md + 写 report |
| **Verifier** | **独立 `claude -p` session**(新 UUID) | 验收 + 写 verdict.md |

---

## 3. Phase 拆解

### Phase 1: Executor 改 README.md
- 在 README.md 加 "## ZCode Adapter (v1.2.1)" 段
- 写 report 含 `> VERDICT:` 引用

### Phase 2: Verifier 独立 session 验收
- 新 UUID
- 验证 README.md 新段存在 + 引用 scripts/ccc-zcode-bridge.sh + 4 文件契约未坏
- 写 verdict.md ≥3 probes

---

只改文件:

- `README.md` (新增段)
- `.ccc/plans/readme-zcode-update.plan.md` (本文件)
- `.ccc/phases/readme-zcode-update.phases.json`
- `.ccc/plans/readme-zcode-update-executor-prompt.txt`
- `.ccc/plans/readme-zcode-update-verifier-prompt.txt`
- `.ccc/plans/readme-zcode-update-{executor,verifier}-session-id.txt`
- `.ccc/reports/readme-zcode-update.report.md`
- `.ccc/verdicts/readme-zcode-update.verdict.md`
- `scripts/ccc-znode-register.py` (readme 任务的 scope whitelist 包含此文件,因为它属于 zcode-adapter 全家桶的依赖文件)

**禁止改动**: `references/red-lines.md` / 其他源代码

## 5. Commit 计划

| Phase | 改动 | Commit |
|-------|------|--------|
| 1 | README 段 + Executor 报告 + Verifier 报告 | 1 commit: `ccc-task-id=readme-zcode-update phase=1` |

## 6. 退出标准

- [ ] README.md 真含 "ZCode Adapter (v1.2.1)" 段
- [ ] Executor session UUID ≠ Verifier session UUID(红线 6)
- [ ] Executor 报告含 `> VERDICT:` 引用
- [ ] Verifier verdict.md ≥3 probes
- [ ] 1 commit 含 ccc-task-id 前缀