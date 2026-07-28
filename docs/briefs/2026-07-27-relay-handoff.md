# CCC Relay 中转站 · 会话移交包（Flash 单通道 · 2026-07-28）

> **用途**：维护中转站时的开场 SSOT。  
> **权威**：[`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「CCC Relay」· [`docs/relay/KEY-POOL.md`](../relay/KEY-POOL.md)  
> **代码**：`relay/` · 运行配置：2017 `~/.ccc/relay/upstreams.json`（**禁止进 git**）  
> **封印证据**：[`2026-07-28-relay-flash-seal.md`](./2026-07-28-relay-flash-seal.md)  
> **部署**：[`docs/relay/DEPLOY-2017.md`](../relay/DEPLOY-2017.md)

---

## 0. 开场指令

```text
你是 Cursor 平台助手，专责 CCC Relay（中转站）。
读本文件 + authority「CCC Relay」+ KEY-POOL.md。
主业：Flash 单通道（Claude+OpenCode 一律 flash/loop/flash）、免费快切、
2×Go paid + pinPaid 保 cache、cooldown；Pro/code 轮空；IP/HK 出口轮换已退役。
不要跑金路径/看板/Ops UI，除非阻塞中转站。
改码只动 relay/ 与相关 launchd/脚本；合入前 vitest；热更 kickstart 2017。
密钥只动 ~/.ccc/relay/upstreams.json，永不提交。
```

---

## 1. 现行拓扑（硬）

```
Desktop / Claude / OpenCode  ──►  2017 relay :4000 / :4002
                                    │
                                    └─ flash 同池:
                                         free Zen (~10) + GLM 等直连快切
                                         └─ 耗尽/墙钟 → 恰好 2× Go paid (zen/go/v1)
                                              └─ 成功后 pinPaid ~24h（保 prompt cache）
                                    Pro / code: 轮空（enabled:false；pro→回落 flash）
```

| 主机 | 服务 | 端口 | 说明 |
|------|------|------|------|
| 2017 | `com.ccc.relay.2017` | `:4000` Anthropic · `:4002` OpenAI chat | **编排权威**；钥 SSOT |
| M1 | `com.ccc.relay.m1` | `:4000` | 旁路；Desktop/Claude **默认打 2017 LAN** |
| M1 | Hub 隧道 | `127.0.0.1:17777` | **与 relay 无关** |

**已退役（勿恢复为 flash 主路径）**：HK `:18080` 出口轮换、`proxy` 字段挂 flash、OpenCode `loop/code` / xfyun 默认、真三档并行主业。

---

## 2. PaidGuarantee + 缓存（摘要）

| 项 | 口径 |
|----|------|
| 墙钟 | `FAILOVER_MAX_MS=45s`；free attempt 8s；paid 25s；peek 6s/12s |
| 新会话 | free-first；仅 **zero 可用 free** 才 paid-first |
| 付费成功 | **pinPaid** TTL≈24h；亲和=`x-session-id` 或 system+**首条** user |
| 禁 | 同会话双付费 RR；flash 挂 `proxy`；按出口封 sibling |
| KPI | `upstream_cache_token_ratio=cached/prompt`；钉会话目标 **≥0.9** |
| thinking | Go/`deepseek-v4-*` → `request_overrides.thinking.type=disabled` |

验收清单见 KEY-POOL §2.1。

---

## 3. 协作

| 工作 | 谁 |
|------|-----|
| 活体排障 / kickstart / 改钥 | **本机 Cursor**（SSH 2017） |
| relay TS + vitest | Cursor（本开程不用 Claude 草稿工） |
| 金路径 / 板面 | 另轨；与中转站正交 |

---

## 4. 常用命令（2017）

```bash
launchctl kickstart -k "gui/$(id -u)/com.ccc.relay.2017"
curl -sS -m 5 -X POST 'http://127.0.0.1:4000/admin/cooldowns/clear'
curl -sS -m 30 -D - -o /dev/null http://127.0.0.1:4000/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}' \
  | grep -iE 'HTTP/|X-Routed|X-Fallback'
curl -sS 'http://127.0.0.1:4000/admin/usage?period=1h' | python3 -m json.tool | head
cd ~/program/CCC/relay && npm test
```

探活：**勿**用 Anthropic `GET /health`（易 404 假红）；用 `POST /v1/messages` / admin / dashboard。

---

## 5. 验收句（Flash 封印）

1. 2017 flash `POST /v1/messages` 稳定 200；关全部 free 后仍 200 且 `X-Routed-Upstream`=paid。  
2. 同 `x-session-id` 多轮后 `upstream_cache_token_ratio` 接近/≥0.9（付费钉会话）。  
3. OpenCode / Engine 默认 **`loop/flash`**（非 xfyun、非 loop/code）。  
4. flash upstreams **无** `proxy`；启用 Go paid **恰好 2**；thinking disabled。  
5. `npm test` 绿；dist 热更 + kickstart；M1→2017 LAN 烟测 OK。

证据：[`2026-07-28-relay-flash-seal.md`](./2026-07-28-relay-flash-seal.md)。

---

## 6. 史（勿当现行）

2026-07-27 曾用半直连+半 HK、code 专钥、`OPENCODE_MODEL=loop/code`。已由 `128129a` Flash-only 推翻。细节仅作排障考古，**禁止**写回 upstreams `proxy` 或恢复 code 主路径。
