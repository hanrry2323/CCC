// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.2 — 透明降级 (Stream Peek + Retry + Budget + Trail)
// ═══════════════════════════════════════════════════════════════

import type { UpstreamConfig, RoutingResult, FallbackAttempt, TrailRecord } from "./types.js";
import { classifyErr, StallError, getStallIdleMs } from "./utils.js";
import { getAppContext } from "./context.js";
import { bad } from "./health.js";
import { recordOutcome, computeBackoffCooldown } from "./scoring.js";
import { getConfig } from "./config.js";
import { ledgerReserve, ledgerSettle, ledgerMarkQuotaExhausted, ledgerWouldExceed } from "./ledger.js";
import { affinityDeleteByUpstream } from "./router.js";

const MAX_QUOTA_COOLDOWN = 4 * 3600;
const MAX_PROVIDER_COOLDOWN = 30 * 60;
const MAX_SAME_UPSTREAM_RETRIES = 2;
const RETRY_DELAY_MS = 300;
const PROVIDER_BREAKER_THRESHOLD = 3;
const PROVIDER_BREAKER_SEC = 120;
const MAX_TRAIL_RING = 200;
const TRAIL_HEADER_MAX = 512;

function failoverMaxAttempts(): number {
  return Math.max(1, parseInt(process.env.FAILOVER_MAX_ATTEMPTS || "6", 10) || 6);
}
function failoverMaxMs(): number {
  return Math.max(1000, parseInt(process.env.FAILOVER_MAX_MS || "45000", 10) || 45_000);
}

function sleep(ms: number): Promise<void> { return new Promise(r => setTimeout(r, ms)); }

function isPlatformError(errMsg: string): boolean {
  return /error from provider|upstream request failed|upstream error|internal server error/i.test(errMsg);
}

const DEFAULT_PEEK_LINES = 5;

function computeEarliestCooldownSec(candidates: UpstreamConfig[]): number {
  const cooldowns = getAppContext().cooldowns;
  const now = Date.now();
  let earliest = 0;
  for (const u of candidates) {
    const c = cooldowns.get(u.name);
    if (c && c.until > now) {
      const left = Math.ceil((c.until - now) / 1000);
      if (earliest === 0 || left < earliest) earliest = left;
    }
  }
  return Math.max(earliest, 5);
}

export function formatExhaustedMessage(
  candidates: UpstreamConfig[],
  failureReasons: Map<string, string>,
): string {
  const cooldowns = getAppContext().cooldowns;
  const lines: string[] = ["当前所有上游不可用："];
  const now = Date.now();

  for (const u of candidates) {
    let status: string;
    if (failureReasons.has(u.name)) {
      const reason = failureReasons.get(u.name)!;
      if (reason.startsWith("HTTP ")) status = `不可用（${reason}）`;
      else if (reason === "empty") status = "不可用（空响应）";
      else if (reason === "fetch") status = "不可用（网络错误）";
      else status = `不可用（${reason}）`;
    } else if (u.enabled === false) {
      status = "已禁用";
    } else {
      const c = cooldowns.get(u.name);
      if (c && c.until > now) {
        status = `冷却中（剩余 ${Math.ceil((c.until - now) / 1000)}s）`;
      } else {
        status = "不可用";
      }
    }
    lines.push(`  ${u.name} — ${status}`);
  }
  lines.push("");
  lines.push("操作：编辑 upstreams.json 增删上游，或等冷却结束后自动恢复");
  return lines.join("\n");
}

function markBad(up: UpstreamConfig, status: number, errMsg: string): void {
  let sec = 20;
  const cls = classifyErr(errMsg);
  if (cls) {
    sec = computeBackoffCooldown(up.name, cls.sec, cls.quota ? MAX_QUOTA_COOLDOWN : MAX_PROVIDER_COOLDOWN);
    if (cls.quota) ledgerMarkQuotaExhausted(up);
  } else if (status === 429) {
    sec = 60;
    ledgerMarkQuotaExhausted(up);
  } else if (/empty/i.test(errMsg)) sec = 20;
  else if (status >= 500 || status === 529) sec = 30;
  else if (status === 400) sec = 15;
  else sec = 30;

  bad(up, sec, `h${status}:${errMsg.slice(0, 36)}`);
  recordOutcome(up.name, false);
  if (cls?.quota || status === 429) affinityDeleteByUpstream(up.name);
  if (up.provider_group) triggerProviderBreaker(up.provider_group, errMsg);
}

