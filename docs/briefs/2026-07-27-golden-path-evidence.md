# 金路径证据日志（Layer1 · 2026-07-27）

> **目的**：记录平台生产级（P-A…P-F / G1–G6）探针与断点；**UI 草稿合入不写入本文件当绿**。  
> **路线**：[`2026-07-27-ccc-production-readiness.md`](./2026-07-27-ccc-production-readiness.md)  
> **候选业务仓**：`qb`（主样板）· 备选小仓 `ccc-demo`  
> **纪律**：业务 epic 须 Desktop 定稿 → transfer；**禁止** Cursor 对 orch 投卡；**禁止** invent。

---

## 2026-07-27 · 基线探针（Cursor）

### 主机与控制面

| 检查 | 结果 | 备注 |
|------|------|------|
| M1 `control.json` | `mode=ui` · `host_role=m1_dialogue` | 预期：本机无 Engine |
| 2017 `control.json` | `mode=enabled` · invent 硬关 · `queue_consumer_only` | 预期：只消费队列 |
| 2017 Engine launchd | `state=running` | fleet 行 `com.ccc.engine` loaded |
| M1 fleet | relay.m1 / hub-tunnel / agent-sidecar **green** | OVERALL green |
| 2017 fleet | relay.2017 / board / chat-server / hk-egress / engine **loaded** | OVERALL green |

### 连通

| 检查 | 结果 | 断点？ |
|------|------|--------|
| `127.0.0.1:17777/`（隧道→Hub） | HTTP 200 HTML | 隧道通 |
| `127.0.0.1:7777`（M1 直连） | Connection refused | **预期**（Hub 不在 M1） |
| Sidecar `:7788/health` | `ok:true` · loop-code | G1 局部绿 |
| Sidecar `/api/projects` | 含 `qb`/`ccc-demo` 等 · `engine_eligible` | 列项通（反代） |
| 隧道 `/api/desktop/projects` | **401 Unauthorized** | 断点：Desktop/隧道鉴权与 sidecar 默认无 auth 不一致，排查时勿当「Hub 挂了」 |
| Hub `/api/health`（17777 与 2017:7777） | **404** | 断点：健康探针路径需对齐（勿用错 path 判死） |
| 2017 relay `:4000/health` | anthropic 模式 Not found | 用正确探活（fleet probe 已 up） |

### qb 板面快照（权威仓 `/Users/fan/program/apps/qb`）

| 列 | 文件数 |
|----|--------|
| backlog | 74 |
| planned / in_progress / testing / verified | 0 |
| released | 90 |

- 近 verdict：2026-07-24 stress-kpi 系列（非本轮产品意图）。  
- **活跃板计数**须滤 `ui_hidden` / epic `split_status=done` — 74 backlog **不能**直接当待办。  
- 空闲 + invent 硬关 → Engine 闲置**正常**；新工作须 Desktop 定稿下达。

### 金路径勾选（本轮）

| ID | 状态 | 证据 / 断点 |
|----|------|-------------|
| G1 / P-A | **部分** | sidecar health 绿；≥30min 无假死 **未跑** |
| G2 / P-B | **部分** | v2：OpenCode 写戳记 + DoD recommit `48027564`（非 OC 自 commit） |
| G3 / P-F | **接近** | Ops P0–P2 已合入；本轮未点灯验收 |
| G4 / P-C | **接近** | v2：verdict PASS + released + epic done（Hub transfer，非 Desktop 点选） |
| P-D | **未证** | 未造 FAIL 收尸演练 |
| G5 / P-E | **部分** | 隧道+fleet 绿；健康 path/401 口径需修文档或探针 |
| G6 | **部分** | 本提交落三层出门；patrol 全日跑另记 |

---

## 断点清单（下一程优先修 / 证）

1. **P-C 主断点**：在 Desktop 选 `qb` 或 `ccc-demo`，定一个**小而硬**意图（带可执行探针）→ transfer → 跟到 `released` + verdict 落盘 → `ccc-board.py regress`。  
2. **健康探针口径**：统一 Hub/relay health URL，避免 404 假红。  
3. **隧道 API 401**：与 sidecar 无 auth 默认对齐说明或 Desktop 凭证路径。  
4. **qb backlog 僵尸**：活跃计数滤完后再报「待办」；清幽灵轨走 board_ops / 当前会话，不靠卫生 epic 当主业。  
5. **P-B**：金路径上必须出现真实 OpenCode `code` commit（非 mock / 非 script_seed  alone 冒充写码通道，除非意图本就 script_seed）。

---

## 下一笔金路径建议（给人点的意图草案 · 非已下达）

**仓**：优先 `ccc-demo`（小）验证平台；通过后再用 `qb` 挂业务探针。  
**意图形状**：单文件/单脚本可验收；验收命令进白名单；禁止散文。  
**成功标准**：板面 tid + `verdicts/<tid>.verdict.md` + regress 绿 → 记入本文件新日期节。

---

## 2026-07-27 · qb 金路径实跑（Cursor）

| 项 | 值 |
|----|-----|
| 仓 | `qb` `/Users/fan/program/apps/qb` |
| epic | `ccc-qb-paper-0e331d93` |
| work | `ccc-qb-paper-0e331d93-w1` |
| 意图 | 写入 `docs/reports/ccc-layer1-golden-path.md`（含 `GOLDEN_PATH_OK`） |

