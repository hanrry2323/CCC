// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.0 — Tier 管理
//  tier 定义, upstream 可用性判定, tier 模型列表
//  状态通过 getAppContext() 获取（依赖注入）
// ═══════════════════════════════════════════════════════════════

import type { TierId, UpstreamConfig } from "./types.js";
import { getAppContext } from "./context.js";
import { ledgerWouldExceed } from "./ledger.js";

// ── Constants ──

export const TIER_PRIORITY: Record<TierId, number> = {
  pro: 0,
  flash: 1,
  code: 2,
};

export const TIER_FALLBACK: Partial<Record<TierId, TierId>> = {
  pro: "flash",
  flash: "code",
};

// ── Public API ──

/** 判断 upstream 是否可用 */
export function isUpstreamOk(u: UpstreamConfig): boolean {
  if (u.enabled === false) return false;
  if (!u.api_key) return false;

  const ctx = getAppContext();
  const cool = ctx.cooldowns.get(u.name);
  if (cool && cool.until > Date.now()) return false;

  if (u.provider_group) {
    const pc = ctx.providerCooldowns.get(u.provider_group);
    if (pc && pc.until > Date.now()) return false;
  }

  if (ledgerWouldExceed(u)) return false;

  return true;
}

/** 计算所有上游中最早冷却剩余的秒数 */
export function getMinCooldownSec(ups: UpstreamConfig[]): number {
  const cooldowns = getAppContext().cooldowns;
  const now = Date.now();
  let min = 0;
  for (const u of ups) {
    const c = cooldowns.get(u.name);
    if (c && c.until > now) {
      const left = Math.ceil((c.until - now) / 1000);
      if (min === 0 || left < min) min = left;
    }
  }
  return Math.max(min, 0);
}

/** 获取 upstream 不可用原因（与 isUpstreamOk 对齐） */
export function getTierBlockReason(u: UpstreamConfig): string | null {
  if (u.enabled === false) return "disabled";
  if (!u.api_key) return "no_api_key";

  const ctx = getAppContext();
  const cool = ctx.cooldowns.get(u.name);
  if (cool && cool.until > Date.now()) {
    return `cooldown:${cool.reason}:${Math.ceil((cool.until - Date.now()) / 1000)}s`;
  }

  if (u.provider_group) {
    const pc = ctx.providerCooldowns.get(u.provider_group);
    if (pc && pc.until > Date.now()) {
      return `provider_cool:${u.provider_group}:${Math.ceil((pc.until - Date.now()) / 1000)}s`;
    }
  }

  if (ledgerWouldExceed(u)) return "ledger_quota";

  return null;
}

export function getTierLabel(tier: TierId): string {
  const labels: Record<TierId, string> = {
    pro: "Pro (High Capability)",
    flash: "Flash (Fast & Balanced)",
    code: "Code (Free Tier)",
  };
  return labels[tier];
}

export function getTierSummary(registry: { tiers: Map<TierId, UpstreamConfig[]>; all: UpstreamConfig[] }) {
  const result: Array<{ id: TierId; label: string; upstreams: number; healthy: number }> = [];
  for (const [tier, ups] of registry.tiers) {
    const healthy = ups.filter(u => isUpstreamOk(u)).length;
    result.push({ id: tier, label: getTierLabel(tier), upstreams: ups.length, healthy });
  }
  return result.sort((a, b) => TIER_PRIORITY[a.id] - TIER_PRIORITY[b.id]);
}

export function matchTierUpstreams(tier: TierId, ups: UpstreamConfig[]): UpstreamConfig[] {
  return ups
    .filter(u => u.models.includes(tier))
    .filter(u => isUpstreamOk(u))
    .sort((a, b) => (a.tier_priority ?? 99) - (b.tier_priority ?? 99));
}
