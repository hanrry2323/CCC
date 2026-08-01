# CCC Relay 中转站 · 会话移交包（付费-only · 2026-07-28）

> **用途**：维护中转站时的开场 SSOT。  
> **2026-08-01 更新**：CCC 仓内 `relay/` 已拆出，Mac2017 不再运行 relay 实例。  
> 使用独立项目 `~/program/ai-loop-router`（M1，端口 4100/4102）。Mac2017 通过 LAN 连接。  
> **权威**：[`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「模型通道简规 / CCC Relay」· [`docs/relay/KEY-POOL.md`](../relay/KEY-POOL.md)  
> **代码**：`~/program/ai-loop-router/` · 运行配置：M1 `~/.ccc/relay/upstreams.json`（**禁止进 git**）  
> **封印证据（史）**：[`2026-07-28-relay-flash-seal.md`](./2026-07-28-relay-flash-seal.md)

---

## 0. 开场指令

```text
你是 Cursor 平台助手，专责 CCC Relay（薄垫片）。
读本文件 + authority「模型通道简规」+ KEY-POOL.md。
主业：Flash 付费-only（Claude+OpenCode 一律 flash/loop/flash）、
恰好 1 把启用 Go paid（第 2 把备份人切）、cache KPI、cooldown；
Pro/code 轮空；免费/MiniMax 不进启用池；IP/HK 出口轮换已退役。
不要跑金路径/看板/Ops UI，除非阻塞中转站。
改码只动 ~/program/ai-loop-router/ 与相关 launchd/脚本；合入前 vitest；热更 kickstart M1。
密钥只动 ~/.ccc/relay/upstreams.json，永不提交。
```

---

## 1. 现行拓扑（硬）

```
Desktop / Claude / OpenCode  ──►  M1 ai-loop-router :4100 / :4102
                                    │
                                    └─ flash: 恰好 1× Go paid (zen/go/v1 · deepseek-v4-flash)
                                              （第 2 把备份 enabled=false，人切）
                                    Pro / code: 轮空（enabled:false；pro→回落 flash）
                                    免费 / MiniMax: 不进启用池
```

| 主机 | 服务 | 端口 | 说明 |
|------|------|------|------|
| M1 | `com.ai-loop-router` | `:4100` Anthropic · `:4102` OpenAI chat | **唯一 relay 实例**；钥 SSOT |
| Mac2017 | — | — | 通过 `http://192.168.3.140:4100` 连接 M1 relay |
| M1 | Hub 隧道 | `127.0.0.1:17777` | **与 relay 无关** |

**已退役（勿恢复为 flash 主路径）**：HK `:18080` 出口轮换、`proxy` 字段挂 flash、OpenCode `loop/code` / xfyun 默认、真三档并行主业。  
**CCC 仓内 relay/ 已拆出**（2026-08-01），`com.ccc.relay.m1` / `com.ccc.relay.2017` plist 已退役。

---

## 2. 单活跃付费 + 缓存（摘要）

| 项 | 口径 |
|----|------|
| 启用池 | flash 付费 `enabled=true` **恰好 1**；第 2 把备份 `enabled=false` |
| 免费 / MiniMax | **不进启用池**（已退役现行教法） |
| 换钥 | 额度用尽 → **人通知后**手动切备份 |
| KPI | `upstream_cache_token_ratio=cached/prompt`；活跃会话目标 **≥0.9** |
| thinking | Go/`deepseek-v4-*` → `request_overrides.thinking.type=disabled` |
| 禁 | 双付费同时 enabled；flash 挂 `proxy`；复活免费打头 |

验收清单见 KEY-POOL §2.1。（旧 PaidGuarantee/free-first 仅作史，见 seal brief）

---

## 3. 协作

| 工作 | 谁 |
|------|-----|
| 活体排障 / kickstart / 改钥 | **M1 本机**（或 SSH） |
| relay TS + vitest | Cursor（本开程不用 Claude 草稿工） |
| 金路径 / 板面 | 另轨；与中转站正交 |

---

## 4. 常用命令（M1）

```bash
launchctl kickstart -k "gui/$(id -u)/com.ai-loop-router"
curl -sS -m 5 -X POST 'http://127.0.0.1:4100/admin/cooldowns/clear'
curl -sS -m 30 -D - -o /dev/null http://127.0.0.1:4100/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}' \
  | grep -iE 'HTTP/|X-Routed|X-Fallback'
curl -sS 'http://127.0.0.1:4100/admin/usage?period=1h' | python3 -m json.tool | head
cd ~/program/ai-loop-router && npm test
```

探活：**勿**用 Anthropic `GET /health`（易 404 假红）；用 `POST /v1/messages` / admin / dashboard。

## Mac2017 上验证

```bash
curl -sS http://192.168.3.140:4100/admin/status | head -5
```

---

## 5. 验收句（Flash 封印）

1. M1 flash `POST /v1/messages` 稳定 200；关全部 free 后仍 200 且 `X-Routed-Upstream`=paid。  
2. 同 `x-session-id` 多轮后 `upstream_cache_token_ratio` 接近/≥0.9（付费钉会话）。  
3. OpenCode / Engine 默认 **`loop/flash`**（非 xfyun、非 loop/code）。  
4. flash upstreams **无** `proxy`；启用 Go paid **恰好 1**（另 1 备份 `enabled=false`）；thinking disabled。  
5. `npm test` 绿；dist 热更 + kickstart；Mac2017→M1 LAN 烟测 OK。

证据：[`2026-07-28-relay-flash-seal.md`](./2026-07-28-relay-flash-seal.md)。

---

## 6. 史（勿当现行）

2026-07-27 曾用半直连+半 HK、code 专钥、`OPENCODE_MODEL=loop/code`。已由 `128129a` Flash-only 推翻。细节仅作排障考古，**禁止**写回 upstreams `proxy` 或恢复 code 主路径。