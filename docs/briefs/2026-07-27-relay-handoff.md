# CCC Relay 中转站 · 会话移交包（2026-07-27）

> **用途**：新开「专门维护中转站」的 Cursor 对话时，把本文件当开场 SSOT 附件。  
> **权威**：冲突以 [`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「CCC Relay」「三档契约 + 上游解耦」为准。  
> **代码根**：`relay/`（TS）· 运行配置：`~/.ccc/relay/upstreams.json`（**禁止进 git**）· 部署：[`docs/relay/DEPLOY-2017.md`](../relay/DEPLOY-2017.md)

---

## 0. 开场指令（粘到新对话）

```text
你是 Cursor 平台助手，专责 CCC Relay（中转站）。
读 docs/briefs/2026-07-27-relay-handoff.md + authority「CCC Relay」。
本会话主业：flash/Pro/code 可用、cooldown/限流、fail-open、OpenCode code 模型对齐 Zen；
不要跑金路径/看板/Ops UI 抛光，除非阻塞中转站。
改码只动 relay/ 与相关 launchd/脚本；合入前 vitest；热更后 kickstart 2017+M1。
密钥只动 ~/.ccc/relay/upstreams.json，永不提交。
```

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

### P0 — 当天（可用性）

1. **确认 2017 relay 活**：LISTEN + `POST /v1/messages` flash 有响应；卡死则 kickstart，查 err 是否又刷 breaker。  
2. **cooldown 策略**：免费池 429 时清 cooldown 是否过猛；评估「长 Retry-After 勿反复 trip 同一 key」或 dashboard 可见剩余冷却。  
3. **钥池健康**：哪些 `opencode-go*` 日额耗尽；HK 出口钥 vs 直连钥分开看。

### P1 — 本周（对齐权威 G2）

4. **OpenCode 默认模型**：2017 `opencode.json` 从 `xfyun/code` → relay **`code`**（Zen `big-pickle` + flash-free 备份）；Engine 热更后金路径再证一笔 **真 code commit**。  
5. **探活统一**：fleet / Ops 勿用会 404 的 `/health`；文档与 `_ops_probe` 对齐。  
6. **卡死看门狗**：LISTEN 但 accept 不回 → launchd 或外部 probe 自动 kickstart（防 13:33 类静默挂）。

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
