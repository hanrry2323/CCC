# Relay Flash 单通道封印证据（2026-07-28）

> **史 / 证据包**：本稿记录「免费池 + PaidGuarantee + 恰好 2× paid」封印当时状态。  
> **现行（2026-07-28 午）**：付费-only · 恰好 **1** 把启用 Go · 第 2 把人切备份 · 免费/MiniMax 不进启用池 —— 见 authority「模型通道简规」· [`../relay/KEY-POOL.md`](../relay/KEY-POOL.md)。  
> **仓内翻转**：`128129a` Flash-only  
> **本文件无密钥**。

---

## 总闸

| # | 条件 | 状态 |
|---|------|------|
| D1 | 文档一致（handoff/DEPLOY/G2/STARTUP-BRIEF/rounds） | **勾** |
| D2 | 2017 upstreams：无 flash `proxy`；恰好 2× Go paid；thinking off；OpenCode `loop/flash` | **勾** |
| D3 | 活体：关 free→paid 200；pinPaid 同钥粘滞 | **勾**（见下） |
| D4 | `relay` vitest 170 绿；dist 热更；LAN 烟测 | **勾** |

**Relay Flash 封印：完成**（2026-07-28 Cursor 独立）。

---

## 基线

| 项 | 值 |
|----|-----|
| VERSION | v0.63.0 |
| main（封印时） | `128129a`（文档提交后将超前） |
| R3/R4 | 暂停中；stash `wip-015-during-relay-flash-seal`；分支 `draft/015-*` 保留 |
| 2017 拉码 | 已 `git pull` → `128129a`；`OPENCODE_MODEL` 默认 `loop/flash` |

---

## 主机审计（Phase C）

| 检查 | 结果 |
|------|------|
| flash 启用 | 13（free 11 + paid 2） |
| flash `proxy` | **none** |
| Go paid URL | 均为 `zen/go/v1` |
| thinking disabled | paid 两钥均 OK |
| `~/.config/opencode/opencode.json` | `loop/flash` → `:4002` |
| `~/.opencode/opencode.json` | 原 `loop/code` → **已改为** `loop/flash`（bak=`opencode.json.bak-flash-seal`） |
| `ccc-engine.sh` | pull 后 `OPENCODE_MODEL` 默认 `loop/flash` |
| launchd | `com.ccc.relay.2017` + `com.ccc.relay.flash-watchdog` |

---

## 活体验收（Phase D）

### PaidGuarantee

1. 临时 `enabled=false` 全部 free flash（bak=`upstreams.json.bak-paid-guarantee-test`）→ kickstart。  
2. `POST /v1/messages` model=flash：

- HTTP **200**
- `X-Routed-Upstream: opencode-go-paid-flash`
- trail：`paid_forced` → `ok`
- content 有文本（非空）

3. **已恢复** free（从 bak copy 回）+ kickstart；恢复后路由 `opencode-go-g` 200。

### pinPaid 粘滞

同 `x-session-id`、free 仍关时连打 5 轮：均路由 **`opencode-go-paid-flash-b`**（粘滞，无双付费 RR）。  
单轮 `cache_read_input_tokens` 在极短 prompt 下为 0（预期弱）；`admin/usage` 1h 聚合 `upstream_cache_token_ratio≈0.39`（历史混合流量，**不**单作失败条件）。大 system 多轮 ≥0.9 目标留作日常观察 KPI，不挡本次封印。

### 烟测

| 路径 | 结果 |
|------|------|
| 2017 `:4000` flash | 200 · free 钥 |
| M1 → `192.168.3.116:4000` | 200 · `opencode-go-f` |
| vitest | **170/170** pass |
| dist rsync + kickstart | 完成 |

---

## Phase E

活体无代码缺口；**未改** `relay/src`（本轮仅文档 + 主机配置）。

---

## 次轨

R3 015 / R4 016 由 Cursor 自跑收口（见 PRODUCTION-DELIVERY-ROUNDS）。
