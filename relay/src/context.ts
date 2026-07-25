// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.2 — 应用上下文（依赖注入容器）
// ═══════════════════════════════════════════════════════════════

import type {
  ClientConfig,
  UsageRecord,
  HealthRecord,
  CooldownRecord,
  ScoreRecord,
  TrailRecord,
} from "./types.js";
import type { LedgerCounters } from "./ledger.js";

export interface AppContext {
  clients: { value: ClientConfig[] };
  usage: { value: UsageRecord[] };
  recentLogs: { value: { t: number; u: string; c: string; m: string; ok: boolean; ms: number; tk: number }[] };
  health: Map<string, HealthRecord>;
  cooldowns: Map<string, CooldownRecord>;
  scores: Map<string, ScoreRecord>;
  startTime: number;
  cacheStats: { hits: number; misses: number; prefixHits: number; prefixMisses: number };
  usageIndex: { client: Map<string, number>; upstream: Map<string, number>; builtAt: number };
  providerFailCounts: Map<string, number>;
  providerCooldowns: Map<string, CooldownRecord>;
  /** v4.2: per-upstream quota ledger */
  ledger: Map<string, LedgerCounters>;
  /** v4.2: recent failover trails (ring) */
  recentTrails: { value: TrailRecord[] };
}

let _ctx: AppContext | null = null;

export function setAppContext(ctx: AppContext): void {
  _ctx = ctx;
}

export function getAppContext(): AppContext {
  if (!_ctx) throw new Error("AppContext not initialized — call setAppContext() at startup");
  return _ctx;
}

/** 测试/启动辅助：补齐 v4.2 缺省槽位 */
export function createAppContext(
  base: Omit<AppContext, "providerFailCounts" | "providerCooldowns" | "ledger" | "recentTrails"> &
    Partial<Pick<AppContext, "providerFailCounts" | "providerCooldowns" | "ledger" | "recentTrails">>,
): AppContext {
  return {
    ...base,
    providerFailCounts: base.providerFailCounts ?? new Map(),
    providerCooldowns: base.providerCooldowns ?? new Map(),
    ledger: base.ledger ?? new Map(),
    recentTrails: base.recentTrails ?? { value: [] },
  };
}
