// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.6 — Tier 梯队路由
//  route(tierId, affinityKey) → RoutingResult
//  按优先级 + Session Affinity + tier fallback 选 upstream
//  v3.6 R5: affinity 改用 upstream name 作 key (跨 tier 复用)
// ═══════════════════════════════════════════════════════════════

import type { TierId, UpstreamConfig, RoutingResult } from "./types.js";
import { TierRegistry } from "./config.js";
import { isUpstreamOk, TIER_FALLBACK, getMinCooldownSec, boostPaidCandidates, isPaidUpstream } from "./tiers.js";
import { getConfig } from "./config.js";
import { getScore } from "./scoring.js";

// ── Session Affinity ──

interface AffinityEntry {
  upstream: string;
  at: number;
}

const _affinity = new Map<string, AffinityEntry>();
const AFFINITY_TTL = 30 * 60 * 1000; // 30min
const AFFINITY_MAX = 500;

function hashStr(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h) + s.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h).toString(36);
}

function msgText(m: { role?: string; content?: unknown }): string {
  if (typeof m.content === "string") return m.content.slice(0, 400);
  return JSON.stringify(m.content || "").slice(0, 400);
}

/**
 * Session affinity key：优先 x-session-id / x-request-id；
 * 否则 hash(system 摘要 + 最近 2 条 user)
 */
export function affinityKey(
  messages: { role: string; content?: unknown }[] | null | undefined,
  opts?: {
    headers?: { get?(name: string): string | null | undefined } | Record<string, string | string[] | undefined> | null;
    system?: unknown;
  },
): string | null {
  const headers = opts?.headers;
  if (headers) {
    const pick = (name: string): string | null => {
      if (typeof (headers as any).get === "function") {
        const v = (headers as { get(n: string): string | null }).get(name);
        return v && String(v).trim() ? String(v).trim() : null;
      }
      const raw = (headers as Record<string, string | string[] | undefined>)[name]
        ?? (headers as Record<string, string | string[] | undefined>)[name.toLowerCase()];
      if (Array.isArray(raw)) return raw[0]?.trim() || null;
      return raw && String(raw).trim() ? String(raw).trim() : null;
    };
    const sid = pick("x-session-id") || pick("x-request-id");
    if (sid) return "hdr:" + hashStr(sid);
  }

  const users = (messages || []).filter(m => m.role === "user").slice(-2);
  const sys = opts?.system != null
    ? (typeof opts.system === "string" ? opts.system.slice(0, 200) : JSON.stringify(opts.system).slice(0, 200))
    : "";
  if (!users.length && !sys) return null;
  const blob = sys + "||" + users.map(msgText).join("||");
  return hashStr(blob);
}

// R5: key 绑定到 upstream name (跨 tier 复用) 而不是 tier
// 例如: 用户先被路由到 opencode-go (flash), 后 tier 降级 → 仍优先 opencode-go
function affinityK(key: string, upstreamName: string): string {
  return key + "::" + upstreamName;
}

export function affinityGet(key: string, upstreamName: string): UpstreamConfig | null {
  const k = affinityK(key, upstreamName);
  const e = _affinity.get(k);
  if (!e) return null;
  if (Date.now() - e.at > AFFINITY_TTL) {
    _affinity.delete(k);
    return null;
  }
  const reg = getConfig();
  for (const up of reg.all) {
    if (up.name === e.upstream) {
      if (!isUpstreamOk(up)) return null; // 已冷却 → 不续绑坏上游
      return up;
    }
  }
  return null;
}

export function affinitySet(key: string, upstreamName: string, _unusedTier?: string): void {
  // 同一会话只保留一个上游绑定：否则 free/paid 多条并存时 route 仍先命中 prio=1 免费钥
  const prefix = key + "::";
  for (const k of [..._affinity.keys()]) {
    if (k.startsWith(prefix)) _affinity.delete(k);
  }
  const k = affinityK(key, upstreamName);
  _affinity.set(k, { upstream: upstreamName, at: Date.now() });
  if (_affinity.size > AFFINITY_MAX) {
    const first = _affinity.keys().next().value;
    if (first) _affinity.delete(first);
  }
}

