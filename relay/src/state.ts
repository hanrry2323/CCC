// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — 全局共享状态
//  server / protocols / admin / health / usage 共享的内存状态
// ═══════════════════════════════════════════════════════════════

import type {
  ClientConfig,
  UsageRecord,
  HealthRecord,
  CooldownRecord,
  ScoreRecord,
} from "./types.js";

// ── 客户端 / 用量 / 日志 ──

export const cls: { value: ClientConfig[] } = { value: [] };
export const usg: { value: UsageRecord[] } = { value: [] };

export interface LogEntry {
  t: number;
  u: string;
  c: string;
  m: string;
  ok: boolean;
  ms: number;
  tk: number;
}

export const rlg: { value: LogEntry[] } = { value: [] };

// ── 健康 / 冷却 ──

export const hlt = new Map<string, HealthRecord>();
export const cool = new Map<string, CooldownRecord>();

// ── Provider 级断路器（v4.1） ──

/** 连续失败计数 per provider_group */
export const providerFailCounts = new Map<string, number>();
/** provider 级 cooldown（与 per-upstream cool 独立） */
export const providerCool = new Map<string, CooldownRecord>();

// ── 健康评分 (v3.6) ──

export const sc = new Map<string, ScoreRecord>();

// ── 启动时间 ──

export const T0 = Date.now();

// ── 缓存统计 (持久化, 重启后保留) ──

export const cacheStats$ = { hits: 0, misses: 0, prefixHits: 0, prefixMisses: 0 };

// ── M9: 今日用量索引 (O(1) 查, 每 60s 重建) ──

export const usgIdx$ = {
  client: new Map<string, number>(),
  upstream: new Map<string, number>(),
  builtAt: 0,
};

/** 重建用量索引 (从 usg.value 全量扫描一次) */
export function rebuildUsgIdx(): void {
  const ts = (() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d.getTime();
  })();
  const cli = new Map<string, number>();
  const up = new Map<string, number>();
  for (const r of usg.value) {
    if (r.timestamp < ts) continue;
    if (r.client) {
      cli.set(r.client, (cli.get(r.client) || 0) + (r.total_tokens || 0));
    }
    if (r.upstream) {
      up.set(r.upstream, (up.get(r.upstream) || 0) + (r.total_tokens || 0));
    }
  }
  usgIdx$.client = cli;
  usgIdx$.upstream = up;
  usgIdx$.builtAt = Date.now();
}
