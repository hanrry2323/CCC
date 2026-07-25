// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — 精确缓存 (L1)
//  LRU + TTL, 仅命中相同请求, 不做语义缓存
//  仅缓存非流式成功响应, 流式 / 错误响应不缓存
//  hit_rate 是 0~1 的小数 (e.g. 0.45 = 45%) — admin/dashboard 应乘 100 显示百分比
// ═══════════════════════════════════════════════════════════════

import { createHash } from "crypto";
import { existsSync, readFileSync, writeFileSync } from "fs";
import type { CacheEntry } from "./types.js";
import { cacheStats$ } from "./state.js";

// ── 配置 ──

const DEFAULT_TTL_MS = 30 * 60 * 1000; // 30 min（代码开发场景：同一文件上下文频繁复用）
const DEFAULT_MAX = 500;
const DEFAULT_PERSIST_FILE = "logs/cache-stats.json";
const PREFIX_TRACKER_MAX = 200;
const PREFIX_TRACKER_TTL_MS = 30 * 60 * 1000; // 30 min — 前缀跟踪存活时间

const TTL_MS = parseInt(process.env.CACHE_TTL_MS || String(DEFAULT_TTL_MS), 10);
const MAX_ENTRIES = parseInt(process.env.CACHE_MAX || String(DEFAULT_MAX), 10);
const ENABLED = process.env.CACHE_ENABLED !== "0";
/** CACHE_STREAM=0 关闭流式成功结果落缓存（工具请求始终跳过） */
const CACHE_STREAM = process.env.CACHE_STREAM !== "0";

/**
 * 带 tools / tool_choice 的请求不走精确缓存（避免 agent 脏 HIT）
 */
export function isCacheableRequest(req: Record<string, unknown>): boolean {
  if (req.tools != null) {
    if (Array.isArray(req.tools) && req.tools.length === 0) {
      /* empty tools ok */
    } else {
      return false;
    }
  }
  if (req.tool_choice != null && req.tool_choice !== "none") return false;
  return true;
}

export function responseHasToolCalls(response: unknown): boolean {
  const r = response as Record<string, any> | null;
  if (!r) return false;
  if (Array.isArray(r.choices)) {
    for (const c of r.choices) {
      if (c?.message?.tool_calls?.length) return true;
      if (c?.delta?.tool_calls?.length) return true;
    }
  }
  if (Array.isArray(r.content)) {
    if (r.content.some((b: { type?: string }) => b?.type === "tool_use")) return true;
  }
  return false;
}

/** 是否允许写入缓存（工具请求 / 工具响应 / 可选关流式） */
export function shouldCacheWrite(
  req: Record<string, unknown>,
  response?: unknown,
  opts?: { stream?: boolean },
): boolean {
  if (!ENABLED) return false;
  if (!isCacheableRequest(req)) return false;
  if (opts?.stream && !CACHE_STREAM) return false;
  if (response !== undefined && responseHasToolCalls(response)) return false;
  return true;
}

// ── 内部状态 ──

const _store = new Map<string, CacheEntry>(); // Map 保持插入顺序, 用于 LRU

// ── 持久化 (hits/misses) ──

function loadPersistedStats(file: string): void {
  if (!existsSync(file)) return;
  try {
    const data = JSON.parse(readFileSync(file, "utf-8"));
    if (typeof data?.hits === "number" && typeof data?.misses === "number") {
      cacheStats$.hits = data.hits;
      cacheStats$.misses = data.misses;
    }
  } catch (e) { console.warn("[cache] failed to load persisted stats:", (e as Error).message); }
}

function persistStats(file: string): void {
  try {
    writeFileSync(file, JSON.stringify({ hits: cacheStats$.hits, misses: cacheStats$.misses }));
  } catch (e) { console.warn("[cache] failed to persist stats:", (e as Error).message); }
}

let _persistTimer: NodeJS.Timeout | null = null;

export function startCacheStatsPersistence(file: string = DEFAULT_PERSIST_FILE, intervalMs = 30_000): void {
  loadPersistedStats(file);
  if (_persistTimer) clearInterval(_persistTimer);
  // 立即写一次, 避免首次 30s 窗口的丢失
  persistStats(file);
  _persistTimer = setInterval(() => persistStats(file), intervalMs);
  _persistTimer.unref?.();
}

// ── 公共 API ──

/**
 * 计算缓存 key
 * 排除 stream / user-facing 字段, 保留所有影响输出的字段
 * (model, messages, system, tools, tool_choice, max_tokens, temperature, top_p, stop_sequences)
 * 注意: 仅 cacheKey 不含 stream 字段, 但当前仅在非流式调用链写入/读取缓存
 *       stream=true 的请求永远不查缓存 (protocols 层直接 skip)
 */
export function cacheKey(req: Record<string, unknown>): string {
  const fields = [
    "model",
    "messages",
    "system",
    "input",          // OpenAI Responses
    "tools",
    "tool_choice",
    "max_tokens",
    "max_output_tokens",
    "temperature",
    "top_p",
    "stop",
    "stop_sequences",
  ];
  const picked: Record<string, unknown> = {};
  for (const k of fields) {
    if (req[k] !== undefined) picked[k] = req[k];
  }
  const json = JSON.stringify(picked);
  return createHash("sha256").update(json).digest("hex");
}

