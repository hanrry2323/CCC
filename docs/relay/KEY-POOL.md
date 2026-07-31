# CCC Relay 钥池手册（无密钥）

> **权威主机**：Mac2017（编排面）· `com.ccc.relay.2017` · `:4000` / `:4002`  
> **运行配置（含密钥）**：2017 本机 `~/.ccc/relay/upstreams.json`（`chmod 600`）  
> **完整密钥清单（仅 2017 本机）**：`~/.ccc/relay/KEY-INVENTORY.md`（`chmod 600`，**禁止进 git / 禁止同步到公开仓**）  
> **M1**：`com.ccc.relay.m1` 为旁路；Desktop / 个人 Claude **默认打 2017** `http://192.168.3.116:4000`  
> **冲突以** [`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「个人主路线 / 模型通道简规 / CCC Relay」为准。

---

## 1. 从哪里入手（给未来的你 / Cursor）

| 要做什么 | 去哪 |
|----------|------|
| 改上游钥 / 启用哪一把付费 | **SSH `mac2017`** → 编辑 `~/.ccc/relay/upstreams.json` → `launchctl kickstart -k "gui/$(id -u)/com.ccc.relay.2017"` |
| 看现在有哪些钥、账号、尾缀 | 2017：`less ~/.ccc/relay/KEY-INVENTORY.md` |
| 看冷却 / 清短冷却 | `GET/POST http://127.0.0.1:4000/admin/cooldowns`（`?force=1` 全清） |
| 探针当前启用 Go | `LOOP_UPSTREAMS_FILE=~/.ccc/relay/upstreams.json node ~/program/CCC/relay/scripts/probe-opencode-go.mjs` |
| 部署 / plist | [`DEPLOY-2017.md`](DEPLOY-2017.md) |

**红线**：密钥只进 `~/.ccc/relay/*`；仓内文档只写账号名 / `key_tail` / 角色，**永不写完整 `sk-`**。

---

## 2. Flash · 付费-only（硬 · 2026-07-28）

**Claude Code + OpenCode 一律打 `flash` / `loop/flash`。** `:4000` 与 `:4002` 共用同一 flash 上游表。`Pro` / `code` **轮空**。个人 Codex（知识席）可走 `:4002` `/v1/responses`，非产线主路径。

Relay = **薄垫片**（协议翻译 + `thinking` 关 + 固定上游），不是多厂商调度站。

### 三目标（硬 · 2026-07-28）

| 目标 | 口径 |
|------|------|
| **快** | 单活跃钥 → **跳过 stream peek**（`LOOP_STREAM_PEEK` 默认关）；瞬态冷却不挡 sole 钥；`PEEK_*` 默认 3s（仅多钥排障时才用）；**出站连接池不限**（undici `connections=null`；入站不设 `maxConnections`） |
| **缓存** | 每请求打 Go `enable_prompt_cache` + `prompt_cache_retention=24h` + sticky `prompt_cache_key`；KPI `upstream_cache_token_ratio` ≥0.9 |
| **稳定** | 协议 shim + 直连 Go；禁止 free 池 / IP 轮换 / short-cool 空转；sole 失败不 `markBad` 自杀 |

多钥 failover peek：**仅** `LOOP_STREAM_PEEK=1` 排障时开。

| | **现行启用池** | **备份（禁用）** | **禁止启用** |
|--|----------------|------------------|--------------|
| 角色 | 恰好 **1** 把 Go 付费 | 第 2 把 Go 付费 | 免费 Zen / GLM / MiniMax / 其它厂商 |
| 字段 | `billing: "opencode-go"` · `free: false` · `enabled: true` | 同左 · `enabled: false` | `zen-free` / `zhipu-*` / MiniMax |
| API 根 | **`https://opencode.ai/zen/go/v1`** | 同左 | — |
| 模型 | `deepseek-v4-flash` | 同左 | `*-free` 等 |
| 出口 | **仅直连**（**禁止** `proxy` / HK） | 同左 | — |
| 换钥 | — | **人通知后**把备份改 `enabled:true`、旧钥改 `false` | — |

**踩坑**：Go 套餐钥若误配到 `zen/v1` + `deepseek-v4-flash` → **401 Insufficient balance**。必须 `zen/go/v1`。

**踩坑（大 Write / 长 tool 流 · 2026-07-31）**：Claude 在 ~50k 上下文后一次性 `Write` 整文件时，上游 Go 常需 1～3 分钟吐 tool_args。旧默认 `FAILOVER_MAX_MS=45s`×2 ≈90s、`STALL_IDLE_MS=30s` 会误杀 → 客户端 `API error · Retrying`。现行默认：`FAILOVER_MAX_MS=180000`、`LOOP_UPSTREAM_ATTEMPT_PAID_MS=90000`、`LOOP_HEADERS_TIMEOUT_MS=120000`、`STALL_IDLE_MS=120000`（`install-relay-plist.sh` + dist 默认；M1/2017 同构）。

**踩坑（IPv6 · 2026-07-28）**：本网到 `opencode.ai` **IPv6 黑洞**（`curl -6` 超时、`curl -4` 秒级通）。Node `verbatim` 先 AAAA → 2017 Relay 表现为 sole flash `attempt timeout`、请求挂死。修复：`dist` 内 `preferIpv4Dns` + undici `connect.family=4`；plist `NODE_OPTIONS=--dns-result-order=ipv4first`；超时后 **recycleDirectAgent** 清半开 keep-alive。**M1 / 2017 须同构**（同 `proxy.js` + 同 plist 环境变量）；勿只 kickstart 不重装 plist。

**踩坑（客户端误指 LAN · 2026-07-28）**：M1 上 Claude / OpenCode / Codex **必须**打本机 `127.0.0.1:4000` / `:4002`。若仍写 `192.168.3.116:4000|4002`，会在 2017 卡死时把 Desktop/运维席一起拖成「连不上」，并反向打挂编排面 Relay。

**IP 轮换退役**：`proxy` 视为遗留，flash **不得**再配。

**已退役教法（勿再写现行）**：免费打头、PaidGuarantee、free-first、同会话双付费 RR、MiniMax 主力。

---

## 2.1 单活跃钥 + 缓存 KPI

| 策略 | 口径 |
|------|------|
| 启用数 | flash 付费 `enabled=true` **恰好 1** |
| 会话 | 单钥 = 天然钉；亲和键可用 `x-session-id` / system+**首条** user |
| 禁 | 双付费同时 `enabled`；自动 RR 切备份；复活免费池 |
| KPI | `upstream_cache_token_ratio=cached/prompt`；活跃付费会话目标 **≥0.9** |

**验收**：`POST /v1/messages` model=`flash` → **200** 且 `X-Routed-Upstream` = 当前启用的 paid。  
同 `x-session-id` / 稳定 `prompt_cache_key` 连打 ≥5 轮：`cache_read / (input_tokens + cache_read)` 目标 **≥0.9**。  
Codex `/v1/responses`：Relay 会把 `previous_response_id` 钉到同一 `prompt_cache_key`；换钥后前几轮冷缓存属正常。  
看 OpenCode 账单时：**大 prompt 数 ≠ 全价**——要看 cache hit / 实价；Relay KPI：`/admin/usage` 的 `upstream_cache_token_ratio`。

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
                                    └─ flash: 恰好 1× opencode-go-paid-* (Go · deepseek-v4-flash)
                                              （另 1 把备份 enabled=false，人切）
                                    Pro / code: 轮空
                                    免费 / MiniMax: 不进启用池
```

`:4002` 另提供 `POST /v1/responses`（Responses→chat 垫片；个人 OpenAI 兼容客户端可选，**非 CCC 产线主路径**；四席里对应 Codex 知识/聊天席）。

- **DeepSeek V4 thinking（硬）**：Go 上游须 `request_overrides: { "thinking": { "type": "disabled" } }`  
- **fail-open**：`CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url`（与钥池正交）  
- **HK 隧道**：勿写回 upstreams `proxy`

---

## 4. upstreams.json 建议字段

| 字段 | 含义 |
|------|------|
| `billing` | 现行启用只认 `opencode-go` |
| `account` / `account_family` | 账号标签 |
| `free` | 启用行必须 `false` |
| `enabled` | 付费备份用 `false`；免费行一律 `false` 或删除 |
| `description` | `[PAID-GO]` / `[PAID-GO·BACKUP]` / `[DISABLED-FREE]` |
| ~~`proxy` / `lane`~~ | **退役**；勿再写 |

---

## 5. 加钥 / 切备份（Cursor / 运维）

1. 人把新 `sk-` 交给 Cursor，或通知「切到备份钥」。  
2. Cursor **只**写 2017 `~/.ccc/relay/upstreams.json`（并刷新 `KEY-INVENTORY.md`）。  
3. 新/备份 Go：`zen/go/v1` + `deepseek-v4-flash` + thinking disabled；**全局仅一把** `enabled:true`。  
4. `kickstart` relay；`POST /v1/messages` 烟测。  
5. **不要** `git commit` 任何含 `sk-` 的文件。  
6. **不要**为「省钱」重新启用免费池。

---

## 6. 常用命令（在 2017 上）

```bash
launchctl print "gui/$(id -u)/com.ccc.relay.2017" | head -40
lsof -nP -iTCP:4000 -sTCP:LISTEN

curl -sS 'http://127.0.0.1:4000/admin/usage?period=1h' | python3 -m json.tool | head
curl -sS http://127.0.0.1:4000/admin/cooldowns | python3 -m json.tool

curl -sS -m 30 -D - -o /dev/null http://127.0.0.1:4000/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"ok"}]}'
```
