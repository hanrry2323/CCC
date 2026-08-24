# CCC 历史包袱清理清单（唯一真值）

> 建立：2026-08-15 · 方案：`ccc-plan-030`（历史包袱渐进清理）
> 规则：旧物只作历史参考，不作历史包袱。分阶段清理，不搞一次性大扫除。

## 处置节奏（每个垃圾源通用）

```
盘点建档 → 隔离/备份 → 观察期（无调用）→ 定日期删除 → 清单留痕
```

- **观察期**：默认 14 天；无任何引用/调用（无新提交、无分支/卡引用、无 worktree 占用、无脚本引用）可缩至 7 天。
- **删除前人工复核**：观察到期项须人工确认无引用后删除，删除时在「删除日期」留痕。
- **归档不删**：T 卡、已关闭历史卡、旧方案 → 迁 `docs/archive/`，永久保留作历史参考。

---

## 一、codex/ 远端分支（43 个 · CCC 仓）

> Codex 已退役。已确认全部分支**未合入 main**（close-only 关闭后残留），分支 tip 对应卡在 main 均为「已关闭」。

### A. 可删（31 个）——仅卡文件贡献，卡已关闭，无未合入代码成果

| 分支 | 处置 | 观察期开始 | 观察到期 | 删除日期 | 备注 |
|------|------|-----------|---------|---------|------|
| clw003-sidebar-git | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| clw005-settings-panel | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| clw008-p0-exec-chain-fix | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| clw012-eng-foundation | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| clw013-settings-wiring | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| clw015-terminal-lifecycle | 观察→删 | 2026-08-15 | 2026-08-22 | | 非卡成果已全部在 main |
| clw018-docs-copy-consistency | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| clw021-parallel-flow-verify | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| clw023-codex-executability | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| clw024-session-open-hardening | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| clw025-session-open-verify | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| hp018-hp-pg-backtest-cron | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| hp019-task | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| hp020-chunk | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| hp022-collector-network-error-retry | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| mx027-core-60 | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| mx029-media-library-sort-persistence | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| mx030-security-p1-fixes | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| mx031-sensitive-info-cleanup | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| mx033-branch-consolidation | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| mx034-script-audit-cleanup | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| qb001-qb-ssot | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| qb002-task | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| qb003-lint | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| qb004-api-response-time-logging | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| qb005-script-argument-parsing-fix | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| xy027-xianyu-hyperframes | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| xy028-pytest-3 | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| xy029-task | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| xy030-video-encoding-progress-log | 观察→删 | 2026-08-15 | 2026-08-22 | | |
| xy031-config-path-resolution-fix | 观察→删 | 2026-08-15 | 2026-08-22 | | |

### B. 备份后删（12 个）——含 main 没有的独特文件，先导出 patch 再观察

> 阶段 3 动作：`git format-patch origin/main..origin/codex/<stem>` 导出到 `docs/archive/codex-branches/`，再进观察期。

| 分支 | 独特文件数 | 处置结果 | 观察期开始 | 观察到期 | 删除日期 | 备注 |
|------|-----------|---------|-----------|---------|---------|------|
| ccc016-t73-t70-p1-11 | 9 | 已覆盖（main 更先进）→ 可删 | | | | cluster.py 路径 main 已修正 |
| ccc017-prompt | 2 | 已覆盖（main 已有 prompt_inject 日志）→ 可删 | | | | |
| ccc018-task | 1 | **已合入 main**（2026-08-15）→ 可删 | | | | sync-kb-index.sh 落地 |
| ccc019-engine-gate-skip-metrics | 2 | **已合入 main**（2026-08-15）→ 可删 | | | | gate_skip metrics 落地 |
| ccc020-prompt-injection-dashboard | 4 | **待合入**（分支就绪，被主仓并发前端改动阻断 ff）→ 待办 | | | | /board/prompt_inject + read_prompt_inject_records |
| clw009-terminal-overhaul | 2 | 文档同步（无代码成果）→ 可删 | | | | clw README + 方案 |
| clw010-ui-rebuild | 8 | 已覆盖（main 已有跨机支持）→ 可删 | | | | approve-merge/validate-plans/docgate 等 |
| clw011-webview-settings | 2 | 文档同步 → 可删 | | | | clw README + 方案 |
| clw014-css-theme-rebuild | 1 | 文档同步 → 可删 | | | | clw 方案 |
| clw016-csp-config-hardening | 2 | 文档同步 → 可删 | | | | ccc/clw 方案 |
| clw017-eng-green-dispatch | 2 | 文档同步 → 可删 | | | | clw 方案 + 教训 |
| clw019-ui-role-inject-verify | 3 | 文档同步 → 可删 | | | | ccc/clw 方案 + 教训 |