export { markBad };

function getProviderMembers(group: string): UpstreamConfig[] {
  return getConfig().all.filter(u => u.provider_group === group && u.enabled !== false);
}

function triggerProviderBreaker(group: string, errMsg: string): void {
  const ctx = getAppContext();
  const next = (ctx.providerFailCounts.get(group) ?? 0) + 1;
  ctx.providerFailCounts.set(group, next);
  if (next < PROVIDER_BREAKER_THRESHOLD) return;

  const members = getProviderMembers(group);
  const until = Date.now() + PROVIDER_BREAKER_SEC * 1000;
  ctx.providerCooldowns.set(group, {
    until,
    reason: `breaker tripped after ${next} consecutive failures: ${errMsg.slice(0, 60)}`,
  });
  for (const m of members) {
    const existing = ctx.cooldowns.get(m.name);
    if (!existing || existing.until < until) {
      ctx.cooldowns.set(m.name, { until, reason: `provider-breaker(${group}): ${errMsg.slice(0, 36)}` });
    }
  }
  console.warn(`[breaker] provider="${group}" tripped after ${next} failures, ${members.length} upstreams cooled for ${PROVIDER_BREAKER_SEC}s`);
  ctx.providerFailCounts.set(group, 0);
}

export function recordProviderSuccess(up: UpstreamConfig): void {
  if (up.provider_group) getAppContext().providerFailCounts.set(up.provider_group, 0);
}

export async function peekStream(
  response: Response,
  peekLines: number = DEFAULT_PEEK_LINES,
): Promise<{
  reader: ReadableStreamDefaultReader<Uint8Array>;
  firstLines: string[];
  buffered: string;
  done: boolean;
}> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buff = "";
  const firstLines: string[] = [];
  let done = false;
  try {
    while (!done && firstLines.length < peekLines) {
      const r = await reader.read();
      done = r.done!;
      if (r.value) {
        buff += decoder.decode(r.value, { stream: true });
        const lines = buff.split("\n");
        buff = lines.pop() || "";
        firstLines.push(...lines);
      }
    }
  } catch (e) {
    reader.cancel().catch(() => {});
    throw e;
  }
  return { reader, firstLines, buffered: buff, done };
}

export function peekHasContent(firstLines: string[]): { hasContent: boolean } {
  let sawDataLine = false;
  for (const ln of firstLines) {
    const tr = ln.trim();
    if (!tr.startsWith("data: ")) continue;
    if (tr.slice(6) === "[DONE]") continue;
    sawDataLine = true;
    try {
      const p = JSON.parse(tr.slice(6));
      if (p.error) continue;
      const delta = p.choices?.[0]?.delta;
      if (delta?.content && delta.content.length > 0) return { hasContent: true };
      if (delta?.tool_calls?.length > 0) return { hasContent: true };
      if (delta?.reasoning_content && delta.reasoning_content.length > 0) return { hasContent: true };
      if (delta?.reasoning && delta.reasoning.length > 0) return { hasContent: true };
      if (p.choices?.[0]?.finish_reason) return { hasContent: true };
      if (p.usage && (p.usage.prompt_tokens || p.usage.total_tokens)) return { hasContent: true };
      if (p.object === "chat.completion.chunk" || p.object === "chat.completion") return { hasContent: true };
    } catch { /* truncated */ }
  }
  return { hasContent: sawDataLine };
}

export function peekHasError(firstLines: string[]): { hasError: boolean; errorMessage: string } {
  for (const ln of firstLines) {
    const tr = ln.trim();
    if (!tr.startsWith("data: ")) continue;
    try {
      const p = JSON.parse(tr.slice(6));
      if (p.error) return { hasError: true, errorMessage: p.error.message || "" };
    } catch { /* skip */ }
  }
  return { hasError: false, errorMessage: "" };
}

function pushTrail(trail: FallbackAttempt[], name: string, reason: string, t0: number): void {
  trail.push({ name, reason, ms: Date.now() - t0, at: Date.now() });
}

