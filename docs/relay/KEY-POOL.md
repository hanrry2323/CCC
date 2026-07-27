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

## 2. 免费 vs 收费（必须分清）

| | **免费 Zen** | **收费 OpenCode Go** |
|--|--------------|----------------------|
| 字段 | `billing: "zen-free"` · `free: true` | `billing: "opencode-go"` · `free: false` |
| API 根 | `https://opencode.ai/zen/v1` | **`https://opencode.ai/zen/go/v1`** |
| 典型模型 | `deepseek-v4-flash-free` · `big-pickle` | `deepseek-v4-flash` · `deepseek-v4-pro` |
| 命名 | `opencode-go-*` / `opencode-code-*` | `opencode-go-paid-flash` · `opencode-go-pro` |
| 优先级 | flash `tier_priority=1`（日常） | flash **`tier_priority=80`（末位兜底）** |
| 出口 | 直连 和/或 HK `:18080` | 一般直连即可（不依赖免费 IP 池） |
| 日限 | 免费额度 / 长 `Retry-After` | 走 Go 套餐配额（看 Go 控制台） |

**踩坑（已核实）**：Go 套餐钥若误配到 `zen/v1` + `deepseek-v4-flash`，会返回 **401 Insufficient balance**，看起来像「没钱」，其实是**端点错了**。必须 `zen/go/v1`。

---

## 2.1 503 根因与付费保底（2026-07-27）

进程 **LISTEN :4000** 仍可对 flash 回 **503**。常见不是「没配付费钥」，而是调度把付费排到墙钟之后：

| 旧坑 | 新策略（已落地） |
|------|------------------|
| 免费钥 `fetch` 挂 60–90s → `budget:wall`，paid 未试 | 单次上游硬超时 **15s**（`LOOP_UPSTREAM_ATTEMPT_MS`） |
| launchd `FAILOVER_MAX_MS=120000` / 12 次 | 默认 / 2017 plist：**90s / 8 次** |
| paid `tier_priority=80` 永远垫底 | free 失败 → **PaidGuarantee**；多数 free 长冷却 → **paid-first** |
| `fetch` 失败打 `provider_group` 整账号 120s | **禁止**；付费 fetch 冷却 **≤3s**；free fetch → 90s 灰名单 |
| 503 文案把未试 paid 写成「不可用」 | trail 可标 `paid_skipped_budget`；成功时 `X-Routed-Upstream: opencode-go-paid-flash` |
| 大上下文仍 503：trail 已点到 paid 也是 `fetch` | **勿**用 `CONNECT_MS` Abort 包整段 fetch；首包后 clearTimeout |
| trail 仍见 100s+ `fetch` | **peek 硬超时** free 10s / paid 25s；同请求按**出口**轮转 free（最多 4），勿一失败就钉 paid |
| 付费兜底仍 502/断流 | flash free 全死时 **last-resort 含短冷却 paid**；墙钟默认 **90s** / paid 首包 **70s**；SSE keepalive + peek 立刻 flush |

**验收口径**：人为关掉全部 free flash 后，`POST /v1/messages` flash 应 **200** 且 `X-Routed-Upstream` = paid。  
**看门狗（可选）**：`bash scripts/install-relay-flash-watchdog-plist.sh`（60s 探针，连续 3 次失败 kickstart）。

**勿做**：用 `?force=1` 清日额长冷却当「提稳」（只会反复撞 429）。

### 2026-07-27 活体结论（轮转 vs 断任务）

- 直连探针：`opencode-go-a..j` **全部** `429` + `Retry-After≈10h`（日配额真耗尽，不是路由漏选）。
- 此时正确行为 = **立刻走 `opencode-go-paid-flash`**，并用 keepalive/更长墙钟避免客户端掐死。
- 免费钥恢复后：affinity 若钉在 paid，路由应**重新优先 free**（paid 留末位保底）。

### 部署检查清单（2017）