> 2026-08-15 深审更新：此组 12 个分支中，5 个 ccc0xx 是真实代码成果（其中 ccc018/019 已合入、ccc020 待合入），其余 7 个 clw 分支是卡流程文档同步（方案/README），无独立代码成果，均可删。ccc016/017/clw010 的「独特文件」经核对是分支落后 main 的旧快照（main 已覆盖）。

---

## 二、历史 T* 任务卡（85 个 · Hub 时代遗留）

> 已禁发新 T 卡。处置：**归档不删**（迁 `docs/archive/`），保留可追溯结构。

清单：T-mapping、T1-server-skeleton、T1-R-server-skeleton-deep、T2-engine-core、T3-board-web、T3-R-board-state-normalize、T4-relay-mac2017、T4-R-deploy-hardcode-fix、T5-board-schedule、T6-roadmap-p3、T7-ops-timer-p4、T8-switch-checklist、T8-X-execute-switch、T9-kb-seed、T10-kb-init、T11-kb-mcp-semantic、T11-R-kb-closeout、T12-legacy-retire-list、T12-R-legacy-2017-audit、T13-server-http-api、T14-e2e-pipeline-test、T14-R-e2e-new-stack、T15-legacy-retire-exec、T16-shell-integration-api、T17-full-acceptance、T18-phase2-retire-exec、T19-shell-migration、T20-board-shell-migration、T21-ops-shell-migration、T22-deploy-2017、T23-http-direct-open、T24-desktop-repackage-web-chat、T24-R-desktop-protocol-align、T25-restore-legacy-chat、T26-desktop-backend-refactor、T26-R-self-audit-cleanup、T27-relay-2017-restart、T28-desktop-repackage、T29-chat-brain-agent、T30-http-refactor、T31-refactor-closeout-docs-baseline、T32-refactor-closeout-engine-real-dispatch、T33-refactor-closeout-hardcode-cluster、T34-refactor-closeout-deadcode-dual-shell、T35-refactor-closeout-hangover-regression、T36-m4-kb-seed-refresh、T37-m4-brain-kb、T38-m4-handoff-acceptance、T39-engine-dispatch-by-binding、T40-shell-base-3col-ui、T41-brain-mind-streaming、T42-dual-shell-e2e-acceptance、T43-conversation-long-poll、T44-shell-ux-optimization、T45-user-centric-ux-overhaul、T46-conversation-stability-sse、T47-project-thread-sidebar、T48-audit-report、T48-shell-problem-audit、T49-conversation-as-workflow、T50-dual-shell-e2e-acceptance、T51-knowledge-mcp-optimize、T52-automation-base、T53-console-roadmap-fix、T54-auto-naming-migration、T55-index-layer、T56-card-components、T57-big-small-cards、T58-board-refactor、T59-engine-parallel-relay-guard、T60-console-cockpit、T61-task-flow-linked、T62-archive-review、T63-nginx-entry、T64-engine-auto-worktree、T65-dual-shell-align、T66-card-format-debt、T67-deploy-race-guard、T68-http-resource-resilience、T69-release-engine-plist-rebuild、T70-audit-report、T70-code-audit、T71-fix-server-p0、T72-fix-desktop-p0、T76-conversation-base-hardening（85 个文件，含 T-mapping 说明）

---

## 三、已关闭历史卡（268 张）

> 处置：**归档不删**（迁 `docs/archive/`），流程产物留档。

## 四、业务仓残留 worktree（0 个）

> 2026-08-15 核查：2017 各业务仓 `.ccc-wt/` 下 5 个目录（cd/clw/mx/qb/xy）均为空目录，无残留 worktree。cd001-004 的 worktree 已在合入收口时清理。无需处理。

---

## 后续节奏（阶段 4/5 · 长期）

1. **阶段 2 归档**：T 卡 85 + 已关闭历史卡 268 → `docs/archive/`（待执行）。
2. **阶段 3 备份**：B 组 12 个分支导出 patch → `docs/archive/codex-branches/`（待执行）。
3. **观察期**：A 组 31 个分支 2026-08-22 到期复核；B 组备份后起算 14 天。
4. **每周五复核**到期项；**每次合入收口**顺手删新关闭卡分支。
5. **删除动作**：`git push origin --delete codex/<stem>`（确认无引用后）。
