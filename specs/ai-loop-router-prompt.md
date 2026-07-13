# AI Loop Router v4.0 — Cursor 开发提示词

**用法**：把本文件完整粘贴到 Cursor 的对话窗口。确保 Cursor 的 workspace 是 `/Users/apple/program/ai-loop-router`。

---

## 你的任务

把 `/Users/apple/program/ai-loop-router/src/` 下的现有代理（v3.x）重构为 v4.0，解决**进程生命周期、配置管理、内存泄漏、冷却丢失**等架构问题。

**不允许做的**：
- 不改依赖（package.json 不增减）
- 不改上游交互协议（HTTP 请求格式、SSE 解析不变）
- 不改 upstreams.json/clients.json 格式
- 不改 dashboard 前端 HTML/CSS
- 不改 scoring.ts (健康评分 + 指数退避) 的业务逻辑
- 不改 fallback.ts 的透明重试逻辑
- 不改 auth.ts、cache.ts、catalog.ts

**必须改的**在下方。

---

## 一、必须修正的 8 个架构问题

### P0 — server.ts 生命周期（最关键）

现有 `server.ts:130-148` 的 `process.on("uncaughtException")` 和双端口启动需要彻底重写。

要求：

**1.1 保留双端口（4000 + 4002），各端口独立退避重试 + 优雅关闭**

当前 `server.ts:130-148` 的双端口启动逻辑需要强化而非删除。两个端口承担不同协议，缺一不可：
- **4000** — Anthropic Messages API（给 `ANTHROPIC_BASE_URL` 的客户端，如 flash tier）
- **4002** — OpenAI Chat API（给 `OPENAI_BASE_URL` 的客户端，如 code tier）

改动要求：
- 两个端口各走独立 `tryListen()` 退避重试（端口绑定失败不会因为一个端口失败而影响另一个）
- 两个端口共享同一套 graceful shutdown（`server.close()` 同时关闭两个 server）
- `/healthz` 只挂在 4000 上（PM2 统一对 4000 做存活检测）

```
Port 4000 — Anthropic Messages API
  POST /v1/messages          → Anthropic Messages API
  GET  /admin/*              → Admin
  GET  /dashboard            → Dashboard HTML
  GET  /healthz              → 存活检查 (200 OK 表示就绪)

Port 4002 — OpenAI Chat API
  POST /v1/chat/completions  → OpenAI Chat API
```

**1.2 listen 失败必须退避重试，不能沉默**

```typescript
// 伪代码 — 在 server.listen 外包裹 retry 逻辑
function tryListen(server, port, maxRetries=5): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await new Promise((resolve, reject) => {
        server.once("error", reject);
        server.listen(port, resolve);
      });
      return; // 成功
    } catch (e) {
      if (e.code !== "EADDRINUSE") throw e; // 非端口冲突直接抛
      const delay = Math.min(1000 * Math.pow(2, i), 10000); // 1s, 2s, 4s, 8s, 10s
      console.warn(`[server] port ${port} in use, retry in ${delay}ms (${i+1}/${maxRetries})`);
      await new Promise(r => setTimeout(r, delay));
    }
  }
  throw new Error(`[server] port ${port} still in use after ${maxRetries} retries`);
}
```

重试 5 次仍失败 → `process.exit(1)` 让 PM2 接管（PM2 的 `restart_delay` 兜底）。

**1.3 graceful shutdown（需处理 SSE 长连接）**

```typescript
let inflight = 0; // 活跃请求计数器

// 请求进入 +1，响应结束 -1（在 handleRequest 的入口/出口各调一次）
function onRequestStart() { inflight++; }
function onRequestEnd()   { inflight--; }

function shutdown(signal: string): void {
  console.log(`[server] received ${signal}, draining...`);

  // 关闭两个 server（停止接受新连接）
  serverAnthropic.close(() => { /* anthropic server closed */ });
  serverOpenAI.close(() => { /* openai server closed */ });

  // 轮询等待 inflight 归零，最多 60 秒
  const start = Date.now();
  const interval = setInterval(() => {
    if (inflight <= 0) {
      console.log("[server] all inflight requests finished");
      clearInterval(interval);
      flushCooldownSync();
      flushUsageSync();
      process.exit(0);
    }
    if (Date.now() - start > 60000) {
      console.warn(`[server] forced exit after 60s, ${inflight} requests still active`);
      clearInterval(interval);
      process.exit(1);
    }
  }, 1000);
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
```

**1.4 process.on("uncaughtException") 要 exit**

现有代码只 log 不 exit，导致进程僵尸。改为：
```typescript
process.on("uncaughtException", (err) => {
  console.error("[process] uncaughtException:", err.message);
  // 不 exit 会僵尸。但不要在这里写文件（可能递归 crash）
  // 让 PM2 重启
  process.exit(1);
});
```