function recordTrailRing(tier: string, ok: boolean, routed: string | undefined, trail: FallbackAttempt[]): void {
  const ring = getAppContext().recentTrails;
  const rec: TrailRecord = { at: Date.now(), tier, ok, routed, trail: trail.slice() };
  ring.value.push(rec);
  if (ring.value.length > MAX_TRAIL_RING) ring.value = ring.value.slice(-MAX_TRAIL_RING);
}

/** 压缩 trail 为响应头 */
export function formatTrailHeader(trail: FallbackAttempt[]): string {
  const s = trail.map(t => `${t.name}:${t.reason}`).join(",");
  return s.length <= TRAIL_HEADER_MAX ? s : s.slice(0, TRAIL_HEADER_MAX - 3) + "...";
}

export function applyTrailHeaders(
  res: { setHeader(k: string, v: string): void; headersSent?: boolean },
  routed: string | null | undefined,
  trail: FallbackAttempt[],
): void {
  if (res.headersSent) return;
  try {
    if (routed) res.setHeader("X-Routed-Upstream", routed);
    if (trail.length) res.setHeader("X-Fallback-Trail", formatTrailHeader(trail));
  } catch {
    /* headers may already be committed */
  }
}

interface StreamTrySuccess {
  ok: true;
  reader: ReadableStreamDefaultReader<Uint8Array>;
  upstream: UpstreamConfig;
  firstLines: string[];
  buffered: string;
}

interface StreamTryFailure {
  ok: false;
  lastErr: string;
  exhausted: boolean;
  platformError: boolean;
  httpStatus?: number;
}

type StreamTryResult = StreamTrySuccess | StreamTryFailure;

async function tryUpstreamStream(
  up: UpstreamConfig,
  streamFn: (up: UpstreamConfig) => Promise<Response | null>,
  failedPlatforms: Set<string>,
): Promise<StreamTryResult> {
  let lastErr = "";
  let lastStatus = 0;

  if (!ledgerReserve(up)) {
    return { ok: false, lastErr: `ledger:${ledgerWouldExceed(up) || "limit"}`, exhausted: true, platformError: false };
  }

  for (let retry = 0; retry <= MAX_SAME_UPSTREAM_RETRIES; retry++) {
    if (retry > 0) await sleep(RETRY_DELAY_MS);
    try {
      const resp = await streamFn(up);
      if (!resp) {
        lastErr = "fetch";
        continue;
      }

      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        let errMsg = `HTTP ${resp.status}`;
        try {
          const e = JSON.parse(text);
          if (e?.error?.message) errMsg = e.error.message;
        } catch { /* ignore */ }
        lastErr = errMsg.slice(0, 60);
        lastStatus = resp.status;
        if (resp.status !== 429 && resp.status < 500 && retry < MAX_SAME_UPSTREAM_RETRIES) continue;
        console.warn(`[fallback] stream ${up.name}: HTTP ${resp.status} ${lastErr}${retry ? " (retry exhausted)" : ""}`);
        markBad(up, resp.status, errMsg);
        const platErr = isPlatformError(errMsg);
        if (platErr) failedPlatforms.add(up.base_url);
        ledgerSettle(up, { success: false, rollbackRequest: resp.status !== 429 && resp.status < 500 });
        return { ok: false, lastErr, exhausted: true, platformError: platErr, httpStatus: resp.status };
      }

      let reader: ReadableStreamDefaultReader<Uint8Array>;
      let firstLines: string[];
      let buffered: string;
      try {
        const peeked = await peekStream(resp);
        reader = peeked.reader;
        firstLines = peeked.firstLines;
        buffered = peeked.buffered;
      } catch (e) {
        console.warn(`[fallback] stream peek err ${up.name}: ${(e as Error).message.slice(0, 50)}`);
        lastErr = "peek";
        continue;
      }

      const { hasError, errorMessage } = peekHasError(firstLines);
      if (hasError) {
        reader.cancel();
        lastErr = errorMessage.slice(0, 40);
        if (retry < MAX_SAME_UPSTREAM_RETRIES) continue;
        console.warn(`[fallback] stream body-err ${up.name}: ${errorMessage.slice(0, 50)}`);
        markBad(up, 0, errorMessage);
        const platErr = isPlatformError(errorMessage);
        if (platErr) failedPlatforms.add(up.base_url);
        ledgerSettle(up, { success: false, rollbackRequest: false });
        return { ok: false, lastErr, exhausted: true, platformError: platErr };
      }

      const { hasContent } = peekHasContent(firstLines);
      if (!hasContent) {
        reader.cancel();
        lastErr = "empty";
        if (retry < MAX_SAME_UPSTREAM_RETRIES) continue;
        console.warn(`[fallback] stream empty content from ${up.name}`);
        markBad(up, 0, "empty stream");
        ledgerSettle(up, { success: false, rollbackRequest: true });
        return { ok: false, lastErr, exhausted: true, platformError: false };
      }

      // Success peek — reserved held until protocol settles via logUsage/ledgerSettle
      return { ok: true, reader, upstream: up, firstLines, buffered };
    } catch (e) {
      console.warn(`[fallback] stream fetch err ${up.name}: ${(e as Error).message.slice(0, 50)}`);
      lastErr = "fetch";
    }
  }

  if (lastErr === "fetch") markBad(up, 0, "fetch failed after retries");
  else if (lastErr === "peek") markBad(up, 0, "peek failed after retries");
  else if (lastErr === "empty") markBad(up, 0, "empty stream");
  ledgerSettle(up, {
    success: false,
    rollbackRequest: lastErr === "fetch" || lastErr === "peek" || lastErr === "empty",
  });
  return { ok: false, lastErr, exhausted: true, platformError: false, httpStatus: lastStatus };
}