/** 查询缓存, 不存在返回 null */
export function cacheGet(key: string): CacheEntry | null {
  if (!ENABLED) return null;
  const entry = _store.get(key);
  if (!entry) {
    cacheStats$.misses++;
    return null;
  }
  // TTL 过期
  if (Date.now() - entry.timestamp > entry.ttl_ms) {
    _store.delete(key);
    cacheStats$.misses++;
    return null;
  }
  // LRU: 重新插入到末尾
  _store.delete(key);
  _store.set(key, entry);
  cacheStats$.hits++;
  return entry;
}

/** 带请求门控的查询：tools 请求直接跳过 */
export function cacheLookup(req: Record<string, unknown>): CacheEntry | null {
  if (!isCacheableRequest(req)) return null;
  const key = cacheKey(req);
  if (!key) return null;
  return cacheGet(key);
}

/** 写入缓存 (仅成功且可缓存响应) */
export function cacheSet(key: string, response: unknown, tokens: { input: number; output: number }): void {
  if (!ENABLED) return;
  if (responseHasToolCalls(response)) return;
  // 已达上限, 删除最老 (Map 第一个)
  if (_store.size >= MAX_ENTRIES) {
    const first = _store.keys().next().value;
    if (first) _store.delete(first);
  }
  const entry: CacheEntry = {
    key,
    response,
    timestamp: Date.now(),
    tokens,
    ttl_ms: TTL_MS,
  };
  _store.set(key, entry);
}

/** 删除单条 (供 admin PURGE 用) */
export function cacheDelete(key: string): boolean {
  return _store.delete(key);
}

/** 清空全部 */
export function cacheClear(): void {
  _store.clear();
  cacheStats$.hits = 0;
  cacheStats$.misses = 0;
}

/**
 * 缓存统计 (供 admin/dashboard)
 * hit_rate: 0~1 的小数, 例如 0.45 = 45%
 * prefix_hit_rate: 前缀匹配率，反映上游 prompt caching 的潜在效果
 */
export function cacheStats(): {
  enabled: boolean;
  size: number;
  max: number;
  hits: number;
  misses: number;
  hit_rate: number;
  prefix_hits: number;
  prefix_misses: number;
  prefix_hit_rate: number;
  prefix_tracker_size: number;
} {
  const total = cacheStats$.hits + cacheStats$.misses;
  const pTotal = cacheStats$.prefixHits + cacheStats$.prefixMisses;
  return {
    enabled: ENABLED,
    size: _store.size,
    max: MAX_ENTRIES,
    hits: cacheStats$.hits,
    misses: cacheStats$.misses,
    hit_rate: total === 0 ? 0 : cacheStats$.hits / total,
    prefix_hits: cacheStats$.prefixHits,
    prefix_misses: cacheStats$.prefixMisses,
    prefix_hit_rate: pTotal === 0 ? 0 : cacheStats$.prefixHits / pTotal,
    prefix_tracker_size: prefixTracker.size,
  };
}

/** 仅供测试: 重置统计与缓存 */
export function _cacheResetForTest(): void {
  _store.clear();
  cacheStats$.hits = 0;
  cacheStats$.misses = 0;
}

/** 计算前缀缓存 key — 仅取 system+tools（Agent 工具的动态 messages 排除后仍可匹配） */
export function prefixCacheKey(req: Record<string, unknown>): string | null {
  const fields = ["model", "system", "tools", "tool_choice"];
  const picked: Record<string, unknown> = {};
  for (const k of fields) {
    if (req[k] !== undefined) picked[k] = req[k];
  }
  if (Object.keys(picked).length === 0) return null;
  const json = JSON.stringify(picked);
  return createHash("sha256").update(json).digest("hex");
}

/** 前缀跟踪 — 记录最近见过的 system+tools 前缀，用于诊断上游 prompt caching 效果 */
const prefixTracker = new Map<string, { count: number; lastSeen: number }>();

export function trackPrefix(prefixKey: string | null): { seen: boolean; hitCount: number } {
  if (!prefixKey) {
    cacheStats$.prefixMisses++;
    return { seen: false, hitCount: 0 };
  }
  const now = Date.now();
  const entry = prefixTracker.get(prefixKey);
  if (entry && (now - entry.lastSeen) < PREFIX_TRACKER_TTL_MS) {
    entry.count++;
    entry.lastSeen = now;
    cacheStats$.prefixHits++;
    return { seen: true, hitCount: entry.count };
  }
  prefixTracker.set(prefixKey, { count: 1, lastSeen: now });
  cacheStats$.prefixMisses++;
  if (prefixTracker.size > PREFIX_TRACKER_MAX) {
    const first = prefixTracker.keys().next().value;
    if (first) prefixTracker.delete(first);
  }
  return { seen: false, hitCount: 1 };
}

/** 前缀缓存统计 */
export function prefixCacheStats(): { size: number; max: number } {
  return { size: prefixTracker.size, max: PREFIX_TRACKER_MAX };
}

// ── 周期清理过期条目 (每 60s) ──

setInterval(() => {
  if (!ENABLED || _store.size === 0) return;
  const now = Date.now();
  for (const [k, v] of _store) {
    if (now - v.timestamp > v.ttl_ms) _store.delete(k);
  }
  // 同时清理前缀 tracker
  for (const [k, v] of prefixTracker) {
    if (now - v.lastSeen > PREFIX_TRACKER_TTL_MS) prefixTracker.delete(k);
  }
}, 60_000).unref?.();
