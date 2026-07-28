# CCC Relay 中转站 · 会话移交包（2026-07-27）

> **用途**：新开「专门维护中转站」的 Cursor 对话时，把本文件当开场 SSOT 附件。  
> **权威**：冲突以 [`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「CCC Relay」「三档契约 + 上游解耦」为准。  
> **代码根**：`relay/`（TS）· 运行配置：`~/.ccc/relay/upstreams.json`（**禁止进 git**）· 部署：[`docs/relay/DEPLOY-2017.md`](../relay/DEPLOY-2017.md)  
> **钥池手册（无密钥）**：[`docs/relay/KEY-POOL.md`](../relay/KEY-POOL.md)  
> **完整密钥清单**：仅 Mac2017 `~/.ccc/relay/KEY-INVENTORY.md`（0600；Cursor 运维会话保管，禁止进 git）

---

## 0. 开场指令（粘到新对话）

```text
你是 Cursor 平台助手，专责 CCC Relay（中转站）。
读 docs/briefs/2026-07-27-relay-handoff.md + authority「CCC Relay」。
本会话主业：Flash 单通道（Claude+OpenCode 一律 flash）、免费快切+双付费钉缓存、cooldown；
Pro/code 轮空；IP/HK 出口轮换已退役。不要跑金路径/看板/Ops UI 抛光，除非阻塞中转站。
改码只动 relay/ 与相关 launchd/脚本；合入前 vitest；热更后 kickstart 2017+M1。
密钥只动 ~/.ccc/relay/upstreams.json，永不提交。
```

> **2026-07-28 拓扑翻转**：主对接仅 flash；OpenCode=`loop/flash`；IP 轮换退役。详见 [`KEY-POOL.md`](../relay/KEY-POOL.md)。

---

## 1. 协作结论（答「自己弄 vs Cloud」）

| 工作类型 | 谁做 | 为什么 |
|----------|------|--------|
| **活体排障**（503/卡住/cooldown/双机探活/kickstart） | **本会话 Cursor 自己弄** | 要 SSH 2017、读 launchd/日志、清 cooldown、改本机配置；Cloud/草稿工看不见真机 |
| **有边界的代码包**（fallback 策略、admin API、单测） | Cursor 主导；可选 **个人 Claude 草稿工** 在 `draft/*` 分支写 TS+vitest | 适合「小 diff + 测绿」；**不适合** Cloud Agent 当合入主路径 |
| **金路径 / Engine / 板面假绿** | **另开会话**（或本会话明确切题） | 与中转站正交；混在一起烧上下文 |

**暂不用 Cloud Agent 做中转站主业**：双机状态、密钥、fail-open 红线、launchd 生命周期都在真机；Cloud 隔离仓合不了这套。  
**个人 Claude Code**：可继续当 `relay/` 草稿工（feature branch），Cursor 审合入 + 双机热更。

---

## 2. 复盘（这一程中转站相关）

### 已发生

1. **客户端「网络错误 / 503」≠ 进程挂了**  
   常见根因：OpenCode Zen **免费钥 429**（长 `Retry-After`）→ breaker 进 **cooldown**；付费档余额不足。  
   急救：`POST http://127.0.0.1:4000/admin/cooldowns/clear`（在 **2017**）。

2. **Desktop / 个人 Claude 默认走 2017 编排面**  
   `http://192.168.3.116:4000`（共享 flash 免费池 + HK `:18080`）。  
   M1 `com.ccc.relay.m1` 存在，但是旁路/备份，不是对话默认。

3. **探活口径易假红**  
   anthropic 模式 **`GET /health` → Not found**；应以 fleet probe / `POST /v1/messages` / admin / dashboard 为准。

4. **金路径暴露：OpenCode 仍钉 `xfyun/code`**  
   权威已写 **xfyun 退役、code=Zen 免费池**；2017 `~/.config/opencode/opencode.json` 仍 `"model": "xfyun/code"` → Engine 写码通道与中转站契约脱节（G2 未满分）。

5. **2026-07-27 13:33 活体**：2017 `com.ccc.relay.2017` **LISTEN :4000 但请求超时**（卡死）；err 日志大量 `opencode-go*` breaker。需 **kickstart** 恢复（移交时已尝试重启，新会话先再探一次）。

### 红线（不可协商）

- **fail-open**：relay 挂了客户端必须能降级直连，禁止 block 任务。  
- 下游只认逻辑名 **`flash` / `Pro` / `code`**；厂商 URL/key 只在 `upstreams.json`。  
- 换上游 = 改配置 + 重启 relay，**不改** Desktop/Engine 硬编码。

---

## 3. 拓扑速查

| 主机 | 服务 | 端口 | 生命周期 |
|------|------|------|----------|
| M1 | `com.ccc.relay.m1` | `:4000` | 同 sidecar |
| 2017 | `com.ccc.relay.2017` | `:4000` anthropic · `:4002` openai-chat | 同 Engine |
| 2017 | `com.ccc.hk-egress-tunnel` | `:18080` | code/flash 部分上游 `proxy` |
| M1 Desktop | Hub 隧道 | `127.0.0.1:17777` → 2017 Hub | **与 relay 无关**；勿混 |

配置：`~/.ccc/relay/upstreams.json`（0600）  
日志：`~/.ccc/logs/ccc-relay-2017.{out,err}.log`  
仓内：`relay/src/{fallback,tiers,router,admin,server}.ts`

常用：

```bash
# 2017
launchctl kickstart -k "gui/$(id -u)/com.ccc.relay.2017"
curl -sS -m 5 -X POST http://127.0.0.1:4000/admin/cooldowns/clear
curl -sS -m 15 http://127.0.0.1:4000/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}'

# M1 → 2017 LAN
curl -sS -m 15 http://192.168.3.116:4000/v1/messages ...同体...

# 单测（M1 仓）
cd relay && npm test
```

---

## 4. 下一步方案（按优先级）

### 钥池梳理（2026-07-27 13:52 · 本会话）

用户交付 **10** 把 Zen 免费钥（5 账号）。已写入 **2017** `~/.ccc/relay/upstreams.json`（M1 全直连备份）。**禁止进 git**。

| 账号 | 钥数 | 用途（现行） | 出口 |
|------|------|--------------|------|
| hanrry2323 | 3 | flash×1 + code×2 | flash 直连；code 直连+HK |
| 苹果 | 2 | flash×2 | 1 直连 + 1 HK（HK 钥今日已长冷却，prio↓） |
| github tai | 2 | flash×1 + code×1 | flash HK（今日长冷却）；code big-pickle 直连 |
| Hanrry212 | 1 | flash×1 | HK（新） |
| Hanrry322 | 2 | flash×1 + code×1 | flash 直连（新）；code big-pickle HK |
| **Tai223** | 2 | flash×2（`go-g`/`go-h`） | 1 HK + 1 直连 · **14:18 追加** |
| **Bbd223** | 2 | flash×2（`go-i`/`go-j`） | 1 HK + 1 直连 · **14:18 追加** |
| **Go 付费**（`...HP6Ul`） | 1 | `opencode-go-paid-flash` + `opencode-go-pro` | **`https://opencode.ai/zen/go/v1`**（非 zen/v1）；flash prio=80 末位兜底；Pro 启用 |

> 注意：普通 `zen/v1` + `deepseek-v4-flash` 对该钥会 401；必须走 **Go** 端点。

flash 启用合计 **10**（含降权旧 HK）。新 4 钥探针全 OK；relay flash 烟测 200。

**拓扑**：flash **3 直连 + 3 HK**；code **专钥**（不与 flash 共用，降互抢日额）。HK=`:18080` 隧道活体 OK。  
**探针**：6 条 flash 初始全 OK；随后旧 HK 钥 `go-d/e` 再触长 RA（~18h）属预期。  
**扩容建议**：若还要拉长稳定窗口，优先再注册 **2–4 个新账号** 专补 **HK 车道**（旧 HK 钥今日额度已空）；同账号堆多钥收益有限。

### P0 — 503 PaidGuarantee（2026-07-27 16:10 · 已落地）

**根因**：LISTEN 仍 503 —— 免费钥慢死吃光墙钟，`opencode-go-paid-flash` 未试到；偶发 fetch 把 paid 与整账号一起惩罚；plist 曾 `FAILOVER=120s/12`。

**代码**：`PaidGuarantee`（fallback）+ `boostPaidCandidates`（router）+ 单次尝试 15s + fetch 不 trip breaker + 付费 ≤10s 冷却。默认 `FAILOVER_MAX_MS=35000` / `ATTEMPTS=6`。vitest 160 绿。

**2017 热更**：dist rsync + plist env 已改 + kickstart。验收：关掉全部 free flash → `X-Routed-Upstream: opencode-go-paid-flash` 200；LAN 同。

**看门狗**：`com.ccc.relay.flash-watchdog`（60s）已装；连续 3 次 flash 失败 kickstart。

文档：`docs/relay/KEY-POOL.md` §2.1 · authority「PaidGuarantee」。

1. **确认 2017 relay 活**：LISTEN + `POST /v1/messages` flash 有响应；卡死则 kickstart，查 err 是否又刷 breaker。  
   → **2026-07-27 本会话**：kickstart 后本机 flash/Pro/code 均 200；LAN 偶发超时仍见（卡死看门狗仍 P1）。
2. **cooldown 策略**：免费池 429 时清 cooldown 是否过猛；评估「长 Retry-After 勿反复 trip 同一 key」或 dashboard 可见剩余冷却。  
   → **已落地**：429+RA>120s 按日配额采纳完整 RA；`POST /admin/cooldowns/clear` 默认保留 left>300s（`?force=1` 全清）；`GET /admin/cooldowns` 列表。活体：`go-e` 65819s 保留验证通过。
3. **钥池健康**：哪些 `opencode-go*` 日额耗尽；HK 出口钥 vs 直连钥分开看。  
   → 部分 HK 钥长冷却中；直连钥仍可服务 flash。

### P1 — 本周（对齐权威 G2）

4. **OpenCode 默认模型**：2017 `opencode.json` 从 `xfyun/code` → relay **`code`**（Zen `big-pickle` + flash-free 备份）；Engine 热更后金路径再证一笔 **真 code commit**。  
   → **已落地配置**：`model=loop/code` + `loop`→`:4002`；`OPENCODE_MODEL=loop/code` 在 Engine 进程环境；直连迁 `opencode.direct.json`。金路径真 commit 仍交金路径会话。
5. **探活统一**：fleet / Ops 勿用会 404 的 `/health`；文档与 `_ops_probe` 对齐。  
6. **卡死看门狗**：LISTEN 但 accept 不回 → launchd 或外部 probe 自动 kickstart（防 13:33 类静默挂）。  
   → **已装** `com.ccc.relay.flash-watchdog`（flash 503/超时路径）；进程假活但仍需偶发人工 `kickstart` 对照 err。
7. **残账**：stream body `h0:Rate limit`（无 HTTP 429/RA）仍短冷却——可后续从 SSE 错误体抽 RA。

### P2 — 可排期

7. admin/dashboard：cooldown 列表、上游 429/余额人话。  
8. fail-open 演练：停 2017 relay → Desktop/Engine 仍能降级（记证据到金路径或本 brief）。  
9. `DEPLOY-2017.md` 更新：去掉过时 MiniMax/xfyun 填法，改 Zen 三档。

### 明确不做（本中转站会话）

- Ops UI 抛光、packet 009 类壳工作  
- qb 业务 KPI / 全表 regress  
- 换平台 IDE；Cloud 当双机运维主控  

---

## 5. 与金路径会话的边界

| 会话 | 主业 | 交接点 |
|------|------|--------|
| **本文件 · Relay** | 通道可用、限流、模型路由、fail-open | G1/G2 绿灯后通知金路径会话 |
| **金路径 / Layer1** | epic→verdict→released、salvage/假绿 | 通道红时停测，甩回本会话 |

金路径残账（供对照，**不在本会话主修**）：salvage dirty 已修 `84f5e16`；P-B/P-C 部分；`verified→kb` 滞后；证据见 `docs/briefs/2026-07-27-golden-path-evidence.md`。

---

## 6. 验收句（本会话何时算阶段性完成）

1. M1 Desktop 经 `192.168.3.116:4000` 连续 `flash` 可用 ≥30min（或等价压测），429 时有可操作冷却/换钥路径。  
2. 2017 OpenCode / Engine 走 **`code`→Zen**，日志不再默认 `xfyun/code`。  
3. relay 卡死可自动或一键恢复；fail-open 演练有记录。  
4. 探活不再因 `/health` 404 报假红。