export interface StreamFallbackResult {
  reader: ReadableStreamDefaultReader<Uint8Array> | null;
  upstream: UpstreamConfig | null;
  firstLines: string[];
  buffered: string;
  errorCode?: number;
  errorMessage?: string;
  emptyUpstream?: UpstreamConfig | null;
  retryAfterSec?: number;
  trail: FallbackAttempt[];
  /** true when consume finished successfully (or no consume) */
  consumedOk?: boolean;
  /** stall after client bytes — cannot failover */
  stalledAfterWrite?: boolean;
}

export interface StreamConsumeCtx {
  reader: ReadableStreamDefaultReader<Uint8Array>;
  firstLines: string[];
  buffered: string;
  upstream: UpstreamConfig;
  stallMs: number;
}

export interface StreamFallbackOptions {
  /** 若提供：peek 成功后调用；抛 StallError 且未写客户端时可换渠 */
  consume?: (ctx: StreamConsumeCtx) => Promise<void>;
  /** 是否已向客户端写出 body（由 consume 更新，或外部闭包） */
  getBytesWritten?: () => number;
}

function buildExhaustedResult(
  candidates: UpstreamConfig[],
  failureReasons: Map<string, string>,
  trail: FallbackAttempt[],
  tier: string,
): StreamFallbackResult {
  recordTrailRing(tier, false, undefined, trail);
  return {
    reader: null,
    upstream: null,
    firstLines: [],
    buffered: "",
    errorCode: 503,
    errorMessage: formatExhaustedMessage(candidates, failureReasons),
    retryAfterSec: computeEarliestCooldownSec(candidates),
    trail,
  };
}

/**
 * 带透明重试 + 预算 + trail 的流式转发。
 * 可选 consume：支持 stall 换渠（仅 bytesWritten===0）。
 */