export function affinityDelete(key: string, upstreamName: string): void {
  _affinity.delete(affinityK(key, upstreamName));
}

/** 清除某 key 的所有 upstream 绑定 (e.g. tier 全部失败) */
export function affinityDeleteAll(key: string): void {
  const prefix = key + "::";
  for (const k of _affinity.keys()) {
    if (k.startsWith(prefix)) _affinity.delete(k);
  }
}

/** 配额耗尽等：清除粘在该上游上的所有会话绑定 */
export function affinityDeleteByUpstream(upstreamName: string): void {
  const suffix = "::" + upstreamName;
  for (const k of [..._affinity.keys()]) {
    if (k.endsWith(suffix)) _affinity.delete(k);
  }
}

/** 清理过期 affinity */
export function affinityCleanup(): void {
  const now = Date.now();
  for (const [k, v] of _affinity) {
    if (now - v.at > AFFINITY_TTL) _affinity.delete(k);
  }
}

// ── Main Route ──

interface RouteState {
  candidates: UpstreamConfig[];
  found: UpstreamConfig | null;
}

/**
 * 路由: 根据 tier + 可选 affinity key 选择最佳 upstream
 *
 * 流程:
 * 1. model 标准化 → tier (loop/code → code, 未知 model → flash)
 * 2. 如果 tier 不存在 → 查 TIER_FALLBACK → fallback 到 flash (主力)
 * 3. 从 tier 内按优先级排序 upstream
 * 4. Session Affinity: 有绑定时优先用绑定的
 * 5. 返回 candidates 列表用于 failover
 * 6. tier 内全部不可用 → 按 fallback 链降级
 */
export function route(tierId: TierId, affKey?: string | null): RoutingResult {
  const reg = getConfig();
  const normTier = normalizeTier(tierId);
  return tryTier(normTier, false, affKey || null, reg);
}

/**
 * 将客户端传入的 model 字段标准化为 tier id
 * - "loop/code" / "loop/flash" / "loop/pro" → 去掉 "loop/" 前缀
 * - "code" / "flash" / "pro" → 原样
 * - "claude-xxx" / "gpt-xxx" / 其他未知 → "flash" (主力兜底)
 */
export function normalizeTier(t: string): TierId {
  if (!t || typeof t !== "string") return "flash";
  let s = t.trim();
  if (s.startsWith("loop/")) s = s.slice(5);
  if (s === "pro" || s === "flash" || s === "code") return s as TierId;
  return "flash";
}

/** 端口默认 tier；仅当 model 显式为 pro/flash/code（或 loop/*）时尊重客户端 */
export function resolveRequestTier(model: string | undefined, portDefault: TierId): TierId {
  if (!model || typeof model !== "string") return portDefault;
  let s = model.trim();
  if (s.startsWith("loop/")) s = s.slice(5);
  if (s === "pro" || s === "flash" || s === "code") return s;
  return portDefault;
}

const SCORE_EPS = 0.05;
const _rrCursor = new Map<string, number>();

/** 同 priority + 接近分数时 round-robin，避免赢家通吃。
 *  付费钥同 priority 忽略分数差：否则成功多的 A 永远压死 B（flash-b total_success=0）。
 */
function fairPick(tier: TierId, sorted: UpstreamConfig[]): UpstreamConfig[] {
  if (sorted.length <= 1) return sorted;
  const bestP = sorted[0].tier_priority ?? 99;
  const bestS = getScore(sorted[0].name);
  const paidHead = isPaidUpstream(sorted[0]);
  const peers: UpstreamConfig[] = [];
  for (const u of sorted) {
    if ((u.tier_priority ?? 99) !== bestP) break;
    if (paidHead && isPaidUpstream(u)) {
      peers.push(u);
      continue;
    }
    if (Math.abs(getScore(u.name) - bestS) > SCORE_EPS) break;
    peers.push(u);
  }
  if (peers.length <= 1) return sorted;
  const rrKey = paidHead ? `${tier}:paid` : tier;
  const idx = (_rrCursor.get(rrKey) ?? 0) % peers.length;
  _rrCursor.set(rrKey, idx + 1);
  const pick = peers[idx];
  return [pick, ...sorted.filter(u => u.name !== pick.name)];
}