```bash
cd ~/program/CCC/relay && npm test && npm run build
rsync -az dist/ mac2017:/Users/fan/program/CCC/relay/dist/   # 或在本机 2017 上 build
# 对齐 plist：FAILOVER_MAX_MS=90000 ATTEMPT_*=15s/70s PEEK_*=10s/25s STALL_IDLE_MS=30000
launchctl kickstart -k "gui/$(id -u)/com.ccc.relay.2017"
# 验收：小 ping + 大 body（~100KB）+ LAN；trail 禁止再出现 ~100s 的 *:fetch
curl -sS 'http://127.0.0.1:4000/admin/trail?limit=10'
curl -sS 'http://127.0.0.1:4000/admin/usage?period=1h' | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('cache_hit_ratio'), d.get('cached_tokens'))"
```

## 3. 现行拓扑（逻辑，不含密钥）

```
Desktop / Claude  ──►  2017 relay :4000
                         │
                         ├─ flash: zen-free 多钥（直连 + HK）prio=1
                         │         └─ 耗尽后 → opencode-go-paid-flash (Go) prio=80
                         ├─ Pro:   opencode-go-pro (Go · deepseek-v4-pro)
                         └─ code:  **Go 套餐** `opencode-go-paid-code`
                                   （`zen/go/v1` + `deepseek-v4-flash`；与 paid-flash/pro 同钥）
                                   旧 `opencode-code-a..d` 误配 zen/v1 后改 Go 仍无支付方式 → 已禁用
```

- **HK**：`com.ccc.hk-egress-tunnel` → `proxy: http://127.0.0.1:18080`（仅免费钥轮换出口）  
- **Engine OpenCode**：本机 `:4002` · `OPENCODE_MODEL=loop/code`  
- **DeepSeek V4 thinking（硬 · 2026-07-27）**：Go `deepseek-v4-*` 默认 thinking 会令 `content=""`、只填 `reasoning_content` → OpenCode 空转 hang。所有 Go 上游须带  
  `request_overrides: { "thinking": { "type": "disabled" } }`（主机 `~/.ccc/relay/upstreams.json`，**不进 git**）。改后 curl `model=code` 应见非空 `content`。  
- **fail-open**：客户端另认 `CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url`（与钥池正交）

---

## 4. upstreams.json 建议字段

每条上游除原有字段外，约定：

| 字段 | 含义 |
|------|------|
| `billing` | `zen-free` \| `opencode-go` \| `zhipu-failover` |
| `account` / `account_family` | 账号标签（如 `Tai223_1` / `Tai223`） |
| `lane` | `direct` \| `hk` |
| `free` | 与 billing 一致 |
| `description` | `[FREE-ZEN]` / `[PAID-GO]` 开头，便于 admin 一眼区分 |

---

## 5. 加钥流程（Cursor / 运维）

1. 人把新 `sk-` 交给 Cursor（本会话或新 Relay 会话）。  
2. Cursor **只**写 2017 `~/.ccc/relay/upstreams.json`（并刷新 `KEY-INVENTORY.md`）。  
3. 免费：`zen/v1` + `*-free`/`big-pickle`；收费 Go：`zen/go/v1` + 付费模型名。  
4. `kickstart` relay；探针 + `POST /v1/messages` 烟测。  
5. **不要** `git commit` 任何含 `sk-` 的文件。

---

## 6. 常用命令（在 2017 上）

```bash
# 状态
launchctl print "gui/$(id -u)/com.ccc.relay.2017" | head -40
lsof -nP -iTCP:4000 -sTCP:LISTEN

# 用量
curl -sS 'http://127.0.0.1:4000/admin/usage?period=1h' | python3 -m json.tool | head
curl -sS 'http://127.0.0.1:4000/admin/usage?period=1d' | python3 -m json.tool | head
curl -sS http://127.0.0.1:4000/admin/cooldowns | python3 -m json.tool

# flash 看门狗（单次）
bash ~/program/CCC/scripts/ccc-relay-flash-watchdog.sh
# 安装 60s launchd
bash ~/program/CCC/scripts/install-relay-flash-watchdog-plist.sh

# 烟测
curl -sS -m 30 -D - -o /dev/null http://127.0.0.1:4000/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}' | grep -iE 'HTTP/|X-Routed|X-Fallback'