export async function streamWithFallback(
  routing: RoutingResult,
  streamFn: (up: UpstreamConfig) => Promise<Response | null>,
  opts?: StreamFallbackOptions | (() => string),
): Promise<StreamFallbackResult> {
  // 兼容旧签名 makeRequestSummary?: () => string
  const options: StreamFallbackOptions =
    typeof opts === "function" || opts === undefined ? {} : opts;

  const { candidates } = routing;
  const failureReasons = new Map<string, string>();
  const failedPlatforms = new Set<string>();
  const trail: FallbackAttempt[] = [];
  const budgetStart = Date.now();
  let attempts = 0;
  const stallMs = getStallIdleMs();

  for (const up of candidates) {
    if (attempts >= failoverMaxAttempts()) {
      pushTrail(trail, "*", "budget:attempts", budgetStart);
      break;
    }
    if (Date.now() - budgetStart >= failoverMaxMs()) {
      pushTrail(trail, "*", "budget:wall", budgetStart);
      break;
    }

    if (failedPlatforms.has(up.base_url)) {
      failureReasons.set(up.name, "skipped (same platform fault)");
      pushTrail(trail, up.name, "skip:platform", budgetStart);
      continue;
    }

    const exceed = ledgerWouldExceed(up);
    if (exceed) {
      failureReasons.set(up.name, `ledger:${exceed}`);
      pushTrail(trail, up.name, `ledger:${exceed}`, budgetStart);
      continue;
    }

    attempts += 1;
    const t0 = Date.now();
    const result = await tryUpstreamStream(up, streamFn, failedPlatforms);
    if (!result.ok) {
      failureReasons.set(up.name, result.lastErr);
      pushTrail(trail, up.name, result.lastErr, t0);
      continue;
    }

    if (!options.consume) {
      ledgerSettle(up, { success: true, tokens: 0 });
      pushTrail(trail, up.name, "ok", t0);
      recordTrailRing(routing.tier, true, up.name, trail);
      return {
        reader: result.reader,
        upstream: result.upstream,
        firstLines: result.firstLines,
        buffered: result.buffered,
        trail,
        consumedOk: true,
      };
    }

    try {
      await options.consume({
        reader: result.reader,
        firstLines: result.firstLines,
        buffered: result.buffered,
        upstream: result.upstream,
        stallMs,
      });
      ledgerSettle(up, { success: true, tokens: 0 });
      pushTrail(trail, up.name, "ok", t0);
      recordTrailRing(routing.tier, true, up.name, trail);
      return {
        reader: result.reader,
        upstream: result.upstream,
        firstLines: result.firstLines,
        buffered: result.buffered,
        trail,
        consumedOk: true,
      };
    } catch (e) {
      const isStall = e instanceof StallError || /stall|Stream read timeout/i.test((e as Error).message);
      const written = options.getBytesWritten?.() ?? 0;
      result.reader.cancel().catch(() => {});

      if (isStall && written === 0) {
        markBad(up, 0, "stream stall (pre-write)");
        ledgerSettle(up, { success: false, rollbackRequest: false });
        failureReasons.set(up.name, "stall");
        pushTrail(trail, up.name, "stall", t0);
        continue;
      }

      if (isStall) {
        markBad(up, 0, "stream stall (mid-write)");
        ledgerSettle(up, { success: false, rollbackRequest: false });
        pushTrail(trail, up.name, "stall:after-write", t0);
        recordTrailRing(routing.tier, false, up.name, trail);
        return {
          reader: null,
          upstream: up,
          firstLines: result.firstLines,
          buffered: result.buffered,
          trail,
          consumedOk: false,
          stalledAfterWrite: true,
        };
      }

      markBad(up, 0, (e as Error).message);
      ledgerSettle(up, { success: false, rollbackRequest: true });
      failureReasons.set(up.name, (e as Error).message.slice(0, 40));
      pushTrail(trail, up.name, "consume-err", t0);
      if (written > 0) {
        recordTrailRing(routing.tier, false, up.name, trail);
        return {
          reader: null,
          upstream: up,
          firstLines: result.firstLines,
          buffered: result.buffered,
          trail,
          consumedOk: false,
          stalledAfterWrite: true,
        };
      }
    }
  }

  return buildExhaustedResult(candidates, failureReasons, trail, routing.tier);
}

// ── Non-Stream ──

export interface NonStreamResult {
  body: any;
  upstream: UpstreamConfig | null;
  errorCode?: number;
  errorMessage?: string;
  retryAfterSec?: number;
  trail: FallbackAttempt[];
}

