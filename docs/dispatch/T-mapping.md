# T 卡 → 项目前缀映射表（T54 命名规则落地）

> **用途**：历史 T1–T54 卡**不批量重命名**（保持 git 历史），本表是「全局编号 → 新规则命名」的唯一参考。
> 旧卡引用仍写 `T<N>`（如 `T39`）；**新卡一律** `<前缀><三位序号>-<slug>.md` 且放 `docs/dispatch/<前缀>/` 子目录。
> 规则配套：`server/board/validate.py`（命名门禁）· `scripts/new-card.sh`（新卡生成）· `server/board/loader.py`（子目录扫描）。
> 本文件为说明文档（无 `# 任务卡` 卡头），loader/Engine 不把它当任务卡。
>
> **前缀表唯一事实源**：[`docs/projects/registry.yaml`](../projects/registry.yaml)（见 [`DOC-PROTOCOL.md`](../DOC-PROTOCOL.md)）。  
> 下表为 registry 的**可读摘要**；增删前缀只改 registry（+ 档案 README），勿只改本文件。

## 前缀表

| 前缀 | 项目 | 说明 |
|------|------|------|
| `qb` | qb | QB（2017 `/Users/fan/program/apps/qb`） |
| `ccc` | CCC | 本仓 |
| `mx` | medio-0 | 2017 `/Users/fan/program/apps/medio-0` |
| `xy` | xianyu | 2017 `/Users/fan/program/apps/xianyu` |
| `hp` | 知识库 | 2017 `/Users/fan/program/apps/hp` |
| `tst` | 临时测试 | 临时/验收占位卡，**禁止合入 main** |

### 禁止走 CCC（硬 · 2026-08-06）

| 前缀 | 项目 | 说明 |
|------|------|------|
| ~~`qh`~~ | QuantHive | **禁止** CCC 出卡 / Engine 派发 / 看板自动开发。独立轨道（M1 `ZCodeProject/QuantHive`）。门禁：`FORBIDDEN_CARD_PREFIXES` + `new-card.sh` 拒 `qh` |

> 前缀=子目录名=文件名前缀，三者一致；编号在同一前缀内唯一（`<前缀><NNN>` 全目录唯一）。

## 历史卡映射（T1–T54）

