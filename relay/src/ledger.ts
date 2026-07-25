// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.2 — 上游配额账本（RPM/RPD/TPM/TPD）
//  主动避限流；触顶只跳过，不写 markBad 长冷却
// ═══════════════════════════════════════════════════════════════

import type { UpstreamConfig } from "./types.js";
import { getAppContext } from "./context.js";

const WINDOW_MS = 60_000;

export type LedgerExceedReason = "rpm" | "rpd" | "tpm" | "tpd";

export interface LedgerCounters {
  /** rolling 60s request timestamps */
  reqTs: number[];
  /** rolling 60s token events { t, n } */
  tokEvents: { t: number; n: number }[];
  dayKey: string;
  reqDay: number;
  tokDay: number;
  /** reserved but not yet settled (in-flight requests) */
  reserved: number;
}

export interface LedgerSnapshot {
  name: string;
  rpm_used: number;
  rpm_limit: number | null;
  rpd_used: number;
  rpd_limit: number | null;
  tpm_used: number;
  tpm_limit: number | null;
  tpd_used: number;
  tpd_limit: number | null;
  reserved: number;
  hold_until: number | null;
  exceed: LedgerExceedReason | null;
}

function utcDayKey(now = Date.now()): string {
  return new Date(now).toISOString().slice(0, 10);
}

function limitsOf(up: UpstreamConfig) {
  const q = up.quota;
  return {
    rpm: q?.rpm,
    rpd: q?.rpd,
    tpm: q?.tpm,
    tpd: q?.tpd ?? q?.daily_tokens,
  };
}

function hasAnyLimit(up: UpstreamConfig): boolean {
  const L = limitsOf(up);
  return L.rpm != null || L.rpd != null || L.tpm != null || L.tpd != null;
}

function ensureEntry(name: string): LedgerCounters {
  const map = getAppContext().ledger;
  let e = map.get(name);
  if (!e) {
    e = { reqTs: [], tokEvents: [], dayKey: utcDayKey(), reqDay: 0, tokDay: 0, reserved: 0 };
    map.set(name, e);
  }
  const today = utcDayKey();
  if (e.dayKey !== today) {
    e.dayKey = today;
    e.reqDay = 0;
    e.tokDay = 0;
  }
  return e;
}

function pruneWindow(e: LedgerCounters, now: number): void {
  const cut = now - WINDOW_MS;
  while (e.reqTs.length && e.reqTs[0]! < cut) e.reqTs.shift();
  while (e.tokEvents.length && e.tokEvents[0]!.t < cut) e.tokEvents.shift();
}

function rpmUsed(e: LedgerCounters): number {
  return e.reqTs.length + e.reserved;
}

function tpmUsed(e: LedgerCounters): number {
  return e.tokEvents.reduce((s, x) => s + x.n, 0);
}

/** 若再发 1 请求（可选预估 token）是否触顶；返回原因 */
export function ledgerWouldExceed(up: UpstreamConfig, estTokens = 0): LedgerExceedReason | null {
  if (!hasAnyLimit(up)) return null;
  const L = limitsOf(up);
  const e = ensureEntry(up.name);
  const now = Date.now();
  pruneWindow(e, now);

  if (L.rpm != null && rpmUsed(e) >= L.rpm) return "rpm";
  if (L.rpd != null && e.reqDay + e.reserved >= L.rpd) return "rpd";
  if (L.tpm != null && tpmUsed(e) + Math.max(0, estTokens) >= L.tpm) return "tpm";
  if (L.tpd != null && e.tokDay + Math.max(0, estTokens) >= L.tpd) return "tpd";
  return null;
}

/** 尝试前占用 1 个 request 名额；若已触顶返回 false */
export function ledgerReserve(up: UpstreamConfig): boolean {
  if (!hasAnyLimit(up)) return true;
  if (ledgerWouldExceed(up)) return false;
  const e = ensureEntry(up.name);
  e.reserved += 1;
  return true;
}

