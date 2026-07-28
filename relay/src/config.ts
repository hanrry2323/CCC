// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.3 — 配置加载 + 热重载调和
// ═══════════════════════════════════════════════════════════════

import { readFileSync, existsSync, watchFile, unwatchFile } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import type { UpstreamConfig, TierId } from "./types.js";
import { getAppContext } from "./context.js";

const DIR = dirname(fileURLToPath(import.meta.url));

export interface TierRegistry {
  tiers: Map<TierId, UpstreamConfig[]>;
  all: UpstreamConfig[];
  names: TierId[];
}

let _registry: TierRegistry | null = null;
let _upstreamFile = process.env.LOOP_UPSTREAMS_FILE || join(DIR, "..", "upstreams.json");
let _watching = false;
let _prevNames = new Set<string>();

// CCC Relay 2026-07-25 门禁②补丁：非流式/连接超时可配（Lesson 24 教训：30s 硬上限对长 LLM 任务不够）
export const TIMEOUTS = {
  // TCP connect only (undici Agent.connect.timeout)
  CONNECT_MS: Number(process.env.LOOP_CONNECT_TIMEOUT_MS) || 8_000,
  // 单次上游「等到响应头」上限（首包后必须解除，否则会杀长流）
  // free：快失败以便换钥/paid（2017 plist / authority：8s）
  ATTEMPT_MS: Number(process.env.LOOP_UPSTREAM_ATTEMPT_MS) || 8_000,
  // 付费保底：大 prompt TTFB 常 >15s，给更长首包预算（authority：25s）
  ATTEMPT_PAID_MS: Number(process.env.LOOP_UPSTREAM_ATTEMPT_PAID_MS) || 25_000,
  // peek：多钥时代筛坏钥用；付费-only 单钥默认关闭（见 LOOP_STREAM_PEEK）
  PEEK_MS: Number(process.env.LOOP_UPSTREAM_PEEK_MS) || 3_000,
  PEEK_PAID_MS: Number(process.env.LOOP_UPSTREAM_PEEK_PAID_MS) || 3_000,
  // total timeout for non-streaming LLM calls (ms);非流式必须放宽,默认 10 分钟
  NONSTREAM_MS: Number(process.env.LOOP_NONSTREAM_TIMEOUT_MS) || 600_000,
  // undici Agent: streaming body timeout (ms);无读活动超过此时长则断开
  BODY_MS: Number(process.env.LOOP_BODY_TIMEOUT_MS) || 600_000,
  // undici Agent: headers 等待超时 (ms) — 须 ≥ ATTEMPT_PAID
  HEADERS_MS: Number(process.env.LOOP_HEADERS_TIMEOUT_MS) || 30_000,
  // keep-alive socket idle timeout (ms);Lesson 24 教训:默认 4s 太短导致池化连接被服务端回收
  KEEPALIVE_MS: Number(process.env.LOOP_KEEPALIVE_TIMEOUT_MS) || 60_000,
} as const;

/** 流式 peek 总闸：默认关。多钥排障可 LOOP_STREAM_PEEK=1 */
export function streamPeekEnabled(): boolean {
  const v = (process.env.LOOP_STREAM_PEEK || "").trim().toLowerCase();
  if (v === "1" || v === "true" || v === "yes" || v === "on") return true;
  if (v === "0" || v === "false" || v === "no" || v === "off") return false;
  return false; // 付费-only 薄垫片：默认不 peek
}

function isValidUpstream(u: unknown): boolean {
  if (!u || typeof u !== "object") return false;
  const o = u as Record<string, unknown>;
  return typeof o.name === "string"
    && typeof o.base_url === "string"
    && typeof o.api_key === "string"
    && (o.tier_priority === undefined || typeof o.tier_priority === "number")
    && (o.models === undefined || Array.isArray(o.models))
    && (o.upstream_model === undefined || typeof o.upstream_model === "string");
}

