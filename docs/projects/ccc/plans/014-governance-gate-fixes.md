# 方案 · 治理门禁系统性修复（docgate Q3/Q4 + 出卡查重）

> 项目：ccc · 编号：ccc-plan-014 · 状态：已确认 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-10 · 更新：2026-08-10
> 关联卡：ccc042 ccc043
> 关联方案：无（2026-08-10 复盘新增）

## 目标

修复复盘发现的 2 个门禁系统性缺陷（A2/B1），A1 已随本次直接修复（plan-to-cards 关联格式）。

## 背景

2026-08-10 复盘（6 Agent 审计）确认：
- **A2**：`server/board/docgate.py get_modified_files` 用 `git diff --name-only origin/main`（工作区 vs 本地 stale origin/main），卡合入后 diff 必空 → Q3/Q4 声明[是]必误判，真实做了 README/roadmap 更新的卡被逼归[否]（ccc033/ccc040 已受害）。
- **B1**：`scripts/new-card.sh` 查重只扫本地 `docs/dispatch/<prefix>/`，出卡前不 fetch origin main → 本地过期时撞号漏过（8/9 多次撞号根因，与看板漂移同源）。
- **A1**（已修，不在本方案转卡）：plan-to-cards 关联 `ccc-plan: <标题>` 不合门禁 `prefix-plan-NNN`，已改为从方案文件名取编号。

## 方案内容

1. **卡1（A2）docgate Q3/Q4 post-merge 校验修复**：get_modified_files 改为对比「分支 merge-base..branch」而非工作区 vs origin/main；approve-merge 校验时基于 codex 分支快照，使卡合入后 Q3/Q4 [是] 可验证。
2. **卡2（B1）出卡查重升级**：new-card.sh 出卡前先 `git fetch origin main`，查重与编号自增基于 origin/main 的 dispatch（不只本地目录），杜绝本地过期撞号。

## 验收标准

- [ ] A2：对真实「README/roadmap 已更新且已合入」的卡，approve-merge Q3/Q4 [是] 校验可通过（用 ccc040 作为回归样例）。
- [ ] B1：出卡时本地不拉最新也不撞号（撞号被拒）；新增测试覆盖「本地过期但远端已占用编号」场景。
- [ ] 门禁相关测试全绿（docgate/validate/board_validate）。

## 转卡计划

```ccc-plan
title: 治理门禁系统性修复（docgate Q3/Q4 + 出卡查重）
project: ccc
slices:
  - title: docgate Q3/Q4 post-merge 校验修复
    slug: docgate-postmerge-fix
    acceptance:
      - server/board/docgate.py get_modified_files 改为基于「分支 merge-base..branch」对比（approve-merge 校验时用 codex 分支快照），不再用工作区 vs origin/main
      - 对真实已合入卡（如 ccc040，Q3 README 真实更新）approve-merge 校验 [是] 可通过
      - 维护区校验回归：验证 Q1/Q2 逻辑不回归（plan-to-cards 新格式卡 + 存量卡）
      - server/tests/test_writeback_gate.py / test_docgate* 全绿
    whitelist:
      - server/board/docgate.py
      - server/tests/**
      - scripts/approve-merge.sh
    executor: OpenCode
  - title: 出卡查重升级（fetch 远端 + 基于 origin/main 查重）
    slug: card-dispatch-gate
    acceptance:
      - scripts/new-card.sh 出卡前先 git fetch origin main，查重与编号自增基于 origin/main 的 docs/dispatch（不只本地目录）
      - 本地仓库过期（未 pull）时，编号已在远端被占用 → 拒绝/自增跳过，不撞号
      - 新增测试：构造「本地过期但远端已占用编号」场景，出卡被拒
      - scripts/plan-to-cards.sh 走的 new-card.sh 同样生效（关联格式已修）
    whitelist:
      - scripts/new-card.sh
      - scripts/plan-to-cards.sh
      - server/tests/**
    executor: OpenCode
```

## 备注

- A1 已直接修复（不在本方案转卡）：plan-to-cards 关联改为 `<prefix>-plan-<NNN>`。
- 复盘相关登记见 hp-kb `/codex/topics/ccc/backlog-3-items-pending-2026-08-10`。