**1.5 /healthz 就绪检测**

程序启动、加载配置、恢复冷却都完成后，`/healthz` 才返回 200。在此之前返回 503。

如果 PM2 环境存在 `process.send`（`process.env.PM2_USAGE` 或 `typeof process.send === "function"`），就绪后调用 `process.send("ready")`。

### P1 — state.ts 冷却持久化

**问题**：冷却状态在内存，进程重启全部丢失 → 立即重试故障上游 → 又 429 → 震荡。

要求：

**1.1 增加 load/save 函数**

```typescript
// 从 cooldown.json 恢复（启动时调用）
export function loadCooldown(filePath: string): void {
  try {
    const raw = JSON.parse(readFileSync(filePath, "utf-8"));
    for (const [name, record] of Object.entries(raw)) {
      if (record.until > Date.now()) {
        cool.set(name, record as CooldownRecord);
      }
    }
  } catch {} // 文件不存在或损坏 → 空冷却
}

// 标记 dirty，定时 flush
const _cooldownDirty = { value: false };
const _cooldownFile = { value: "" };

// 每次 fallback.ts 调用 markBad() 之后标记 dirty
export function markCooldownDirty(): void { _cooldownDirty.value = true; }
export function setCooldownFile(p: string): void { _cooldownFile.value = p; }

// 定时 flush（每 30 秒）
export function startCooldownPersistence(filePath: string): void {
  _cooldownFile.value = filePath;
  setInterval(() => {
    if (!_cooldownDirty.value) return;
    const data: Record<string, CooldownRecord> = {};
    for (const [k, v] of cool) data[k] = v;
    writeFileSync(filePath, JSON.stringify(data, null, 2));
    _cooldownDirty.value = false;
  }, 30000);
}

// 同步 flush（shutdown 时用）
export function flushCooldownSync(): void {
  if (!_cooldownFile.value) return;
  const data: Record<string, CooldownRecord> = {};
  for (const [k, v] of cool) data[k] = v;
  writeFileSync(_cooldownFile.value, JSON.stringify(data, null, 2));
}
```

文件路径从环境变量 `LOOP_COOLDOWN_FILE` 读取，默认 `logs/cooldown.json`。

**1.2 修改 fallback.ts**

在 `markBad()` 函数末尾（`~/program/ai-loop-router/src/fallback.ts:103`），添加：
```typescript
import { markCooldownDirty } from "./state.js";
// 在 bad() 调用后:
markCooldownDirty();
```

### P2 — config.ts 原子热重载

**问题**：`watchFile` + 直接 `JSON.parse` → 读到半截 JSON → 配置全空 → 0 路由。

要求：

**2.1 parse 失败时不 reload**

修改 `config.ts:reloadConfig()`：
```typescript
export function reloadConfig(): void {
  const raw = readUpstreams();  // 可能返回 []（parse 失败）
  if (raw.length === 0 && _registry && _registry.all.length > 0) {
    // 有旧配置且新解析结果是空的 → 可能是半截写入，保留旧配置
    console.warn("[config] parse returned 0 upstreams but we had", _registry.all.length, "— keeping old config");
    return;
  }
  _registry = buildRegistry(raw);
  console.log("[config] reloaded, tiers:", [..._registry.tiers.keys()].join(","));
}
```

同时 `readUpstreams()` 内部 JSON.parse 失败时返回 `null` 而不是 `[]`，让 caller 区分"文件空"和"解析失败"。

```typescript
function readUpstreams(): UpstreamConfig[] | null {
  // parse 成功但空数组 → 返回 [] (用户清空了)
  // parse 失败 → 返回 null (解析错误)
}
```

**2.2 启动时加载冷却文件**

在 `server.ts` 的 `startServer()` / `main()` 中：
```typescript
import { loadCooldown, startCooldownPersistence, setCooldownFile } from "./state.js";
const cooldownFile = process.env.LOOP_COOLDOWN_FILE || join(DIR, "logs", "cooldown.json");
loadCooldown(cooldownFile);
startCooldownPersistence(cooldownFile);
```

### P3 — state.ts 有界内存

**问题**：`usg.value` 和 `rlg.value` 无限增长，admin API 每次全遍历。

要求：

**3.1 usg.value 保留 7 天**

修改 `usage.ts` 的持久化逻辑——写文件时：
```typescript
const SEVEN_DAYS = 7 * 24 * 3600 * 1000;
const cutoff = Date.now() - SEVEN_DAYS;
usg.value = usg.value.filter(r => r.timestamp >= cutoff);
```

在 `startUsagePersistence()` 中，每次 persist 前做这个 prune。

**3.2 rlg 改为环形缓冲区**

