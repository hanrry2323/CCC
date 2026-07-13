# AI Loop Router v4.0 — 架构定案

## 一、定位

单机 AI 请求网关。一台 M1 上跑，把 Claude Code / qx-observer / xianyu 等下游的 LLM 请求路由到 minimax / opencode / xfyun / zhipu 等多个上游，按 tier 自动降级。

**核心指标**：不僵尸、不丢冷却、不跑漏内存、不因配置写坏而瘫痪。

---

## 二、架构原则

| 原则 | 说明 |
|------|------|
| 单进程双端口，按协议分端口 | 4000（Anthropic）+ 4002（OpenAI）双端口独立监听，不合并 |
| 进程管理用 PM2 | 不再裸 launchd。PM2 `--wait-ready` + `kill-timeout: 15000` |
| 启动必检端口 | listen 前先 check 端口空闲，不硬抢 |
| 关停必 graceful | SIGTERM → drain → close → exit，不等 TIME_WAIT |
| 冷却持久化 | cooldown 状态写 `logs/cooldown.json`，重启恢复 |
| 配置原子写入 | 写 temp → rename，热重载不再读到半截 JSON |
| 内存有界 | usage 保留最近 7 天，log 环形缓冲区 10000 条 |
| 错误不沉默 | 每层必须有 fallback 或降级路径，不吞异常 |

---

## 三、模块结构

```
src/
├── server.ts          # 入口, HTTP server 生命周期
├── config.ts           # 配置加载 + 热重载 (原子写入感知)
├── router.ts           # tier 路由 + session affinity
├── fallback.ts         # 透明重试 (stream + non-stream)
├── health.ts           # 健康探针
├── tiers.ts            # tier 定义 + 可用性判定
├── scoring.ts          # 健康评分 + 指数退避
├── state.ts            # 共享内存状态 (用法/日志/冷却/分数)
├── admin.ts            # Admin API
├── dashboard.ts        # Dashboard HTML
├── cache.ts            # 缓存
├── auth.ts             # 客户端认证
├── usage.ts            # 用量持久化
├── http.ts             # HTTP 工具函数
├── types.ts            # 类型定义
├── protocols/
│   ├── messages.ts     # /v1/messages (Anthropic)
│   └── chat.ts         # /v1/chat/completions (OpenAI)
└── translator/
    ├── anthropic.ts    # Anhtropic ↔ OpenAI 格式转换
    └── openai-chat.ts  # OpenAI ↔ 通用
```

---

## 四、API 设计

### 4.1 下游端口

**双端口 4000 + 4002**，按协议分端口：

| 端口 | 路径 | 协议 |
|------|------|------|
| 4000 | `POST /v1/messages` | Anthropic Messages API |
| 4000 | `GET /admin/*` | Admin |
| 4000 | `GET /dashboard` | Dashboard |
| 4000 | `GET /healthz` | 存活检查 (PM2 --wait-ready 用) |
| 4002 | `POST /v1/chat/completions` | OpenAI Chat API |

### 4.2 /healthz 接口（PM2 就绪探测）

```
GET /healthz → 200 { "status": "ok" }  # server 就绪后开始响应
```

PM2 等待此接口返回 200 后才认为进程启动完成。用来防 EADDRINUSE。

---

## 五、模块职责

### 5.1 server.ts — 生命周期管理

```typescript
function main(): void {
  // 1. 双端口检测: 4000 (Anthropic) + 4002 (OpenAI) 各独立 tryListen
  //    每个端口退避重试 (最多 5 次), 一个端口失败不影响另一个
  // 2. /healthz 只在 4000 上响应, 就绪前返回 503
  // 3. process.on("SIGTERM") / process.on("SIGINT"):
  //    - 两个 server.close() → 停接新请求
  //    - 轮询 inflight 计数器, 等已有请求完成 (最长 60s)
  //    - flush usage.json / cooldown.json → process.exit(0)
  //    - 60s 超时 → process.exit(1)
  // 4. 请求级 inflight 计数器: 入口 +1 → 出口 -1
  // 5. PM2 --wait-ready 协议: ready 后触发 process.send("ready")
}
```

**PM2 配置**：
```json
{
  "name": "ai-loop-router",
  "script": "dist/proxy.js",
  "kill_timeout": 65000,
  "wait_ready": true,
  "listen_timeout": 10000,
  "env": {
    "LOOP_PORT_ANTHROPIC": "4000",
    "LOOP_PORT_OPENAI": "4002",
    "LOOP_COOLDOWN_FILE": "logs/cooldown.json"
  }
}
```

### 5.2 config.ts — 配置管理

**升级重点**：

1. 热重载检测到修改时，不直接 `JSON.parse`，而是：
   - 先读文件 → parse 校验通过 → 再生效
   - parse 失败 → 保留旧配置 + `console.warn` + 不 crash
2. 写入端工具不归本代理管，但代理应能容忍写入中的半截文件（通过文件大小变化检测？或专监听 mtime 的 delay 200ms）
3. 启动时从 `LOOP_COOLDOWN_FILE` 恢复冷却状态

### 5.3 router.ts — 路由逻辑