/** 仅供测试：重置 RR 游标 */
export function _resetFairCursorForTest(): void {
  _rrCursor.clear();
}

function tryTier(
  tier: TierId,
  isFb: boolean,
  affKey: string | null,
  reg: TierRegistry,
  visited: Set<TierId> = new Set(),
): RoutingResult {
  if (visited.has(tier)) {
    console.error(`[route] fallback loop detected at tier '${tier}', visited: ${[...visited].join(",")}`);
    return { upstream: null, candidates: [], tier, is_fallback: true, fallback_model: null };
  }
  visited.add(tier);

  let tierUp = reg.tiers.get(tier);

  // Tier 不存在 → 查 fallback 链 → fallback 到 flash (主力 tier)
  if (!tierUp || tierUp.length === 0) {
    const fbTier = TIER_FALLBACK[tier];
    if (fbTier) {
      console.warn(`[route] tier '${tier}' empty → fallback to '${fbTier}'`);
      return tryTier(fbTier, true, affKey, reg, visited);
    }
    if (tier !== "flash" && reg.tiers.has("flash") && !visited.has("flash")) {
      console.warn(`[route] tier '${tier}' not found → fallback to 'flash' (main tier)`);
      return tryTier("flash", true, affKey, reg, visited);
    }
    // 全局兜底: 所有可用 upstream (按 tier_priority)
    const allOk = reg.all
      .filter(u => u.api_key && isUpstreamOk(u))
      .sort((a, b) => (a.tier_priority ?? 99) - (b.tier_priority ?? 99));
    const fb = allOk[0] || null;
    if (!fb) {
      const minCd = getMinCooldownSec(reg.all);
      console.warn(`[route] no upstream available at all (${reg.all.length} upstreams all on cooldown/disabled, earliest recovery in ~${minCd}s)`);
    }
    return {
      upstream: fb,
      candidates: allOk,
      tier,
      is_fallback: true,
      fallback_model: fb?.fallback_model || null,
    };
  }

  // Session Affinity: 优先用绑定的上游 (R5: 跨 tier 复用, key 基于 upstream name)
  // 例外：绑在 paid 上但免费池已恢复 → 放开轮转（paid 仍留候选末位保底）
  if (affKey && !isFb) {
    for (const up of tierUp) {
      if (!isUpstreamOk(up)) continue;
      const afUp = affinityGet(affKey, up.name);
      if (afUp) {
        const others = tierUp.filter(x => isUpstreamOk(x) && x.name !== afUp.name);
        if (isPaidUpstream(afUp)) {
          const freeOk = others.filter(x => !isPaidUpstream(x));
          if (freeOk.length >= 1) {
            const preferProxy = process.env.LOOP_PREFER_PROXY === "1";
            const freeSorted = freeOk.slice().sort((a, b) => {
              const pd = (a.tier_priority ?? 99) - (b.tier_priority ?? 99);
              if (pd !== 0) return pd;
              const ap = (a.proxy || "").trim() ? 1 : 0;
              const bp = (b.proxy || "").trim() ? 1 : 0;
              if (ap !== bp) return preferProxy ? ap - bp : bp - ap;
              return getScore(b.name) - getScore(a.name);
            });
            const candidates = boostPaidCandidates(
              fairPick(tier, [...freeSorted, afUp, ...others.filter(isPaidUpstream)]),
              tier,
            );
            return {
              upstream: candidates[0] || freeSorted[0]!,
              candidates,
              tier,
              is_fallback: false,
              fallback_model: null,
            };
          }
        }
        const candidates = boostPaidCandidates([afUp, ...others], tier);
        return {
          upstream: candidates[0] || afUp,
          candidates,
          tier,
          is_fallback: false,
          fallback_model: null,
        };
      }
    }
  }

  // 优先级优先；默认同档 prefer direct（HK 慢）；LOOP_PREFER_PROXY=1 才优先 proxy
  const okList = tierUp.filter(isUpstreamOk);
  if (okList.length > 0) {
    const preferProxy = process.env.LOOP_PREFER_PROXY === "1";
    const sorted = okList.slice().sort((a, b) => {
      const pd = (a.tier_priority ?? 99) - (b.tier_priority ?? 99);
      if (pd !== 0) return pd;
      const ap = (a.proxy || "").trim() ? 1 : 0;
      const bp = (b.proxy || "").trim() ? 1 : 0;
      if (ap !== bp) return preferProxy ? ap - bp : bp - ap; // default: direct(0) first
      return getScore(b.name) - getScore(a.name);
    });
    const ordered = boostPaidCandidates(fairPick(tier, sorted), tier);
    return {
      upstream: ordered[0],
      candidates: ordered,
      tier,
      is_fallback: isFb,
      fallback_model: null,
    };
  }

  // Tier 内全部不可用 → fallback
  // R5: 删 affinity 时按当前 upstream 名字删 (跨 tier 复用)
  if (affKey) {
    for (const up of tierUp) affinityDelete(affKey, up.name);
  }

  const fbTier = TIER_FALLBACK[tier];
  if (fbTier) {
    console.warn(`[route] tier '${tier}' unavailable → fallback to '${fbTier}'`);
    return tryTier(fbTier, true, affKey, reg, visited);
  }
  if (tier !== "flash" && reg.tiers.has("flash") && !visited.has("flash")) {
    console.warn(`[route] tier '${tier}' all unavailable → fallback to 'flash' (main tier)`);
    return tryTier("flash", true, affKey, reg, visited);
  }

  // 显式 flash：free 全冷却时仍须带上付费兜底（含短冷却的 paid，禁止空候选 502 断任务）
  if (tier === "flash") {
    const paidAll = tierUp
      .filter(u => !!u.api_key && isPaidUpstream(u))
      .sort((a, b) => (a.tier_priority ?? 99) - (b.tier_priority ?? 99));
    if (paidAll.length) {
      const paidOk = paidAll.filter(isUpstreamOk);
      const base = paidOk.length ? paidOk : paidAll;
      const candidates = fairPick(tier, base);
      console.warn(
        `[route] flash free unavailable → last-resort paid ${candidates[0]!.name}` +
          (paidOk.length ? "" : " (short-cool bypass)"),
      );
      return {
        upstream: candidates[0]!,
        candidates,
        tier,
        is_fallback: true,
        fallback_model: null,
      };
    }
    const minCd = getMinCooldownSec(tierUp);
    console.warn(
      `[route] flash all unavailable; no paid key configured (earliest recovery ~${minCd}s)`,
    );
    return {
      upstream: null,
      candidates: [],
      tier,
      is_fallback: true,
      fallback_model: null,
    };
  }

  // 全局兜底: 所有可用 upstream (按 tier_priority)
  const allOk = reg.all
    .filter(u => u.api_key && isUpstreamOk(u))
    .sort((a, b) => (a.tier_priority ?? 99) - (b.tier_priority ?? 99));
  const fb = allOk[0] || null;
  if (!fb) {
    console.warn(`[route] all upstreams in tier '${tier}' unavailable AND no global fallback available (${reg.all.length} upstreams all on cooldown/disabled)`);
  } else {
    console.warn(`[route] all upstreams in tier '${tier}' unavailable → global fallback: ${fb.name} (cooldown remaining: ${getMinCooldownSec(reg.all)})`);
    if (!fb.fallback_model) {
      console.warn(`[route] fallback upstream '${fb.name}' has no fallback_model defined, 降级链可能断裂`);
    }
  }
  return {
    upstream: fb,
    candidates: allOk,
    tier,
    is_fallback: true,
    fallback_model: fb?.fallback_model || null,
  };
}

// 定期清理过期 affinity
const _affinityCleanupTimer = setInterval(affinityCleanup, 60000);
_affinityCleanupTimer.unref?.(); // M8: 不阻塞进程退出