/** 归一：models 权威；缺 models 用 tier；缺 tier 用 models[0]；Pro→pro */
export function normalizeUpstream(raw: Record<string, unknown>): UpstreamConfig | null {
  if (!isValidUpstream(raw)) return null;
  const name = String(raw.name);
  const hasModels = Array.isArray(raw.models) && (raw.models as unknown[]).length > 0;
  const rawTier = raw.tier as string | undefined;
  if (!hasModels && !rawTier) return null;

  const canon = (t: string): TierId | null => {
    const s = t.trim().toLowerCase();
    if (s === "pro" || s === "flash" || s === "code") return s;
    return null;
  };

  const models = (hasModels
    ? (raw.models as unknown[]).map(x => canon(String(x))).filter((x): x is TierId => !!x)
    : [canon(String(rawTier))].filter((x): x is TierId => !!x));
  if (models.length === 0) return null;
  const resolvedTier = (canon(String(rawTier || models[0])) || models[0]) as TierId;

  return {
    ...(raw as unknown as UpstreamConfig),
    name,
    models,
    tier: resolvedTier,
    tier_priority: typeof raw.tier_priority === "number" ? raw.tier_priority : 99,
    upstream_model: typeof raw.upstream_model === "string" ? raw.upstream_model : "gpt-4o-mini",
  };
}

/** 校验 upstream 配置，返回有效条目 + 警告列表 */
export function validateConfig(raw: unknown[]): { valid: UpstreamConfig[]; warnings: string[] } {
  const warnings: string[] = [];
  const valid: UpstreamConfig[] = [];

  for (let i = 0; i < raw.length; i++) {
    const u = raw[i] as Record<string, unknown>;
    const idx = i + 1;

    if (!u || typeof u !== "object") {
      warnings.push(`[config] WARN skip upstream #${idx}: not an object`);
      continue;
    }
    if (!u.name || typeof u.name !== "string") {
      warnings.push(`[config] WARN skip upstream #${idx}: missing "name"`);
      continue;
    }
    if (!u.base_url || typeof u.base_url !== "string") {
      warnings.push(`[config] WARN skip "${u.name}": missing "base_url"`);
      continue;
    }
    if (!u.api_key || typeof u.api_key !== "string") {
      warnings.push(`[config] WARN skip "${u.name}": missing "api_key"`);
      continue;
    }
    const hasModels = Array.isArray(u.models) && u.models.length > 0;
    const hasTier = !!u.tier;
    if (!hasModels && !hasTier) {
      warnings.push(`[config] WARN skip "${u.name}": no "models" or "tier"`);
      continue;
    }
    const norm = normalizeUpstream(u);
    if (!norm) {
      warnings.push(`[config] WARN skip "${u.name}": type mismatch`);
      continue;
    }
    valid.push(norm);
  }

  return { valid, warnings };
}

/** Admin 写盘前：整表必须全部合法，否则返回错误文案 */
export function assertValidUpstreamList(raw: unknown[]): string | null {
  if (!Array.isArray(raw)) return "Expected JSON array";
  if (raw.length === 0) return "Empty upstreams list not allowed";
  const { valid, warnings } = validateConfig(raw);
  if (valid.length !== raw.length) {
    return warnings.join("; ") || "validation failed";
  }
  return null;
}

function readUpstreams(): UpstreamConfig[] {
  const p = _upstreamFile;
  if (!existsSync(p)) {
    console.warn("[config] upstreams file not found:", p);
    return [];
  }
  try {
    const raw = JSON.parse(readFileSync(p, "utf-8"));
    if (!Array.isArray(raw)) {
      console.error("[config] upstreams file must be a JSON array");
      return [];
    }
    const { valid, warnings } = validateConfig(raw);
    if (warnings.length) {
      console.warn("[config] validation issues (" + warnings.length + "):\n" + warnings.join("\n"));
    }
    return valid;
  } catch (e) {
    console.error("[config] failed to parse upstreams:", (e as Error).message);
    return [];
  }
}

