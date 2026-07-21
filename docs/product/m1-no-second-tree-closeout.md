# M1 无业务第二树 — 清扫收口（史 · 2026-07-21）

> **状态**：已落地史实，**不是**日常真理 SSOT。  
> **现行事实权威**：[`loop-engineer-authority.md`](loop-engineer-authority.md)（透镜 / 四权威 / 工程师模式）。  
> **日常心智**：[`desktop-agent-handoff.md`](desktop-agent-handoff.md)。

---

## 为什么清（背景）

双机曾同时存在「对话瘦 clone」与 2017 权威仓。对齐基线若再引导本机 `Read`/`git status`，会与 Hub 快照打架。  
清扫完成后，日常只读 **loop-engineer-authority**，勿再复制「现行真理」到本文。

---

## 已执行清扫（M1 · 记录）

| 项 | 处置 |
|----|------|
| `~/program/apps/<业务>` | 删除（目录留空） |
| 顶层 `hp` / `xianyu` 等 | 删除 |
| `archive/2026-07-20-m1-freeze` | 删除（~18G） |
| `com.qb.*` / `com.hp*` / `com.hp-kb.*` / `com.mavis.hp-kb-tunnel` | bootout → `~/.ccc/retired/launchagents-2026-07-21/` |
| Desktop `sessions/` | 清空 |
| `~/.ccc/loop-code/{projects,sessions,…}` | 清空（保留 `CLAUDE.md` + `settings.json`） |
| `~/.claude` | → `~/.ccc/retired/claude-home-2026-07-21/` |
| `ccc.localWorkspaceMap` | 仅 `{"ccc":"/Users/apple/program/CCC"}` |

**保留**：`/Users/apple/program/CCC`（Cursor 改平台）。

---

## 代码 / 纪律跟进

| 落点 | 变化 |
|------|------|
| `_project_baseline.baseline_prompt_for_claude` | 以 Hub 快照为唯一事实；禁止本机 git/Read 再核实业务仓 |
| `hub_voice` / `DISCUSS_TOOL_DISCIPLINE` / `QuickPrompts` | 同上 |
| Desktop `AppModel.localPath` | 业务仓无映射 → `nil`；禁止全局路径冒充业务 cwd |
| `desktop/scripts/configure-desktop.sh` | **不再** rsync 业务仓到本机 |

---

## 验收清单（2026-07-21 实测）

- [x] `ls ~/program/apps` 无业务子目录；无 `archive/2026-07-20-m1-freeze`
- [x] `defaults read com.ccc.desktop ccc.localWorkspaceMap` 仅 `ccc` → 本机 CCC
- [x] `test ! -e ~/.claude`；sidecar `config_dir=~/.ccc/loop-code`
- [x] Hub baseline（2017 本机 curl）：含 Mac2017 / 第二树 / 禁止再核实；**不含** `git log -5`
- [x] sidecar：`project_path` 指向已删 `apps/ccc-demo` → 403；平台仓 cwd 短聊确认「只信 Hub 基线」
- [x] `pytest`：`test_dual_port_shell` / `test_hub_voice` / `test_v41_closed_loop` 通过
- [x] 文档：handoff / layout / runbook / identity / INDEX 收口页已更新；`configure-desktop.sh` 不再拉业务仓

---

## 相关入口

| 文档 | 用途 |
|------|------|
| [`loop-engineer-authority.md`](loop-engineer-authority.md) | 事实权威 + Hub 只读透镜 + 旁路收死 |
| [`desktop-agent-handoff.md`](desktop-agent-handoff.md) | Agent 日常短交接 |
| [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) | 对话/编排边界 |
| [`../deploy/server-layout.md`](../deploy/server-layout.md) | 2017 目录规范 |
| [`../deploy/fleet-apps-migration-2026-07.md`](../deploy/fleet-apps-migration-2026-07.md) | 舰队迁移（含 07-21 清扫注记） |
| [`loop-code-ownership-cut.md`](loop-code-ownership-cut.md) | Desktop 独占 loop-code |