/**
 * 结算一次尝试。
 * - success: 记入 request + tokens，扣 reserved
 * - failure + rollbackRequest: 只扣 reserved（瞬态失败可回滚）
 * - failure 且不回滚（如 429）: 仍计入 request，避免重试风暴
 */
export function ledgerSettle(
  up: UpstreamConfig,
  opts: { tokens?: number; success: boolean; rollbackRequest?: boolean },
): void {
  if (!hasAnyLimit(up)) return;
  const e = ensureEntry(up.name);
  const now = Date.now();
  pruneWindow(e, now);

  if (e.reserved > 0) e.reserved -= 1;

  if (opts.success) {
    e.reqTs.push(now);
    e.reqDay += 1;
    const n = Math.max(0, opts.tokens || 0);
    if (n > 0) {
      e.tokEvents.push({ t: now, n });
      e.tokDay += n;
    }
    return;
  }

  if (opts.rollbackRequest) return;

  // 计入失败请求（429 等），不记 token
  e.reqTs.push(now);
  e.reqDay += 1;
}

/** 上游 429/配额类：把日请求拉满（若配置了 rpd）或标记 hold */
export function ledgerMarkQuotaExhausted(up: UpstreamConfig): void {
  if (!hasAnyLimit(up)) return;
  const L = limitsOf(up);
  const e = ensureEntry(up.name);
  if (L.rpd != null) e.reqDay = Math.max(e.reqDay, L.rpd);
  if (L.tpd != null) e.tokDay = Math.max(e.tokDay, L.tpd);
  if (L.rpm != null) {
    const now = Date.now();
    pruneWindow(e, now);
    while (e.reqTs.length < L.rpm) e.reqTs.push(now);
  }
}

export function ledgerHoldUntil(up: UpstreamConfig): number | null {
  const reason = ledgerWouldExceed(up);
  if (!reason) return null;
  const e = ensureEntry(up.name);
  const now = Date.now();
  pruneWindow(e, now);
  if (reason === "rpm" || reason === "tpm") {
    const oldest = reason === "rpm" ? e.reqTs[0] : e.tokEvents[0]?.t;
    if (oldest == null) return now + 1000;
    return oldest + WINDOW_MS;
  }
  // rpd/tpd → next UTC midnight
  const d = new Date();
  d.setUTCHours(24, 0, 0, 0);
  return d.getTime();
}

export function ledgerSnapshot(up: UpstreamConfig): LedgerSnapshot {
  const L = limitsOf(up);
  const e = ensureEntry(up.name);
  const now = Date.now();
  pruneWindow(e, now);
  const exceed = ledgerWouldExceed(up);
  return {
    name: up.name,
    rpm_used: rpmUsed(e),
    rpm_limit: L.rpm ?? null,
    rpd_used: e.reqDay + e.reserved,
    rpd_limit: L.rpd ?? null,
    tpm_used: tpmUsed(e),
    tpm_limit: L.tpm ?? null,
    tpd_used: e.tokDay,
    tpd_limit: L.tpd ?? null,
    reserved: e.reserved,
    hold_until: exceed ? ledgerHoldUntil(up) : null,
    exceed,
  };
}

export function ledgerAll(upstreams: UpstreamConfig[]): LedgerSnapshot[] {
  return upstreams.filter(hasAnyLimit).map(ledgerSnapshot);
}

/** 仅追加 token（请求次数已由 settle 记过） */
export function ledgerAddTokens(up: UpstreamConfig, tokens: number): void {
  if (!hasAnyLimit(up) || tokens <= 0) return;
  const e = ensureEntry(up.name);
  const now = Date.now();
  pruneWindow(e, now);
  e.tokEvents.push({ t: now, n: tokens });
  e.tokDay += tokens;
}

/** 测试用：清空账本 */
export function ledgerReset(): void {
  getAppContext().ledger.clear();
}
