// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.0 — 用量记录
//  状态通过 getAppContext() 获取（依赖注入）
// ═══════════════════════════════════════════════════════════════

import { writeFileSync, existsSync, readFileSync } from "fs";
import { rebuildUsgIdx } from "./state.js";
import { getAppContext } from "./context.js";
import type { UsageRecord } from "./types.js";
import { recordOutcome } from "./scoring.js";
import { getConfig } from "./config.js";
import { ledgerAddTokens } from "./ledger.js";

const MAX_USG = 100_000;
const MAX_RLG = 5_000;

/** 记录一次请求的用量 */
export function logUsage(u: UsageRecord): void {
  const ctx = getAppContext();
  ctx.usage.value.push(u);
  if (ctx.usage.value.length > MAX_USG) ctx.usage.value = ctx.usage.value.slice(-MAX_USG);
  ctx.recentLogs.value.push({
    t: u.timestamp,
    u: u.upstream,
    c: u.client,
    m: u.model,
    ok: u.success,
    ms: u.latency_ms,
    tk: u.total_tokens,
  });
  if (ctx.recentLogs.value.length > MAX_RLG) ctx.recentLogs.value = ctx.recentLogs.value.slice(-MAX_RLG);
  if (u.upstream && u.upstream !== "cache") {
    recordOutcome(u.upstream, u.success);
    if (u.success && u.total_tokens > 0) {
      const up = getConfig().all.find(x => x.name === u.upstream);
      if (up) ledgerAddTokens(up, u.total_tokens);
    }
  }
}

/** 从磁盘加载历史 usage */
export function loadUsage(file: string): void {
  if (!existsSync(file)) return;
  try {
    const data = JSON.parse(readFileSync(file, "utf-8"));
    if (Array.isArray(data)) getAppContext().usage.value = data.slice(-MAX_USG);
  } catch (e) { console.warn("[usage] failed to load history:", (e as Error).message); }
}

let _persistTimer: ReturnType<typeof setInterval> | null = null;

/** 周期性持久化 usage 到磁盘 + 重建 M9 用量索引（全局只注册一次） */
export function startUsagePersistence(file: string, intervalMs = 60_000): void {
  if (_persistTimer) return;
  _persistTimer = setInterval(() => {
    try {
      const ctx = getAppContext();
      writeFileSync(file, JSON.stringify(ctx.usage.value));
      rebuildUsgIdx();
    } catch (e) { console.warn("[usage] failed to persist:", (e as Error).message); }
  }, intervalMs);
  _persistTimer.unref?.();
}
