// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.0 — Tier 管理
//  tier 定义, upstream 可用性判定, tier 模型列表
//  状态通过 getAppContext() 获取（依赖注入）
// ═══════════════════════════════════════════════════════════════

import type { TierId, UpstreamConfig } from "./types.js";
import { getAppContext } from "./context.js";
import { ledgerWouldExceed } from "./ledger.js";
import { getConfig } from "./config.js";

// ── Constants ──

export const TIER_PRIORITY: Record<TierId, number> = {
  pro: 0,
  flash: 1,
  code: 2,
};

export const TIER_FALLBACK: Partial<Record<TierId, TierId>> = {
  pro: "flash",
  // flash→code 默认关闭：对话突然变成写码档体感像「不稳定」。
  // 需要旧行为时设 LOOP_FLASH_FALLBACK_CODE=1
  ...(process.env.LOOP_FLASH_FALLBACK_CODE === "1" ? { flash: "code" as TierId } : {}),
};

// ── Public API ──

/** 付费 / Go 套餐上游（flash 兜底保底用） */
export function isPaidUpstream(u: UpstreamConfig): boolean {
  if (u.free === false) return true;
  if (u.billing === "opencode-go") return true;
  return /\/zen\/go(\/|$)/i.test(u.base_url || "");
}

/** 长冷却（日配额类）剩余是否超过 thresholdMs */
export function isLongCooldown(u: UpstreamConfig, thresholdMs = 300_000): boolean {
  const cool = getAppContext().cooldowns.get(u.name);
  return !!(cool && cool.until - Date.now() > thresholdMs);
}

/** flash：多数免费钥长冷却时，把 paid 提到候选首位（保 Go 前缀缓存 + 少断流） */
export function boostPaidCandidates(ordered: UpstreamConfig[], tier: TierId): UpstreamConfig[] {
  if (tier !== "flash" || ordered.length < 2) return ordered;
  const regFree = (getConfig().tiers.get("flash") || []).filter(
    u => u.enabled !== false && !isPaidUpstream(u),
  );
  if (!regFree.length) return ordered;
  const longN = regFree.filter(u => isLongCooldown(u)).length;
  if (longN / regFree.length < 0.5) return ordered;

  const paid = ordered.filter(isPaidUpstream);
  const free = ordered.filter(u => !isPaidUpstream(u));
  if (!paid.length || !free.length) return ordered;
  console.warn(
    `[route] flash free long-cooldown ${longN}/${regFree.length} → paid-first (cache sticky)`,
  );
  // 多把同档付费：RR，禁止永远钉第一把
  const paidRotated =
    paid.length > 1
      ? (() => {
          const idx = (_boostPaidRr++ % paid.length);
          return [paid[idx]!, ...paid.filter((_, i) => i !== idx)];
        })()
      : paid;
  return [...paidRotated, ...free];
}

let _boostPaidRr = 0;
/** 测试用 */
export function _resetBoostPaidRrForTest(): void {
  _boostPaidRr = 0;
}

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