### 过程断点（真问题）

1. **product 扇出挂死**：`claude --model flash` 长时间 0% CPU；杀进程后 Engine 才继续。  
2. **标题含「探针」→ transfer 强制 `executor=python`**，script_seed 短路径抢走写报告卡。  
3. **`no-script-seed` 标签假阳**：blob 子串匹配 `script-seed`（已修 `script_seed.py` + 单测）。  
4. **script_seed 假绿进 verified/released**：未写 `GOLDEN_PATH_OK` 时仍 deterministic pass；戳记后由人工 commit `fbecbc16` 补上。  
5. **无 `verdicts/<tid>.verdict.md`**：短路径审测未落 hollow+verdict 文件 → **P-C 未真过**。  
6. **全量 `ccc-board.py regress` 误伤**：一次扫出 20 张回归卡；已 `board-repair archive`（`ui_hidden`）清场。

### 勾选（诚实）

| ID | 状态 | 说明 |
|----|------|------|
| P-B | **未证** | 未出现 OpenCode `code` 真写码 commit（被 script_seed 短路） |
| P-C | **未证** | 虽 `released` + epic `split_status=done`，缺 verdict/hollow；属假绿路径 |
| 探针 | **局部** | `DRY_RUN=true python3 scripts/paper_intent_probe.py --env paper` → PASS |
| 戳记 | **有** | `docs/reports/ccc-layer1-golden-path.md` 含 `GOLDEN_PATH_OK` |

### 下一笔（qb）

- 标题**禁止**单独「探针」字样（用「文档戳记 / 报告」）；`executor_intent=opencode` 且验收探针不要触发整卡 python 强制。  
- 跟到 **verdict 文件落盘** 才勾 P-C。  
- regress **只对目标 tid**，禁止无过滤全表 released。

---

## 2026-07-27 · qb 金路径 v2（OpenCode + 真戳记）

| 项 | 值 |
|----|-----|
| 仓 | `qb` `/Users/fan/program/apps/qb` |
| epic | `layer1-v2-966d70fa` → `split_status=done` |
| work | `layer1-v2-966d70fa-w1` → **released** |
| 意图 | 写入 `docs/reports/ccc-layer1-golden-path-v2.md`（含 `GOLDEN_PATH_OK_V2`） |
| transfer | Hub `executor_intent=opencode`（标题「文档戳记」） |
| 戳记 commit | `48027564` — `layer1-v2-966d70fa-w1 phase=1: auto-commit by CCC DoD gate` |
| 先前假绿 | `4814756a` script_seed 仅写 `PENDING`；WT 已有 `GOLDEN_PATH_OK_V2` 时 salvage 曾归因旧 hash |

### 过程断点（真问题 → 已修/残留）

1. **salvage WT 假绿（已修 `84f5e16`）**：acceptance 在脏工作树绿、task commit 仍 `PENDING` → 现拒绝 `acceptance_uncommitted_vs_commit`，并对仍脏的 plan scope **DoD recommit**。  
2. **script_seed 仍先落 PENDING**：`4814756a` 消息含 `paper_intent_probe via script_seed`（与 docs 戳记意图不符）——下一程收紧 script_seed 触发。  
3. **OpenCode 模型仍 `xfyun/code`**：进程被 salvage 收口时 SIGTERM；交付内容由 OpenCode 写 WT，**git 落盘靠 DoD**，非 OpenCode 自带 commit。  
4. **verified→kb 滞后**：审测后卡 verified；`verified → testing` pullback 被板拒绝；kb 未在同 tick 自动跟上，本轮 **手动 `kb_role()`** 后才 `released` + epic `done`。  
5. **Engine 热更**：平台 Python 修复须 `launchctl kickstart -k …/com.ccc.engine`，否则仍跑旧 salvage。

### 勾选（诚实）

| ID | 状态 | 说明 |
|----|------|------|
| P-B | **部分** | OpenCode 写出戳记；commit=`48027564` 为 DoD auto-commit（含 `GOLDEN_PATH_OK_V2`）。非「OpenCode CLI 自己 commit」满分。 |
| P-C | **部分→接近** | `verdicts/…w1.verdict.md` PASS + `released` + epic `done` + acceptance 对 **HEAD 戳记** 绿。非 Desktop UI 点选，属 Hub transfer 实跑。 |
| 戳记 | **有** | HEAD 含独立行 `GOLDEN_PATH_OK_V2` |
| 平台修 | **已合入** | `84f5e16` salvage dirty-vs-commit |

### 下一程

- **指令包 [`010-golden-path-kb-script-seed`](../dev-packets/010-golden-path-kb-script-seed.md)**（Claude 草稿 → Cursor 合入）：`verified→testing` + 每 tick kb + script_seed 勿抢 opencode。  
- OpenCode 默认模型对齐 relay `code`（停 `xfyun/code`）— **Cursor 双机配置，不进 010**。  
- 010 合入并 Engine 热更后，再证 P-B：OpenCode 自 commit（或明确把 DoD recommit 记为合法落地口径）。

---
