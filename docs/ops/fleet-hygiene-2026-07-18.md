# 舰队卫生盘点 — 2026-07-18（v0.51 后）

> Cursor 通道执行 · **非** Engine 自消费。对齐 `docs/hygiene/PLAN-TEMPLATE.md` / R-15。  
> 探针原始数据：本机 `/tmp/fleet-inventory.json`（扫描时点）。  
> 可执行清理：[fleet-cleanup-playbook-2026-07-18.md](./fleet-cleanup-playbook-2026-07-18.md)

## 1. 可靠性结论（v0.51 orch 分离）

| # | 检查 | 结果 |
|---|------|------|
| R1 | Registry CCC `role=orch` `engine=false` | **PASS** |
| R2 | `list_engine_paths` = 7 apps，无 CCC | **PASS** |
| R3 | Engine 日志「发现 7 个 workspace」、无 CCC | **PASS**（重启后） |
| R4 | launchd `engine` / `chat-server` / `board` 在跑 | **PASS** |
| R5 | Hub `default_project` ≠ ccc（实测 `hp`） | **PASS** |
| R6 | Hub 对 CCC 创建任务 → **400** + 编排仓文案 | **PASS** |
| R7 | `invent_hard_disabled=true` / `invent_allowed=false` | **PASS** |
| R8 | CLAUDE.md 与 R-15 / invent 硬关一致 | **FAIL → P0 修复**（见下） |
| R9 | Hub 未登记 `qx` 标 `engine_eligible` | **WARN**：Board 发现的 `qx` 仍显示 `eng=True`（易误导下达） |

**总评**：编排/消费分离运行面 **可用**；文档漂移与 Hub 对未登记仓的 `engine_eligible` 默认偏乐观，属维护缝。

### CLAUDE.md 漂移（P0）

| 位置 | 问题 |
|------|------|
| §Hub 基线 #6 | 「空板 → 写 epic」易被读成 **对 CCC 本体看板** 下发 |
| 控制面表 `invent` 行 | 仍写「全开 / 自造」，与硬关政策矛盾 |

应对：改写为「业务仓经 Hub 下达；CCC orch 禁止 Engine 消费 / invent 已退役」。

---

## 2. 舰队总表

登记：`~/.ccc/workspaces.json` schema 1.1 · doctor `errors=0` · apps(engine)=7 · orch=1

| name | path | role | eng | active | released | 入口 | 风险摘要 |
|------|------|------|-----|--------|----------|------|----------|
| CCC | `/Users/apple/program/CCC` | orch | F | 0 | 0 | CLAUDE+profile+state | CLAUDE 漂移；plans≈101；worktree 可 prune |
| xianyu | `/Users/apple/program/xianyu` | app | T | 0 | 4 | 根 stub→`.claude/CLAUDE` | `.DS_Store`；plans 67；ahead 1 |
| qb | `/Users/apple/program/projects/qb` | app | T | 0 | 14 | CLAUDE | `on-hold`×3；plans 64；**ahead 218**；`?? .credentials.note` |
| clawmed-ccc | `/Users/apple/program/clawmed-ccc` | app | T | 2 | 11 | CLAUDE | **done epic 可见** `task-dzgb` |
| ai-loop-router | `…/ai-loop-router` | app | T | 0 | 0 | CLAUDE+AGENTS | 干净；ahead 8；?? heartbeat |
| hp | `/Users/apple/program/hp` | app | T | 0 | 0 | CLAUDE+AGENTS | **`.bak-20260712-K23/`**；`.DS_Store` |
| Medio-0 | `/Users/apple/program/Medio-0` | app | T | 0 | 0 | CLAUDE+AGENTS | 干净；?? heartbeat |
| qxo | `/Users/apple/program/qx-observer` | app | T | 0 | 0 | CLAUDE→AGENTS | plans 107；`__pycache__`；多 worker worktree；ahead 66 |
| qx* | `/Users/apple/program/projects/qx` | 未登记 | — | 0 | 0 | 有 | Hub 可见；**保持零件库，不进 Engine** |