```typescript
// state.ts
const MAX_LOG = 10000;
export function pushLog(entry: LogEntry): void {
  rlg.value.push(entry);
  if (rlg.value.length > MAX_LOG) {
    rlg.value.splice(0, rlg.value.length - MAX_LOG);
  }
}
```

所有调用 `rlg.value.push()` 的地方改为 `pushLog()`。

### P4 — server.ts error handler

**问题**：`handleRequest` 的 `try/catch` 在 `server.ts:72-80` 已经存在，但外层没有兜底。

**现状正确**：`http.createServer` 的回调有 try/catch → 500 JSON。不改。

**补充**：给 `server.on("clientError", ...)` 加 handler，防止畸形 HTTP 请求 crash 进程。
```typescript
server.on("clientError", (err, socket) => {
  console.warn("[server] clientError:", err.message?.slice(0, 60));
  socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
});
```

### P5 — admin.ts clients hot-reload

**问题**：`admin.ts:160` 用 POST 替换 `cls.value`，但文件不同步。

**改成**：POST /admin/clients 写入新配置后，同步写回 `clients.json`。
```typescript
// admin.ts PUT /admin/clients 末尾
cls.value = b;
writeFileSync(clientsFile, JSON.stringify(b, null, 2));
```

`clientsFile` 从 `process.env.LOOP_CLIENTS_FILE` 或 `clients.json` 读取。

### P6 — server.ts /healthz endpoint

追加到 `handleRequest()` 的路由匹配中：
```typescript
if (pathname === "/healthz") {
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ status: "ok" }));
  return;
}
```

在 `_ready` 标志位 false 时返回 503。

### P7 — server.ts listen 前端口检查（可选增强）

```typescript
import { createServer } from "net";
function isPortAvailable(port: number): Promise<boolean> {
  return new Promise(resolve => {
    const s = createServer();
    s.once("error", () => resolve(false));
    s.once("listening", () => { s.close(); resolve(true); });
    s.listen(port);
  });
}
```

在 `tryListen` 循环前先快速检查一次。

---

## 二、不改的文件（已稳定）

| 文件 | 原因 |
|------|------|
| `fallback.ts` | 透明重试逻辑已正确，只需在 markBad 加一行 markCooldownDirty |
| `scoring.ts` | EWMA + 指数退避正确 |
| `health.ts` | 探针逻辑正确 |
| `tiers.ts` | TIER_FALLBACK 链 + isUpstreamOk 正确 |
| `auth.ts` | 认证逻辑正确 |
| `cache.ts` | 缓存逻辑正确 |
| `catalog.ts` | 目录服务逻辑正确 |
| `http.ts` | 工具函数正确 |
| `utils.ts` | 工具函数正确 |
| `types.ts` | 类型定义正确 |
| `dashboard.ts` | 前端展示，不改 |
| `protocols/` | 协议处理逻辑正确 |
| `translator/` | 格式转换正确 |

---

## 三、交付清单

修改以下文件（按依赖顺序）：

1. `src/state.ts` — 加冷却持久化、环形缓冲区、flush 函数
2. `src/config.ts` — 加解析失败保护、parse 返回值改为 UpstreamConfig[] | null
3. `src/server.ts` — 重写生命周期：双端口独立 retry + 共享 graceful shutdown + /healthz（4000 独有）
4. `src/fallback.ts` — 加 1 行 `markCooldownDirty()`
5. `src/admin.ts` — PUT /admin/clients 同步写文件
6. `src/usage.ts` — persist 前 prune 7 天

新增文件：无（全在现有 src/ 内修改）

---

## 四、自验证

开发完成后在终端依次验证：

```bash
# 4.1 编译
cd ~/program/ai-loop-router && npm run build

# 4.2 启动
node dist/proxy.js &
sleep 2

# 4.3 健康检查
curl -s http://127.0.0.1:4000/healthz

# 4.4 基本路由
curl -s -w "\nHTTP %{http_code}" -X POST http://127.0.0.1:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: test" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"flash","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'

# 4.5 冷却持久化验证
kill <PID>
node dist/proxy.js  # 重启后查 cooldown.json 是否恢复

# 4.6 SIGTERM 优雅关闭
kill -TERM <PID>  # 应能看到 graceful shutdown 日志

# 4.7 PM2 启动 (先停掉手动进程)
pm2 start dist/proxy.js --name ai-loop-router --kill-timeout 65000 --wait-ready
pm2 logs --lines 20
```

---

## 五、上下文字典

| 术语 | 含义 |
|------|------|
| upstream | 上游模型提供商（minimax / opencode / xfyun / zhipu） |
| tier | 梯队：pro(高端) / flash(主力) / code(免费) |
| cooldown | 冷却时间，上游失败后暂不选它 |
| session affinity | 同一会话尽量路由到同一个上游 |
| /healthz | PM2 就绪探测端点 |
| graceful shutdown | 收到停止信号后 drain 完现有请求再退 |
