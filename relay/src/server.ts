// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.0 — HTTP 入口
//  启动时创建 AppContext（依赖注入容器），替代 setCooldowns/setHealth
// ═══════════════════════════════════════════════════════════════

import http from "http";
import { existsSync, readFileSync } from "fs";
import { Agent, setGlobalDispatcher } from "undici";
// CCC Relay 2026-07-25 门禁②补丁:显式 undici Agent 配 body/headers/keep-alive 超时
// (Lesson 24: 默认 keep-alive 4s 太短,长 LLM 任务撞连接池回收)
import { TIMEOUTS } from "./config.js";
import { preferIpv4Dns, EGRESS_CONNECT_IPV4 } from "./dns-prefer-ipv4.js";

// 本网 opencode.ai IPv6 黑洞：DNS + undici 一律 IPv4-first（对齐 M1 稳定出站）
preferIpv4Dns();

// 全局 dispatcher:统一所有 fetch() 出站的 socket / body / headers / keep-alive 行为
// 不设 connections → undici 默认 null=不限并发（下游 Claude/OpenCode/Codex/Desktop 可同时打）
setGlobalDispatcher(new Agent({
  connect: { timeout: TIMEOUTS.CONNECT_MS, ...EGRESS_CONNECT_IPV4 },
  bodyTimeout: TIMEOUTS.BODY_MS,
  headersTimeout: TIMEOUTS.HEADERS_MS,
  keepAliveTimeout: TIMEOUTS.KEEPALIVE_MS,
  pipelining: 1,
}));
import { loadConfig, startConfigWatcher } from "./config.js";
import { cls, hlt, cool, sc, usg, rlg, usgIdx$, cacheStats$, T0, providerFailCounts, providerCool } from "./state.js";
import { createAppContext, setAppContext } from "./context.js";
import type { AppContext } from "./context.js";
import { startHealthProbe } from "./health.js";
import { loadUsage, startUsagePersistence } from "./usage.js";
import { startCacheStatsPersistence } from "./cache.js";
import { startScorePersistence } from "./scoring.js";
import type { ClientConfig } from "./types.js";
import { handleMessages } from "./protocols/messages.js";
import { handleChat } from "./protocols/chat.js";
import { handleResponses } from "./protocols/responses.js";
import { handleAdmin } from "./admin.js";
import { handleDashboard } from "./dashboard.js";
import { json, notFound } from "./http.js";

export type ServerMode = "anthropic" | "openai-chat" | "all";

export interface ServerOptions {
  port?: number;
  mode?: ServerMode;
}

let _probeStarted = false;

const DEFAULT_PORT = parseInt(process.env.LOOP_PORT || "4000", 10);
const VALID_MODES: readonly ServerMode[] = ["anthropic", "openai-chat", "all"];

function resolveMode(envMode: string | undefined, fallback: ServerMode): ServerMode {
  if (envMode && (VALID_MODES as readonly string[]).includes(envMode)) {
    return envMode as ServerMode;
  }
  if (envMode) {
    console.warn(`[server] unknown LOOP_MODE="${envMode}", fallback to "${fallback}". valid: ${VALID_MODES.join(", ")}`);
  }
  return fallback;
}

function initAppContext(): AppContext {
  const ctx = createAppContext({
    clients: cls,
    usage: usg,
    recentLogs: rlg,
    health: hlt,
    cooldowns: cool,
    scores: sc,
    startTime: T0,
    cacheStats: cacheStats$,
    usageIndex: usgIdx$,
    providerFailCounts,
    providerCooldowns: providerCool,
  });
  setAppContext(ctx);
  return ctx;
}

export function startServer(opts: ServerOptions = {}): http.Server {
  const port = opts.port ?? DEFAULT_PORT;
  const mode: ServerMode = opts.mode
    ? resolveMode(opts.mode, opts.mode)
    : resolveMode(process.env.LOOP_MODE, "all");

  loadConfig();
  startConfigWatcher();

  const clientsFile = process.env.LOOP_CLIENTS_FILE || "clients.json";
  if (existsSync(clientsFile)) {
    try { cls.value = JSON.parse(readFileSync(clientsFile, "utf-8")) as ClientConfig[]; }
    catch (e) { console.warn("[server] failed to parse clients file:", (e as Error).message); }
  }

  loadUsage(process.env.LOOP_USAGE_FILE || "logs/usage.json");
  startUsagePersistence(process.env.LOOP_USAGE_FILE || "logs/usage.json");
  startCacheStatsPersistence(process.env.LOOP_CACHE_STATS_FILE || "logs/cache-stats.json");
  startScorePersistence(process.env.LOOP_SCORES_FILE || "logs/scores.json");

  if (!_probeStarted) {
    startHealthProbe();
    _probeStarted = true;
  }

  const server = http.createServer(async (req, res) => {
    try {
      await handleRequest(req, res, mode);
    } catch (e) {
      console.error("[server] uncaught:", e);
      if (!res.headersSent) {
        json(res, 500, { error: { type: "internal_error", message: (e as Error).message } });
      }
    }
  });
  // 入站不设 maxConnections（Node 默认 undefined=不限；切勿设 0，会被当成最多 0 条）

  server.listen(port, () => {
    console.log(`╔══════════════════════════════════════════════╗`);
    console.log(`║  AI Loop Router v4.3.0                       ║`);
    console.log(`║  Mode: ${mode.padEnd(40)}║`);
    console.log(`║  Port: ${String(port).padEnd(40)}║`);
    console.log(`╚══════════════════════════════════════════════╝`);
    console.log(`  Endpoints:`);
    if (mode === "anthropic" || mode === "all") console.log(`    POST /v1/messages          (Anthropic)`);
    if (mode === "openai-chat" || mode === "all") {
      console.log(`    POST /v1/chat/completions  (OpenAI Chat)`);
      console.log(`    POST /v1/responses         (OpenAI Responses · Codex)`);
    }
    console.log(`    GET  /admin/*              (Admin API)`);
    console.log(`    GET  /dashboard            (Dashboard)`);
  });

  return server;
}