function buildRegistry(ups: UpstreamConfig[]): TierRegistry {
  const tiers = new Map<TierId, UpstreamConfig[]>();

  for (const u of ups) {
    if (u.enabled === false) continue;
    const modelTiers = (u.models && u.models.length)
      ? (u.models as TierId[])
      : (u.tier ? [u.tier as TierId] : []);
    if (!modelTiers.length) continue;
    for (const t of modelTiers) {
      if (!tiers.has(t)) tiers.set(t, []);
      tiers.get(t)!.push(u);
    }
  }

  for (const [, list] of tiers) {
    list.sort((a, b) => (a.tier_priority ?? 99) - (b.tier_priority ?? 99));
  }

  const names = (["pro", "flash", "code"] as TierId[]).filter(t => tiers.has(t));
  const allFiltered = ups.filter(u => u.enabled !== false);
  return { tiers, all: allFiltered, names };
}

export function reconcileRuntimeState(cfg: TierRegistry): string[] {
  const live = new Set(cfg.all.map(u => u.name));
  const liveGroups = new Set(
    cfg.all.map(u => u.provider_group).filter(Boolean) as string[],
  );

  let ctx;
  try {
    ctx = getAppContext();
  } catch {
    const added: string[] = [];
    for (const n of live) {
      if (!_prevNames.has(n)) added.push(n);
    }
    _prevNames = live;
    return added;
  }

  for (const k of [...ctx.cooldowns.keys()]) {
    if (!live.has(k)) ctx.cooldowns.delete(k);
  }
  for (const k of [...ctx.scores.keys()]) {
    if (!live.has(k)) ctx.scores.delete(k);
  }
  for (const k of [...ctx.ledger.keys()]) {
    if (!live.has(k)) ctx.ledger.delete(k);
  }
  for (const k of [...ctx.health.keys()]) {
    if (!live.has(k)) ctx.health.delete(k);
  }
  for (const k of [...ctx.providerCooldowns.keys()]) {
    if (!liveGroups.has(k)) ctx.providerCooldowns.delete(k);
  }
  for (const k of [...ctx.providerFailCounts.keys()]) {
    if (!liveGroups.has(k)) ctx.providerFailCounts.delete(k);
  }

  const added: string[] = [];
  for (const n of live) {
    if (!_prevNames.has(n)) added.push(n);
  }
  _prevNames = live;
  return added;
}

export function loadConfig(path?: string): TierRegistry {
  if (path) {
    stopConfigWatcher();
    _upstreamFile = path;
    _registry = null;
  }
  if (!_registry) {
    _registry = buildRegistry(readUpstreams());
    _prevNames = new Set(_registry.all.map(u => u.name));
  }
  return _registry;
}

export function resetConfig(): void {
  stopConfigWatcher();
  _registry = null;
  _prevNames = new Set();
}

export function reloadConfig(): void {
  const next = buildRegistry(readUpstreams());
  _registry = next;
  const added = reconcileRuntimeState(next);
  console.log("[config] reloaded, tiers:", [..._registry.tiers.keys()].join(","));
  if (added.length) {
    console.log("[config] new upstreams:", added.join(","));
    // 延迟 import 避免循环依赖
    import("./health.js").then(h => {
      const targets = next.all.filter(u => added.includes(u.name));
      Promise.allSettled(targets.map(u => h.probeOne(u))).catch(() => {});
    }).catch(() => {});
  }
}

export function isAutoReloadEnabled(): boolean {
  return process.env.LOOP_AUTO_RELOAD !== "false";
}

export function startConfigWatcher(): void {
  if (!isAutoReloadEnabled() || _watching) return;
  const p = _upstreamFile;
  if (!existsSync(p)) {
    console.warn("[config] auto-reload: file not found, watcher not started:", p);
    return;
  }
  _watching = true;
  watchFile(p, { interval: 1000 }, (curr, prev) => {
    if (curr.mtimeMs !== prev.mtimeMs) {
      console.log("[config] upstreams file changed, auto-reloading...");
      reloadConfig();
    }
  });
  console.log("[config] auto-reload enabled, watching:", p);
}

export function stopConfigWatcher(): void {
  if (_watching) {
    unwatchFile(_upstreamFile);
    _watching = false;
  }
}

export function getConfig(): TierRegistry {
  if (!_registry) return loadConfig();
  return _registry;
}

export function getUpstreamsFile(): string {
  return _upstreamFile;
}
