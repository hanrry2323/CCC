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
| G2 / P-B | **未证** | 本轮未触发 OpenCode `code` 真 commit |
| G3 / P-F | **接近** | Ops P0–P2 已合入；本轮未点灯验收 |
| G4 / P-C | **未证** | 缺 Desktop 定稿小 epic → 全程 verdict→released |
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

## 变更记录

| 日期 | 作者 | 摘要 |
|------|------|------|
| 2026-07-27 | Cursor | 首建；M1/2017 基线探针；P-C 未开跑（待 Desktop 定稿） |