async function handleRequest(req: http.IncomingMessage, res: http.ServerResponse, mode: string): Promise<void> {
  const url = new URL(req.url || "/", "http://x");
  const pathname = url.pathname;
  const method = req.method || "GET";

  // M1: /admin/* 仅允许白名单 method
  if (pathname === "/admin" || pathname.startsWith("/admin/")) {
    const m = method.toUpperCase();
    if (!["GET", "POST", "PUT", "DELETE", "PATCH"].includes(m)) {
      res.writeHead(405, { "Allow": "GET, POST, PUT, DELETE, PATCH", "Content-Type": "text/plain" });
      res.end("Method Not Allowed");
      return;
    }
    return handleAdmin(req, res, pathname);
  }

  if (method === "GET" && (pathname === "/dashboard" || pathname === "/")) {
    return handleDashboard(req, res);
  }

  if ((mode === "anthropic" || mode === "all") && method === "POST" && pathname === "/v1/messages") {
    return handleMessages(req, res);
  }

  if ((mode === "openai-chat" || mode === "all") && method === "POST" && pathname === "/v1/chat/completions") {
    return handleChat(req, res);
  }

  if ((mode === "openai-chat" || mode === "all") && method === "POST" && pathname === "/v1/responses") {
    return handleResponses(req, res);
  }

  // Codex / ChatGPT.app doctor 探活；逻辑档名 flash（上游仍是 Go paid）
  if ((mode === "openai-chat" || mode === "all") && method === "GET" && pathname === "/v1/models") {
    return json(res, 200, {
      object: "list",
      data: [
        {
          id: "flash",
          object: "model",
          created: 0,
          owned_by: "ccc-relay",
        },
      ],
    });
  }

  return notFound(res, pathname, mode);
}

// ── 全局异常保护 ──
process.on("unhandledRejection", (reason, promise) => {
  console.error("[process] unhandledRejection:", (reason as Error).message?.slice(0, 120) || reason);
  // 防止 Node.js 15+ 强制终止进程
  if (process.exitCode === undefined) process.exitCode = 1;
  // 不主动 exit，让进程继续运行
});
process.on("uncaughtException", (err) => {
  console.error("[process] uncaughtException:", err.message?.slice(0, 120), err.stack?.slice(0, 200));
  // 不主动 exit，但记录以便排查
});

process.on("SIGTERM", () => {
  console.log("[process] received SIGTERM, shutting down gracefully");
  process.exit(0);
});
process.on("SIGINT", () => {
  console.log("[process] received SIGINT (Ctrl+C), shutting down");
  process.exit(0);
});
process.on("exit", (code) => {
  console.log(`[process] exited with code ${code}, PID ${process.pid}`);
});

// ── 入口检测 ──
// LOOP_MAIN=0 可显式禁用（测试/import场景），否则按文件名自动判定
const _entry = process.argv[1] || "";
const isMain = process.env.LOOP_MAIN !== "0" && (
  _entry.endsWith("/dist/proxy.js") ||
  _entry.endsWith("/src/server.ts") ||
  _entry.endsWith("/proxy") ||
  _entry.endsWith("\\dist\\proxy.js") // Windows
);
if (isMain) {
  // v4.0: 统一共享状态容器 — 替代原来的 setCooldowns/setHealth 桥接
  initAppContext();
  // 单进程双端口：共享冷却/健康/用量状态
  startServer({ port: 4000, mode: "anthropic" });    // flash tier: opencode-go 系列
  startServer({ port: 4002, mode: "openai-chat" });   // code tier: xfyun → zhipu
  console.log(`[server] 双端口就绪: 4000(anthropic) 4002(openai-chat)`);
}