\* doctor WARN `hub_visible_not_in_engine_registry` — **决策：不 register**。

---

## 3. 分仓盘点

### 3.1 CCC（orch）

- **Board**：各列 0（符合不自消费）
- **膨胀**：plans≈101 · events≈98 · quarantines≈27
- **Worktrees**：2× prunable（`agent-a0b82a…`、`chat-v031-frontend`）；1× locked（`agent-ae7e…`）
- **冲突**：CLAUDE invent/epic 口径（上表）
- **Git**：与 `origin/main` 同步（扫描时）

### 3.2 xianyu

- **入口**：根 `CLAUDE.md` 已是跳转 stub → `.claude/CLAUDE.md`（**有意双文件，非脏冲突**）
- **垃圾**：`.DS_Store`、`.ccc/.DS_Store`；pids `*.done`×14
- **Git**：ahead 1；dirty heartbeat/stats

### 3.3 qb

- **Board**：released 14；**非标列 `on-hold/` ×3**（c01–c03）
- **敏感**：`?? .credentials.note`（**勿提交**）
- **Git**：ahead **218**（P3，另开）

### 3.4 clawmed-ccc

- **Board**：backlog 2（其一 `cla-b1-1-migrate-e2e` 已 `ui_hidden`；**`task-dzgb` done 仍可见**）
- **Git**：dirty（w2 released 过程文件）

### 3.5 ai-loop-router / Medio-0

- 入口齐、板空、无明显垃圾；仅 runtime `?? .ccc/engine-heartbeat.json` / `stats/`

### 3.6 hp

- **垃圾**：`.bak-20260712-K23/`（含 `config.py.bak` 等）；`.DS_Store`
- 无 README（非错误）

### 3.7 qxo（qx-observer）

- Hub 名 `qxo` / 路径 `qx-observer` — 别名自洽
- plans≈107；根 `__pycache__/`；`.DS_Store`
- worktrees：`/private/tmp/test-worktree-add` prunable；多个 `.qx-worker-*`
- Git：ahead 66；released 列大量删除未提交（脏）

---

## 4. 优先级总表

| Pri | 项 | 仓 | 本轮 |
|-----|-----|-----|------|
| P0 | 对齐 CLAUDE.md ↔ R-15 / invent 硬关 | CCC | **执行** |
| P0 | `task-dzgb` `ui_hidden=true` | clawmed | **执行** |
| P0 | 文档确认 `qx` 不登记 | 报告 | **写明** |
| P0 | Hub 未登记仓勿标 `engine_eligible=true` | CCC | **执行** |
| P1 | xianyu 双 CLAUDE | xianyu | 已合格，跳过 |
| P1 | 删 `.bak-20260712-K23/` | hp | **执行** |
| P1 | 清 `.DS_Store` / 根 `__pycache__` | 多仓 | **执行** |
| P1 | CCC `worktree prune` + 移除 prunable | CCC | **执行** |
| P2 | orphan plans 归档 | CCC/qxo/qb | **已执行** |
| P2 | qb `on-hold` 文档化 | qb | **已执行** |
| P2 | heartbeat/stats `.gitignore` | apps+CCC | **已执行** |
| P3 | `.credentials.note` 删除+gitignore | qb | **已执行** |
| P3 | ahead 推送 | qb/qxo/… | **执行 push** |

---

## 5. 验收（执行 P0–P1 后复核）

- [x] Doctor：无 `done_epic_visible`（仅剩 qx WARN）
- [x] Engine 仍 7 apps（本轮未再重启；既有进程已跳过 CCC）
- [x] CLAUDE 对齐 R-15 / invent 硬关
- [x] Hub 未登记仓 `engine_eligible=false`（含 qx）
- [x] hp `.bak-*` 已删；多仓 `.DS_Store` / qxo `__pycache__` 已清
- [x] CCC prunable worktrees 已移除（locked 保留）