```
下游请求 (model: "flash" | "code" | "pro")
  → normalize tier
  → 查 tier 表 (tier 内按 priority + score 排序)
  → 优先 session affinity (content hash → upstream name)
  → isUpstreamOk(u) 过滤
  → 返回 candidates 列表

candidates 全不可用 → TIER_FALLBACK 链
fallback 链: pro → flash → code

code 也全不可用:
  → 全局兜底: 扫描 reg.all (所有未 disabled 上游)
  → 如果全部冷却/禁用 → 503 + Retry-After header(min cooldown 剩余)
```

### 5.4 fallback.ts — 透明重试 (同 v3.5 设计 + 修复)

无改动点，之前的逻辑是对的。`streamWithFallback` + `nonStreamWithFallback` 保持不变。

**唯一修改**：`markBad()` 调用后立即持久化冷却状态到 `state.ts` 的 `dirty` 标记，health 探针事后批量写盘。

### 5.5 health.ts — 健康探针

```typescript
// 每 2 分钟对所有 upstream 发 max_tokens=1 轻量请求
// 结果写入 hlt Map
// 如果上游已恢复且冷却剩余 >= 2min → 清除冷却
// 探针前检查 cooldown 是否还在有效期内 (冷却中的不探, 减少无用请求)
```

### 5.6 state.ts — 内存状态管理

**v4.0 改造：**

```typescript
// 冷却持久化: 改写 cool Map 的操作同时标记 dirty
// 后台定时器每 30s flush dirty 到 cooldown.json
// 启动从 cooldown.json 恢复

// 用量: usg.value 保留 7 天, 启动时从 usage.json 加载, 
// 周期性 prune 掉超过 7 天的记录 (在 persist 时截断)

// 请求日志: rlg 用环形缓冲区, 最多 10000 条
```

### 5.7 scoring.ts — 健康评分

同 v3.6，EWMA + 指数退避。无改动点。

### 5.8 auth.ts — 客户端认证

同 v3.5，从 clients.json 读取白名单。无改动点。

---

## 六、上游配置格式 (upstreams.json)

维持现有格式，**仅增加 enabled 字段语义**：
- `enabled: true` / 不填 → 启用
- `enabled: false` → 禁用（不加载到 tier）

```json
[
  {
    "name": "minimax",
    "base_url": "https://api.minimaxi.com/v1",
    "api_key": "sk-xxx",
    "models": ["code"],
    "tier_priority": 0,
    "upstream_model": "MiniMax-M3",
    "enabled": true
  }
]
```

---

## 七、进程生命周期状态机

```
INIT → 端口检测 → EADDRINUSE → 退避 2s → 重试 (最多 5 次)
    ↓ 成功
    LOAD_CONFIG → 恢复冷却 → 启动探针 → /healthz 就绪 (process.send("ready"))
    ↓
    RUNNING (正常服务)
    ↓ SIGTERM / SIGINT
    DRAINING → server.close() → 轮询 inflight (最长 60s) → flush 状态 → exit(0)
    ↓ 崩溃
    CRASHED → PM2 自动重启 (走 INIT)
```

---

## 八、开发注意事项

### 8.1 PM2 适配

- `process.send("ready")` 在 PM2 中才可用，非 PM2 环境要 guard
- `kill_timeout: 65000` ≧ 轮询上限 60s + 5s buffer，PM2 在这个时间前不 SIGKILL。
  **不要调小**，否则 drain 未完成就被杀，cooldown 和 usage 来不及 flush。
- 启动时 listen 失败不 crash 退出，而是退避重试（PM2 `restart_delay: 5000` 兜底）

### 8.2 冷却持久化格式

```json
{
  "minimax": {
    "until": 1783945865323,
    "reason": "h429:Token Plan 用量上限"
  },
  "opencode-go-2": {
    "until": 1783945865323,
    "reason": "h400:Error from provider"
  }
}
```

### 8.3 指标输出（不改 dashboard，加 json 端点给外部消费）

- `GET /admin/stats` → 各上游今日用量、当前冷却、健康状态
- `GET /admin/upstreams` → 同 v3.5

### 8.4 写入端 (外部工具) 的约定

upstreams.json 被热重载监听。外部写入（vim/ echo / curl POST /admin/upstreams）需确保：
- **优先通过 POST /admin/upstreams 修改**（代理内部原子写入）
- 如果直接写文件→用原子写入（写 temp→rename），否则可能触发半截 JSON 导致配置清空

---

## 九、验证标准

交付后验证以下场景：

| 场景 | 预期 |
|------|------|
| 启动时端口被占 | 退避重试，最多 5 次，不僵尸 |
| 杀掉进程 | PM2 重启，端口释放后恢复 |
| upstreams.json 写坏 | 保留旧配置，不 crash |
| minimax 429 报错 | 冷却 minimax，降级到其他上游 |
| 全部上游冷却 | 503 + Retry-After header |
| SIGTERM | 优雅关闭，usage.json flush 完整 |
| 跑 7 天 | 内存稳定，usage prune 正常工作 |
| 并发 100 请求 | 全部正确路由，不丢请求 |

---

## 十、开发顺序

1. server.ts (生命周期 + PM2 适配 + graceful shutdown)
2. config.ts (原子感知热重载 + 冷却恢复)
3. state.ts (有界内存 + 冷却持久化)
4. router.ts + tiers.ts (路由逻辑)
5. fallback.ts (透明重试)
6. health.ts + scoring.ts (探针 + 评分)
7. protocols/messages.ts + chat.ts (协议处理)
8. admin.ts + dashboard.ts (管理界面)
9. auth.ts + usage.ts + cache.ts (辅助功能)