| 全局 | 原卡文件名 | 新命名 | 说明 |
|------|-----------|--------|------|
| T1 | T1-server-skeleton.md | ccc001-server-skeleton | — |
| T1 | T1-R-server-skeleton-deep.md | ccc002-server-skeleton-deep | R 变体（复盘/重构） |
| T2 | T2-engine-core.md | ccc003-engine-core | — |
| T3 | T3-board-web.md | ccc004-board-web | — |
| T3 | T3-R-board-state-normalize.md | ccc005-board-state-normalize | R 变体（复盘/重构） |
| T4 | T4-relay-mac2017.md | ccc006-relay-mac2017 | — |
| T4 | T4-R-deploy-hardcode-fix.md | ccc007-deploy-hardcode-fix | R 变体（复盘/重构） |
| T5 | T5-board-schedule.md | ccc008-board-schedule | — |
| T6 | T6-roadmap-p3.md | ccc009-roadmap-p3 | — |
| T7 | T7-ops-timer-p4.md | ccc010-ops-timer-p4 | — |
| T8 | T8-switch-checklist.md | ccc011-switch-checklist | — |
| T8 | T8-X-execute-switch.md | ccc012-execute-switch | X 变体（专项） |
| T9 | T9-kb-seed.md | ccc013-kb-seed | — |
| T10 | T10-kb-init.md | ccc014-kb-init | — |
| T11 | T11-kb-mcp-semantic.md | ccc015-kb-mcp-semantic | — |
| T11 | T11-R-kb-closeout.md | ccc016-kb-closeout | R 变体（复盘/重构） |
| T12 | T12-legacy-retire-list.md | ccc017-legacy-retire-list | — |
| T12 | T12-R-legacy-2017-audit.md | ccc018-legacy-2017-audit | R 变体（复盘/重构） |
| T13 | T13-server-http-api.md | ccc019-server-http-api | — |
| T14 | T14-e2e-pipeline-test.md | ccc020-e2e-pipeline-test | — |
| T14 | T14-R-e2e-new-stack.md | ccc021-e2e-new-stack | R 变体（复盘/重构） |
| T15 | T15-legacy-retire-exec.md | ccc022-legacy-retire-exec | — |
| T16 | T16-shell-integration-api.md | ccc023-shell-integration-api | — |
| T17 | T17-full-acceptance.md | ccc024-full-acceptance | — |
| T18 | T18-phase2-retire-exec.md | ccc025-phase2-retire-exec | — |
| T19 | T19-shell-migration.md | ccc026-shell-migration | — |
| T20 | T20-board-shell-migration.md | ccc027-board-shell-migration | — |
| T21 | T21-ops-shell-migration.md | ccc028-ops-shell-migration | — |
| T22 | T22-deploy-2017.md | ccc029-deploy-2017 | — |
| T23 | T23-http-direct-open.md | ccc030-http-direct-open | — |
| T24 | T24-desktop-repackage-web-chat.md | ccc031-desktop-repackage-web-chat | — |
| T24 | T24-R-desktop-protocol-align.md | ccc032-desktop-protocol-align | R 变体（复盘/重构） |
| T25 | T25-restore-legacy-chat.md | ccc033-restore-legacy-chat | — |
| T26 | T26-desktop-backend-refactor.md | ccc034-desktop-backend-refactor | — |
| T26 | T26-R-self-audit-cleanup.md | ccc035-self-audit-cleanup | R 变体（复盘/重构） |
| T27 | T27-relay-2017-restart.md | ccc036-relay-2017-restart | — |
| T28 | T28-desktop-repackage.md | ccc037-desktop-repackage | — |
| T29 | T29-chat-brain-agent.md | ccc038-chat-brain-agent | — |
| T30 | T30-http-refactor.md | ccc039-http-refactor | — |
| T31 | T31-refactor-closeout-docs-baseline.md | ccc040-refactor-closeout-docs-baseline | — |
| T32 | T32-refactor-closeout-engine-real-dispatch.md | ccc041-refactor-closeout-engine-real-dispatch | — |
| T33 | T33-refactor-closeout-hardcode-cluster.md | ccc042-refactor-closeout-hardcode-cluster | — |
| T34 | T34-refactor-closeout-deadcode-dual-shell.md | ccc043-refactor-closeout-deadcode-dual-shell | — |
| T35 | T35-refactor-closeout-hangover-regression.md | ccc044-refactor-closeout-hangover-regression | — |
| T36 | T36-m4-kb-seed-refresh.md | ccc045-m4-kb-seed-refresh | — |
| T37 | T37-m4-brain-kb.md | ccc046-m4-brain-kb | — |
| T38 | T38-m4-handoff-acceptance.md | ccc047-m4-handoff-acceptance | — |
| T39 | T39-engine-dispatch-by-binding.md | ccc048-engine-dispatch-by-binding | — |
| T40 | T40-shell-base-3col-ui.md | ccc049-shell-base-3col-ui | — |
| T41 | T41-brain-mind-streaming.md | ccc050-brain-mind-streaming | — |
| T42 | T42-dual-shell-e2e-acceptance.md | ccc051-dual-shell-e2e-acceptance | — |
| T43 | T43-conversation-long-poll.md | ccc052-conversation-long-poll | — |
| T44 | T44-shell-ux-optimization.md | ccc053-shell-ux-optimization | — |
| T45 | T45-user-centric-ux-overhaul.md | ccc054-user-centric-ux-overhaul | — |
| T46 | T46-conversation-stability-sse.md | ccc055-conversation-stability-sse | — |
| T47 | T47-project-thread-sidebar.md | ccc056-project-thread-sidebar | — |
| T48 | T48-shell-problem-audit.md | ccc057-shell-problem-audit | — |
| T49 | T49-conversation-as-workflow.md | ccc058-conversation-as-workflow | — |
| T50 | T50-dual-shell-e2e-acceptance.md | ccc059-dual-shell-e2e-acceptance | — |
| T51 | T51-knowledge-mcp-optimize.md | ccc060-knowledge-mcp-optimize | — |
| T52 | T52-automation-base.md | ccc061-automation-base | — |
| T53 | T53-console-roadmap-fix.md | ccc062-console-roadmap-fix | — |
| T54 | T54-auto-naming-migration.md | ccc063-auto-naming-migration | — |

> 变体说明：同全局编号的 R/X 变体卡在旧目录保留原名（如 `T1-R-server-skeleton-deep.md`），
> 新命名用**连续序号**区分（`ccc001` / `ccc002`），slug 去掉 R/X 标记，查历史以「原卡文件名」列为准。
