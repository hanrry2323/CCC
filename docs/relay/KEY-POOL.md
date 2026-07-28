# CCC Relay 钥池手册（无密钥）

> **权威主机**：Mac2017（编排面）· `com.ccc.relay.2017` · `:4000` / `:4002`  
> **运行配置（含密钥）**：2017 本机 `~/.ccc/relay/upstreams.json`（`chmod 600`）  
> **完整密钥清单（仅 2017 本机）**：`~/.ccc/relay/KEY-INVENTORY.md`（`chmod 600`，**禁止进 git / 禁止同步到公开仓**）  
> **M1**：`com.ccc.relay.m1` 为旁路；Desktop / 个人 Claude **默认打 2017** `http://192.168.3.116:4000`  
> **冲突以** [`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「CCC Relay」为准。

---

## 1. 从哪里入手（给未来的你 / Cursor）

| 要做什么 | 去哪 |
|----------|------|
| 改上游钥 / 免费·收费分流 | **SSH `mac2017`** → 编辑 `~/.ccc/relay/upstreams.json` → `launchctl kickstart -k "gui/$(id -u)/com.ccc.relay.2017"` |
| 看现在有哪些钥、账号、尾缀 | 2017：`less ~/.ccc/relay/KEY-INVENTORY.md` |
| 看冷却 / 清短冷却 | `GET/POST http://127.0.0.1:4000/admin/cooldowns`（`?force=1` 全清） |
| 探针免费 Zen | `LOOP_UPSTREAMS_FILE=~/.ccc/relay/upstreams.json node ~/program/CCC/relay/scripts/probe-opencode-go.mjs` |
| 部署 / plist | [`DEPLOY-2017.md`](DEPLOY-2017.md) |
| 会话移交包 | [`docs/briefs/2026-07-27-relay-handoff.md`](../briefs/2026-07-27-relay-handoff.md) |

**红线**：密钥只进 `~/.ccc/relay/*`；仓内文档只写账号名 / `key_tail` / 角色，**永不写完整 `sk-`**。

---

## 2. Flash 单通道（硬 · 2026-07-28）

**Claude Code + OpenCode 一律打 `flash` / `loop/flash`。** `:4000` 与 `:4002` 共用同一 flash 上游表。`Pro` / `code` **轮空**（配置可留、`enabled:false`）。

| | **免费（打头）** | **收费 OpenCode Go（兜底 ×2）** |
|--|------------------|--------------------------------|
| 字段 | `billing: "zen-free"` / `zhipu-failover` · `free: true` | `billing: "opencode-go"` · `free: false` |
| API 根 | `https://opencode.ai/zen/v1`（或智谱等） | **`https://opencode.ai/zen/go/v1`** |
| 典型模型 | `deepseek-v4-flash-free` · GLM-4.7 · `big-pickle` | `deepseek-v4-flash` |
| 优先级 | `tier_priority=1` | `tier_priority=80` |
| 出口 | **仅直连**（**禁止** `proxy` / HK 轮换） | 直连 |
| 调度 | 钥级**快速轮换**（短 attempt） | 墙钟内必试；成功后 **pinPaid** |

**踩坑（已核实）**：Go 套餐钥若误配到 `zen/v1` + `deepseek-v4-flash`，会返回 **401 Insufficient balance**。必须 `zen/go/v1`。

**IP 轮换退役**：旧「半直连 + 半 HK `:18080`」会打冷 prompt cache，已拆除。`proxy` 字段视为遗留，flash **不得**再配。

---

## 2.1 PaidGuarantee + 缓存（2026-07-28）

| 策略 | 口径 |
|------|------|
| 新会话 | **free-first**，免费钥快切 |
| 免费耗尽 / 墙钟逼近 | 插队两把 Go 付费之一 |
| 付费成功 | **钉 paid** TTL≈24h（free 恢复也不 unpin） |
| 亲和键 | `x-session-id` / `x-request-id`，否则 system+**首条** user |
| 禁 | 同会话双付费 RR；last-2-user 亲和；按出口封 sibling |
| KPI | `upstream_cache_token_ratio=cached/prompt`；付费钉会话目标 **≥0.9** |

默认：`FAILOVER_MAX_MS=45s` / free attempt **8s** / paid **25s** / peek 6s·12s。

**验收**：人为关掉全部 free flash 后，`POST /v1/messages` flash 应 **200** 且 `X-Routed-Upstream` = paid。  
同 `x-session-id` 连打 ≥5 轮（大 system + 累积 messages）：付费钉会话  
`cache_read / (input_tokens + cache_read)` 目标 **≥0.9**（Anthropic 口径下 `input_tokens` 已扣缓存）。

### 部署检查清单（2017）

```bash
cd ~/program/CCC/relay && npm test && npm run build
rsync -az dist/ mac2017:/Users/fan/program/CCC/relay/dist/
bash scripts/install-relay-plist.sh 2017
launchctl kickstart -k "gui/$(id -u)/com.ccc.relay.2017"
curl -sS 'http://127.0.0.1:4000/admin/trail?limit=10'
curl -sS 'http://127.0.0.1:4000/admin/usage?period=1h' | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('upstream_cache_token_ratio'), d.get('l1_hit_rate'))"
```

## 3. 现行拓扑（逻辑，不含密钥）

```
Desktop / Claude / OpenCode  ──►  2017 relay :4000 / :4002
                                    │
                                    └─ flash: zen-free 多钥（直连，快切）+ GLM 等
                                              └─ 耗尽 → 2× opencode-go-paid-* (Go · deepseek-v4-flash)
                                    Pro / code: 轮空
```

- **DeepSeek V4 thinking（硬）**：Go 上游须 `request_overrides: { "thinking": { "type": "disabled" } }`  
- **fail-open**：`CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url`（与钥池正交）  
- **HK 隧道**：不再作为 flash 必需；可保留作它用，但 **勿** 写回 upstreams `proxy`

---

## 4. upstreams.json 建议字段

| 字段 | 含义 |
|------|------|
| `billing` | `zen-free` \| `opencode-go` \| `zhipu-failover` |
| `account` / `account_family` | 账号标签 |
| `free` | 与 billing 一致 |
| `description` | `[FREE-ZEN]` / `[PAID-GO]` / `[FREE-ZHIPU]` 开头 |
| ~~`proxy` / `lane`~~ | **退役**；勿再写 |

---

## 5. 加钥流程（Cursor / 运维）

1. 人把新 `sk-` 交给 Cursor（本会话或新 Relay 会话）。  
2. Cursor **只**写 2017 `~/.ccc/relay/upstreams.json`（并刷新 `KEY-INVENTORY.md`）。  
3. 免费：`zen/v1` + `*-free` / GLM → **`tier=flash`**；收费 Go：`zen/go/v1` + 付费模型名 → flash prio=80（最多 2 启用）。  
4. `kickstart` relay；探针 + `POST /v1/messages` 烟测。  
5. **不要** `git commit` 任何含 `sk-` 的文件。

---

## 6. 常用命令（在 2017 上）

```bash
launchctl print "gui/$(id -u)/com.ccc.relay.2017" | head -40
lsof -nP -iTCP:4000 -sTCP:LISTEN

curl -sS 'http://127.0.0.1:4000/admin/usage?period=1h' | python3 -m json.tool | head
curl -sS http://127.0.0.1:4000/admin/cooldowns | python3 -m json.tool

curl -sS -m 30 -D - -o /dev/null http://127.0.0.1:4000/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}' | grep -iE 'HTTP/|X-Routed|X-Fallback'
```