async function tryUpstreamNonStream(
  up: UpstreamConfig,
  fetchFn: (up: UpstreamConfig) => Promise<{ response: Response; body: any } | null>,
  failedPlatforms: Set<string>,
): Promise<{ ok: true; body: any; upstream: UpstreamConfig } | { ok: false; lastErr: string; platformError: boolean }> {
  let lastErr = "";

  if (!ledgerReserve(up)) {
    return { ok: false, lastErr: `ledger:${ledgerWouldExceed(up) || "limit"}`, platformError: false };
  }

  for (let retry = 0; retry <= MAX_SAME_UPSTREAM_RETRIES; retry++) {
    if (retry > 0) await sleep(RETRY_DELAY_MS);
    try {
      const result = await fetchFn(up);
      if (!result) {
        lastErr = "fetch";
        continue;
      }
      const { response: resp, body: d } = result;

      if (d?.error) {
        lastErr = (d.error.message || "body-error").slice(0, 40);
        if (retry < MAX_SAME_UPSTREAM_RETRIES) continue;
        markBad(up, 0, d.error.message || "body-error");
        const platErr = isPlatformError(d.error.message || "");
        if (platErr) failedPlatforms.add(up.base_url);
        ledgerSettle(up, { success: false, rollbackRequest: false });
        return { ok: false, lastErr, platformError: platErr };
      }

      if (!resp.ok) {
        let errMsg = `HTTP ${resp.status}`;
        try {
          const e = JSON.parse(typeof d === "string" ? d : JSON.stringify(d));
          if (e?.error?.message) errMsg = e.error.message;
        } catch { /* ignore */ }
        lastErr = errMsg.slice(0, 60);
        if (resp.status !== 429 && resp.status < 500 && retry < MAX_SAME_UPSTREAM_RETRIES) continue;
        markBad(up, resp.status, errMsg);
        const platErr = isPlatformError(errMsg);
        if (platErr) failedPlatforms.add(up.base_url);
        ledgerSettle(up, { success: false, rollbackRequest: resp.status !== 429 && resp.status < 500 });
        return { ok: false, lastErr, platformError: platErr };
      }

      // Success — settle request now; tokens via logUsage
      ledgerSettle(up, { success: true, tokens: 0 });
      // Re-reserve token settle path: logUsage will add tokens only.
      // Actually we already settled request. logUsage should only add tokens without another request.
      return { ok: true, body: d, upstream: up };
    } catch (e) {
      console.warn(`[fallback] fetch err ${up.name}: ${(e as Error).message.slice(0, 50)}`);
      lastErr = "fetch";
    }
  }

  if (lastErr === "fetch") markBad(up, 0, "fetch failed after retries");
  ledgerSettle(up, { success: false, rollbackRequest: true });
  return { ok: false, lastErr, platformError: false };
}

export async function nonStreamWithFallback(
  routing: RoutingResult,
  fetchFn: (up: UpstreamConfig) => Promise<{ response: Response; body: any } | null>,
): Promise<NonStreamResult> {
  const { candidates } = routing;
  const failureReasons = new Map<string, string>();
  const failedPlatforms = new Set<string>();
  const trail: FallbackAttempt[] = [];
  const budgetStart = Date.now();
  let attempts = 0;

  for (const up of candidates) {
    if (attempts >= failoverMaxAttempts()) {
      pushTrail(trail, "*", "budget:attempts", budgetStart);
      break;
    }
    if (Date.now() - budgetStart >= failoverMaxMs()) {
      pushTrail(trail, "*", "budget:wall", budgetStart);
      break;
    }
    if (failedPlatforms.has(up.base_url)) {
      failureReasons.set(up.name, "skipped (same platform fault)");
      pushTrail(trail, up.name, "skip:platform", budgetStart);
      continue;
    }
    const exceed = ledgerWouldExceed(up);
    if (exceed) {
      failureReasons.set(up.name, `ledger:${exceed}`);
      pushTrail(trail, up.name, `ledger:${exceed}`, budgetStart);
      continue;
    }

    attempts += 1;
    const t0 = Date.now();
    const result = await tryUpstreamNonStream(up, fetchFn, failedPlatforms);
    if (result.ok) {
      pushTrail(trail, up.name, "ok", t0);
      recordTrailRing(routing.tier, true, up.name, trail);
      return { body: result.body, upstream: result.upstream, trail };
    }
    failureReasons.set(up.name, result.lastErr);
    pushTrail(trail, up.name, result.lastErr, t0);
  }

  recordTrailRing(routing.tier, false, undefined, trail);
  return {
    body: null,
    upstream: null,
    errorCode: 503,
    errorMessage: formatExhaustedMessage(candidates, failureReasons),
    retryAfterSec: computeEarliestCooldownSec(candidates),
    trail,
  };
}

/** 成功流结束后结算 token（request 已在 peek 成功时仍 reserved） */
export function settleStreamSuccess(up: UpstreamConfig, tokens: number): void {
  ledgerSettle(up, { success: true, tokens });
}

/** 流失败释放 reserved */
export function settleStreamFailure(up: UpstreamConfig, rollback = false): void {
  ledgerSettle(up, { success: false, rollbackRequest: rollback });
}
