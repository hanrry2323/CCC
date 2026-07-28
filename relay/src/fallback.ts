// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.2 — 透明降级 (Stream Peek + Retry + Budget + Trail)
// ═══════════════════════════════════════════════════════════════

import type { UpstreamConfig, RoutingResult, FallbackAttempt, TrailRecord } from "./types.js";
import { classifyErr, StallError, getStallIdleMs, streamReadWithTimeout, agentDebugLog } from "./utils.js";
import { getAppContext } from "./context.js";
import { bad } from "./health.js";
import { recordOutcome, computeBackoffCooldown } from "./scoring.js";
import { getConfig, TIMEOUTS } from "./config.js";
import { ledgerReserve, ledgerSettle, ledgerMarkQuotaExhausted, ledgerWouldExceed } from "./ledger.js";
import { affinityDeleteByUpstream } from "./router.js";
import { isPaidUpstream, isUpstreamOk } from "./tiers.js";

const MAX_QUOTA_COOLDOWN = 4 * 3600;
const MAX_PROVIDER_COOLDOWN = 30 * 60;
/** 同钥重试：超时/网络失败不重试，其它最多 1 次（共 2 次） */
const MAX_SAME_UPSTREAM_RETRIES = 1;
const RETRY_DELAY_MS = 300;
const PROVIDER_BREAKER_THRESHOLD = 3;
const PROVIDER_BREAKER_SEC = 120;
/** 突发限流 Retry-After 封顶；超过此值视为日配额耗尽（Zen 免费池常给到 UTC 重置） */
const RATE_LIMIT_RETRY_AFTER_CAP = 120;
const PAID_FETCH_COOLDOWN_SEC = 3; // 付费超时勿长冷却：否则 free 全死时只剩空候选 → 502 断任务
const FREE_FETCH_COOLDOWN_SEC = 20;
const FETCH_GRAY_SEC = 90;
/** 同请求最多试几个 free；按「不同出口」优先轮转，勿一失败就钉死 paid */
const MAX_FREE_ATTEMPTS_PER_REQ = 4;
const KEY_STAGGER_MS = 50;
const MAX_TRAIL_RING = 200;
const TRAIL_HEADER_MAX = 512;
/**
 * 按 route() 候选序取付费钥（钉钥在首位时禁止再 RR）。
 * 跨请求双付费轮转只在 router.fairPick；此处换钥仅作失败 failover。
 */
function pickPaidInCandidateOrder(
  candidates: UpstreamConfig[],
  paidUsable: UpstreamConfig[],
): UpstreamConfig {
  if (paidUsable.length === 1) return paidUsable[0]!;
  const usable = new Set(paidUsable.map(u => u.name));
  for (const u of candidates) {
    if (usable.has(u.name)) return u;
  }
  return paidUsable[0]!;
}

/** free 钥连续 fetch 失败灰名单（不进账号 breaker） */
const _fetchGrayUntil = new Map<string, number>();

export function markFetchGray(name: string, sec = FETCH_GRAY_SEC): void {
  _fetchGrayUntil.set(name, Date.now() + sec * 1000);
}
export function isFetchGray(name: string): boolean {
  const until = _fetchGrayUntil.get(name);
  if (!until) return false;
  if (until <= Date.now()) {
    _fetchGrayUntil.delete(name);
    return false;
  }
  return true;
}
export function _clearFetchGrayForTest(): void {
  _fetchGrayUntil.clear();
}

function failoverMaxAttempts(): number {
  return Math.max(1, parseInt(process.env.FAILOVER_MAX_ATTEMPTS || "6", 10) || 6);
}
function failoverMaxMs(): number {
  // 付费 TTFB 常 20–55s；60s 墙钟几乎无余量 → 一碰 free 就 budget:wall 断任务
  return Math.max(1000, parseInt(process.env.FAILOVER_MAX_MS || "45000", 10) || 45_000);
}

/** 墙钟余量低于此值则不再试 free（对齐 2017 热更 dist） */
function paidWallReserveMs(): number {
  return TIMEOUTS.ATTEMPT_MS + TIMEOUTS.PEEK_PAID_MS + 5_000;
}

export { isPaidUpstream };

/**
 * 本请求内「刚撞 RPM」的钥名集合键。
 * 2026-07-28：IP/proxy 出口轮换退役 — 429 只跳过该钥，不再按 base_url||proxy 封 sibling。
 * @deprecated 名称保留兼容测试；语义 = upstream.name
 */
export function egressRateLimitKey(up: UpstreamConfig): string {
  return up.name;
}

/** @deprecated IP 轮换退役后恒为「还有未试 free」；保留导出以免外部引用炸 */
export function hasUntriedFreeOtherEgress(
  candidates: UpstreamConfig[],
  tried: Set<string>,
  isBlocked: (u: UpstreamConfig) => boolean,
): boolean {
  return candidates.some(
    u => !tried.has(u.name) && !isPaidUpstream(u) && !isBlocked(u),
  );
}

function sleep(ms: number): Promise<void> { return new Promise(r => setTimeout(r, ms)); }

function isPlatformError(errMsg: string): boolean {
  return /error from provider|upstream request failed|upstream error|internal server error/i.test(errMsg);
}

function parseRetryAfter(resp: Response): number | null {
  const raw = resp.headers.get("retry-after") || resp.headers.get("Retry-After");
  if (!raw) return null;
  const n = parseInt(raw, 10);
  if (!Number.isNaN(n) && n > 0) return n;
  const date = Date.parse(raw);
  if (!Number.isNaN(date)) return Math.max(0, Math.ceil((date - Date.now()) / 1000));
  return null;
}

function isDailyQuotaError(errType: string | undefined, errMsg: string): boolean {
  if (errType === "FreeUsageLimitError") return true;
  return /usage limit reached|usage quota|额度用完|流量用完|配额|FreeUsage/i.test(errMsg);
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
      else if (reason === "fetch" || reason === "timeout") status = `不可用（网络错误${reason === "timeout" ? "/超时" : ""}）`;
      else if (reason.startsWith("skipped")) status = `跳过（${reason}）`;
      else if (reason === "paid_skipped_budget") status = "未试到（墙钟耗尽）";
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

interface MarkBadOpts {
  retryAfterSec?: number | null;
  errType?: string | null;
}

function markBad(up: UpstreamConfig, status: number, errMsg: string, opts: MarkBadOpts = {}): void {
  let sec = 20;
  const cls = classifyErr(errMsg);
  const paid = isPaidUpstream(up);
  const isFetchOrTimeout =
    status === 0 &&
    /fetch failed|attempt timeout|timeout|peek failed|UND_ERR|ECONN|ETIMEDOUT|aborted/i.test(errMsg);
  // Zen 免费池常回 429 "Rate limit exceeded" + 数小时 Retry-After（到日切），无 FreeUsage 类型也按日配额
  const longRetryAsQuota =
    status === 429 &&
    !!opts.retryAfterSec &&
    opts.retryAfterSec > RATE_LIMIT_RETRY_AFTER_CAP;
  const dailyQuota =
    isDailyQuotaError(opts.errType ?? undefined, errMsg) || longRetryAsQuota;
  // 限流（非日配额）：多钥同 IP 级联时若再乘 EWMA，会把整池锁 10 分钟→假死
  const isRateLimit =
    !dailyQuota &&
    (status === 429 || (cls != null && !cls.quota && /rate|限流|超限|too many/i.test(errMsg)));
  const isBalanceError =
    status === 401 ||
    status === 402 ||
    /insufficient balance|payment required|billing here/i.test(errMsg);

  if (dailyQuota && opts.retryAfterSec && opts.retryAfterSec > 60) {
    // 免费通道日配额耗尽：上游给了 retry-after（通常到 UTC 午夜），直接采用
    sec = opts.retryAfterSec;
    ledgerMarkQuotaExhausted(up);
  } else if (dailyQuota || cls?.quota) {
    sec = computeBackoffCooldown(up.name, cls?.sec ?? 300, MAX_QUOTA_COOLDOWN);
    ledgerMarkQuotaExhausted(up);
  } else if (paid && isBalanceError) {
    sec = Math.min(computeBackoffCooldown(up.name, 600, MAX_QUOTA_COOLDOWN), 3600);
    console.warn(`[fallback] paid balance/auth fail ${up.name}: ${errMsg.slice(0, 80)}`);
  } else if (isRateLimit) {
    // 固定短冷却，禁止 EWMA 放大；有 Retry-After 则采纳但封顶 RATE_LIMIT_RETRY_AFTER_CAP
    const ra = opts.retryAfterSec && opts.retryAfterSec > 0 ? opts.retryAfterSec : (cls?.sec ?? 60);
    sec = Math.min(Math.max(ra, 15), RATE_LIMIT_RETRY_AFTER_CAP);
  } else if (isFetchOrTimeout || /empty/i.test(errMsg)) {
    sec = paid ? PAID_FETCH_COOLDOWN_SEC : FREE_FETCH_COOLDOWN_SEC;
  } else if (cls) {
    sec = paid
      ? Math.min(computeBackoffCooldown(up.name, cls.sec, 120), 60)
      : computeBackoffCooldown(up.name, cls.sec, MAX_PROVIDER_COOLDOWN);
  } else if (status >= 500 || status === 529) sec = paid ? 15 : 30;
  else if (status === 400) sec = 15;
  else sec = paid ? PAID_FETCH_COOLDOWN_SEC : 30;

  bad(up, sec, `h${status}:${errMsg.slice(0, 36)}`);
  // 日配额 / 限流 / 瞬态网络：不记 EWMA 失败（否则低分×限流→多钥池假死）
  if (!dailyQuota && !isRateLimit && !cls?.quota && !isFetchOrTimeout) {
    recordOutcome(up.name, false);
  }
  if (cls?.quota || dailyQuota || isRateLimit) affinityDeleteByUpstream(up.name);
  // 限流 / 日配额 / 网络超时：不打 provider breaker（避免整账号团灭）
  // 付费钥永不账号 breaker
  if (
    up.provider_group &&
    !paid &&
    !isRateLimit &&
    !dailyQuota &&
    !isFetchOrTimeout
  ) {
    triggerProviderBreaker(up.provider_group, errMsg);
  }
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
  peekTimeoutMs?: number,
  signal?: AbortSignal,
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
  const budget = peekTimeoutMs ?? TIMEOUTS.PEEK_MS;
  const deadline = Date.now() + budget;
  const onAbort = () => {
    reader.cancel().catch(() => {});
  };
  if (signal?.aborted) {
    onAbort();
    throw Object.assign(new Error("peek aborted"), { name: "TimeoutError" });
  }
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    while (!done && firstLines.length < peekLines) {
      if (signal?.aborted) {
        throw Object.assign(new Error("peek aborted"), { name: "TimeoutError" });
      }
      const left = deadline - Date.now();
      if (left <= 0) {
        reader.cancel().catch(() => {});
        throw Object.assign(new Error("peek timeout"), { name: "TimeoutError" });
      }
      const r = await streamReadWithTimeout(reader, left);
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
  } finally {
    signal?.removeEventListener("abort", onAbort);
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

/** streamFn 可接收墙钟 AbortSignal，以便 FAILOVER_MAX_MS 打断进行中的 fetch/peek */
export type StreamFn = (up: UpstreamConfig, signal?: AbortSignal) => Promise<Response | null>;

async function tryUpstreamStream(
  up: UpstreamConfig,
  streamFn: StreamFn,
  failedPlatforms: Set<string>,
  signal?: AbortSignal,
  wallDeadlineMs?: number,
): Promise<StreamTryResult> {
  let lastErr = "";
  let lastStatus = 0;

  if (!ledgerReserve(up)) {
    return { ok: false, lastErr: `ledger:${ledgerWouldExceed(up) || "limit"}`, exhausted: true, platformError: false };
  }

  for (let retry = 0; retry <= MAX_SAME_UPSTREAM_RETRIES; retry++) {
    if (signal?.aborted) {
      lastErr = "timeout";
      break;
    }
    if (retry > 0) await sleep(RETRY_DELAY_MS);
    try {
      const resp = await streamFn(up, signal);
      if (!resp) {
        if (signal?.aborted) {
          lastErr = "timeout";
          break;
        }
        lastErr = "fetch";
        continue;
      }

      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        let errMsg = `HTTP ${resp.status}`;
        let errType: string | undefined;
        try {
          const e = JSON.parse(text);
          if (e?.error?.message) errMsg = e.error.message;
          if (e?.error?.type) errType = e.error.type;
        } catch { /* ignore */ }
        lastErr = errMsg.slice(0, 60);
        lastStatus = resp.status;
        if (resp.status !== 429 && resp.status < 500 && retry < MAX_SAME_UPSTREAM_RETRIES) continue;
        const retryAfter = parseRetryAfter(resp);
        console.warn(`[fallback] stream ${up.name}: HTTP ${resp.status} ${lastErr}${retry ? " (retry exhausted)" : ""}${retryAfter ? ` retry-after=${retryAfter}s` : ""}`);
        markBad(up, resp.status, errMsg, { retryAfterSec: retryAfter, errType });
        const platErr = isPlatformError(errMsg);
        if (platErr) failedPlatforms.add(up.base_url);
        ledgerSettle(up, { success: false, rollbackRequest: resp.status !== 429 && resp.status < 500 });
        return { ok: false, lastErr, exhausted: true, platformError: platErr, httpStatus: resp.status };
      }

      let reader: ReadableStreamDefaultReader<Uint8Array>;
      let firstLines: string[];
      let buffered: string;
      try {
        const basePeek = isPaidUpstream(up) ? TIMEOUTS.PEEK_PAID_MS : TIMEOUTS.PEEK_MS;
        const wallLeft = wallDeadlineMs != null ? Math.max(1, wallDeadlineMs - Date.now()) : basePeek;
        const peekMs = Math.min(basePeek, wallLeft);
        const peeked = await peekStream(resp, DEFAULT_PEEK_LINES, peekMs, signal);
        reader = peeked.reader;
        firstLines = peeked.firstLines;
        buffered = peeked.buffered;
      } catch (e) {
        const msg = (e as Error).message || "";
        console.warn(`[fallback] stream peek err ${up.name}: ${msg.slice(0, 50)}`);
        if (/timeout|stall|abort/i.test(msg)) {
          lastErr = "timeout";
          break;
        }
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
      const msg = (e as Error).message || "";
      const name = (e as Error).name || "";
      console.warn(`[fallback] stream fetch err ${up.name}: ${msg.slice(0, 50)}`);
      lastErr = /timeout|aborted|TimeoutError|budget:wall/i.test(name + msg) ? "timeout" : "fetch";
      // #region agent log
      agentDebugLog("B", "fallback.ts:tryUpstreamStream:catch", "streamFn threw", {
        up: up.name,
        lastErr,
        name,
        message: msg.slice(0, 120),
        signalAborted: !!signal?.aborted,
        retry,
      });
      // #endregion
      // 超时不重试同钥，立刻换下一家
      if (lastErr === "timeout") break;
    }
  }

  if (lastErr === "fetch") markBad(up, 0, "fetch failed after retries");
  else if (lastErr === "timeout") markBad(up, 0, "attempt timeout");
  else if (lastErr === "peek") markBad(up, 0, "peek failed after retries");
  else if (lastErr === "empty") markBad(up, 0, "empty stream");
  if ((lastErr === "fetch" || lastErr === "timeout") && !isPaidUpstream(up)) {
    markFetchGray(up.name);
  }
  ledgerSettle(up, {
    success: false,
    rollbackRequest: lastErr === "fetch" || lastErr === "timeout" || lastErr === "peek" || lastErr === "empty",
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
  /** 换钥 / 等待上游时心跳（写 SSE comment），勿计入 content lock */
  onAttemptWait?: () => void;
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

/** 挑选下一跳：免费钥快速轮换；墙钟不够或免费耗尽再插队 paid */
export function selectNextCandidate(
  candidates: UpstreamConfig[],
  tried: Set<string>,
  opts: {
    budgetStart: number;
    attempts: number;
    freeFailCount: number;
    failedPlatforms: Set<string>;
    /** 本请求内已 RPM 的钥名（仅该钥，不封 sibling） */
    rateLimitedHosts: Set<string>;
    /** 候选里无可用 free → 直接 paid */
    paidOnly?: boolean;
  },
): UpstreamConfig | null {
  const untried = candidates.filter(u => !tried.has(u.name));
  if (!untried.length) return null;

  const isBlocked = (u: UpstreamConfig): boolean =>
    opts.failedPlatforms.has(u.base_url) ||
    opts.rateLimitedHosts.has(u.name) ||
    !!ledgerWouldExceed(u) ||
    isFetchGray(u.name);

  const paidUsable = untried.filter(u => isPaidUpstream(u) && !isBlocked(u));
  const pickPaid = () => pickPaidInCandidateOrder(candidates, paidUsable);
  const wall = failoverMaxMs();
  const maxAtt = failoverMaxAttempts();
  const elapsed = Date.now() - opts.budgetStart;
  const attemptsLeft = maxAtt - opts.attempts;
  const freeTried = candidates.filter(u => tried.has(u.name) && !isPaidUpstream(u)).length;
  const wallLeft = wall - elapsed;
  const reserve = paidWallReserveMs();
  const nextFreeUsable = untried.filter(u => !isPaidUpstream(u) && !isBlocked(u));

  // route() 已把 paid 放首位（pinPaid / boost / last-resort）：禁止再插队 free，禁止双付费 RR 换钉钥
  if (
    paidUsable.length &&
    candidates[0] &&
    isPaidUpstream(candidates[0])
  ) {
    return pickPaid();
  }

  if (opts.paidOnly && paidUsable.length) {
    return pickPaid();
  }

  // 先吐出顺序上的 skip（本钥 RL / platform），保留 trail 可观测性
  const head = untried[0]!;
  if (isBlocked(head) && !isPaidUpstream(head)) return head;

  // 墙钟余量不够付费首包 → 立刻 paid（禁止再烧 free）
  if (paidUsable.length && wallLeft <= reserve) {
    return pickPaid();
  }

  // 同请求 free 次数上限
  if (paidUsable.length && freeTried >= MAX_FREE_ATTEMPTS_PER_REQ) {
    return pickPaid();
  }

  if (paidUsable.length && attemptsLeft <= 1) {
    if (!isPaidUpstream(head) || isBlocked(head)) return pickPaid();
  }

  // 免费钥快切：还有未试 free 就继续；耗尽或墙钟过半才强制 paid
  const forcePaid =
    paidUsable.length > 0 &&
    ((opts.freeFailCount >= 1 && nextFreeUsable.length === 0) ||
      elapsed >= wall * 0.55 ||
      wallLeft <= reserve);

  if (forcePaid) return pickPaid();

  if (nextFreeUsable.length) return nextFreeUsable[0]!;
  if (paidUsable.length) return pickPaid();
  return untried.find(u => !isBlocked(u)) || head;
}

function markPaidSkippedBudget(
  candidates: UpstreamConfig[],
  tried: Set<string>,
  failureReasons: Map<string, string>,
): void {
  for (const u of candidates) {
    if (isPaidUpstream(u) && !tried.has(u.name) && !failureReasons.has(u.name)) {
      failureReasons.set(u.name, "paid_skipped_budget");
    }
  }
}

/**
 * 带透明重试 + 预算 + trail 的流式转发。
 * 可选 consume：支持 stall 换渠（仅 bytesWritten===0）。
 * PaidGuarantee：免费失败/墙钟过半时强制插队 Go 付费钥。
 */
export async function streamWithFallback(
  routing: RoutingResult,
  streamFn: StreamFn,
  opts?: StreamFallbackOptions | (() => string),
): Promise<StreamFallbackResult> {
  // 兼容旧签名 makeRequestSummary?: () => string
  const options: StreamFallbackOptions =
    typeof opts === "function" || opts === undefined ? {} : opts;

  const { candidates } = routing;
  const failureReasons = new Map<string, string>();
  const failedPlatforms = new Set<string>();
  /** 本请求刚撞 RPM 的钥：只跳过该钥，继续快切 sibling free */
  const rateLimitedHosts = new Set<string>();
  const trail: FallbackAttempt[] = [];
  const budgetStart = Date.now();
  let attempts = 0;
  let freeFailCount = 0;
  const tried = new Set<string>();
  const stallMs = getStallIdleMs();
  const paidOnlyReq = !candidates.some(u => !isPaidUpstream(u) && isUpstreamOk(u));
  const pinPaidReq =
    !!candidates[0] &&
    isPaidUpstream(candidates[0]) &&
    candidates.some(u => !isPaidUpstream(u) && isUpstreamOk(u));
  let annotatedPaidReason = false;
  // #region agent log
  agentDebugLog("A", "fallback.ts:streamWithFallback:start", "stream fallback start", {
    tier: routing.tier,
    candidateN: candidates.length,
    paidOnlyReq,
    pinPaidReq,
    wallMs: failoverMaxMs(),
    attemptPaidMs: TIMEOUTS.ATTEMPT_PAID_MS,
    peekPaidMs: TIMEOUTS.PEEK_PAID_MS,
    names: candidates.map(c => c.name).slice(0, 12),
  });
  // #endregion

  while (true) {
    options.onAttemptWait?.();
    if (attempts >= failoverMaxAttempts()) {
      pushTrail(trail, "*", "budget:attempts", budgetStart);
      break;
    }
    const wallHit = Date.now() - budgetStart >= failoverMaxMs();
    if (wallHit) {
      const paidUntried = candidates.find(
        u => isPaidUpstream(u) && !tried.has(u.name) && !failedPlatforms.has(u.base_url)
          && !rateLimitedHosts.has(u.name) && !ledgerWouldExceed(u),
      );
      if (!paidUntried) {
        markPaidSkippedBudget(candidates, tried, failureReasons);
        pushTrail(trail, "*", "budget:wall", budgetStart);
        break;
      }
      // 墙钟已尽但仍有未试付费 → 强制只试付费
    }

    const up = selectNextCandidate(candidates, tried, {
      budgetStart,
      attempts,
      freeFailCount,
      failedPlatforms,
      rateLimitedHosts,
      paidOnly: paidOnlyReq,
    });
    if (!up) break;

    if (!annotatedPaidReason && isPaidUpstream(up)) {
      annotatedPaidReason = true;
      if (paidOnlyReq) pushTrail(trail, up.name, "paid_forced", budgetStart);
      else if (pinPaidReq) pushTrail(trail, up.name, "paid_pinned", budgetStart);
    }

    if (Date.now() - budgetStart >= failoverMaxMs() && !isPaidUpstream(up)) {
      markPaidSkippedBudget(candidates, tried, failureReasons);
      pushTrail(trail, "*", "budget:wall", budgetStart);
      break;
    }

    if (failedPlatforms.has(up.base_url)) {
      tried.add(up.name);
      failureReasons.set(up.name, "skipped (same platform fault)");
      pushTrail(trail, up.name, "skip:platform", budgetStart);
      continue;
    }
    if (rateLimitedHosts.has(up.name)) {
      tried.add(up.name);
      failureReasons.set(up.name, "skipped (key rate-limit)");
      pushTrail(trail, up.name, "skip:key-rl", budgetStart);
      continue;
    }
    if (isFetchGray(up.name)) {
      tried.add(up.name);
      failureReasons.set(up.name, "skipped (fetch-gray)");
      pushTrail(trail, up.name, "skip:fetch-gray", budgetStart);
      continue;
    }

    const exceed = ledgerWouldExceed(up);
    if (exceed) {
      tried.add(up.name);
      failureReasons.set(up.name, `ledger:${exceed}`);
      pushTrail(trail, up.name, `ledger:${exceed}`, budgetStart);
      continue;
    }

    tried.add(up.name);
    attempts += 1;
    const t0 = Date.now();
    const wallDeadline = budgetStart + failoverMaxMs();
    const wallLeft = wallDeadline - Date.now();
    if (wallLeft <= 0 && !isPaidUpstream(up)) {
      markPaidSkippedBudget(candidates, tried, failureReasons);
      pushTrail(trail, "*", "budget:wall", budgetStart);
      break;
    }
    // #region agent log
    agentDebugLog("A", "fallback.ts:streamWithFallback:attempt", "trying upstream", {
      up: up.name,
      paid: isPaidUpstream(up),
      attempts,
      wallLeft,
      freeFailCount,
      paidOnlyReq,
    });
    // #endregion
    // 墙钟可打断进行中的 fetch/peek（禁止单次拖死到 ATTEMPT 以外）
    const peerPaidLeft =
      isPaidUpstream(up) &&
      candidates.some(
        u =>
          u.name !== up.name &&
          isPaidUpstream(u) &&
          !tried.has(u.name) &&
          !failedPlatforms.has(u.base_url) &&
          !rateLimitedHosts.has(u.name) &&
          !ledgerWouldExceed(u),
      );
    // 还有下一把付费时：单次最多 ATTEMPT_PAID，禁止一把拖满整墙钟导致第二把永远 0 成功
    const armMs = peerPaidLeft
      ? Math.min(Math.max(1, wallLeft), TIMEOUTS.ATTEMPT_PAID_MS)
      : Math.max(1, wallLeft > 0 ? wallLeft : (isPaidUpstream(up) ? TIMEOUTS.ATTEMPT_PAID_MS : 1));
    const attemptAc = new AbortController();
    const wallTimer = setTimeout(() => {
      // #region agent log
      agentDebugLog("B", "fallback.ts:streamWithFallback:wallAbort", "wall timer fired", {
        up: up.name,
        elapsedMs: Date.now() - t0,
        wallLeftAtArm: wallLeft,
        armMs,
        peerPaidLeft,
      });
      // #endregion
      attemptAc.abort(Object.assign(new Error("budget:wall"), { name: "TimeoutError" }));
    }, armMs);
    let result: StreamTryResult;
    try {
      result = await tryUpstreamStream(up, streamFn, failedPlatforms, attemptAc.signal, wallDeadline);
    } finally {
      clearTimeout(wallTimer);
    }
    if (!result.ok) {
      failureReasons.set(up.name, result.lastErr);
      pushTrail(trail, up.name, result.lastErr, t0);
      // #region agent log
      agentDebugLog("A", "fallback.ts:streamWithFallback:fail", "upstream attempt failed", {
        up: up.name,
        lastErr: result.lastErr,
        elapsedMs: Date.now() - t0,
        paid: isPaidUpstream(up),
      });
      // #endregion
      if (!isPaidUpstream(up)) freeFailCount += 1;
      if (/rate.?limit|限流|超限|too many requests/i.test(result.lastErr)) {
        rateLimitedHosts.add(up.name);
      } else {
        await sleep(KEY_STAGGER_MS);
      }
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
        if (!isPaidUpstream(up)) freeFailCount += 1;
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
      if (!isPaidUpstream(up)) freeFailCount += 1;
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
  fetchFn: (up: UpstreamConfig, signal?: AbortSignal) => Promise<{ response: Response; body: any } | null>,
  failedPlatforms: Set<string>,
  signal?: AbortSignal,
): Promise<{ ok: true; body: any; upstream: UpstreamConfig } | { ok: false; lastErr: string; platformError: boolean }> {
  let lastErr = "";

  if (!ledgerReserve(up)) {
    return { ok: false, lastErr: `ledger:${ledgerWouldExceed(up) || "limit"}`, platformError: false };
  }

  for (let retry = 0; retry <= MAX_SAME_UPSTREAM_RETRIES; retry++) {
    if (signal?.aborted) {
      lastErr = "timeout";
      break;
    }
    if (retry > 0) await sleep(RETRY_DELAY_MS);
    try {
      const result = await fetchFn(up, signal);
      if (!result) {
        lastErr = "fetch";
        continue;
      }
      const { response: resp, body: d } = result;

      if (d?.error) {
        lastErr = (d.error.message || "body-error").slice(0, 40);
        if (retry < MAX_SAME_UPSTREAM_RETRIES) continue;
        markBad(up, 0, d.error.message || "body-error", { errType: d.error.type });
        const platErr = isPlatformError(d.error.message || "");
        if (platErr) failedPlatforms.add(up.base_url);
        ledgerSettle(up, { success: false, rollbackRequest: false });
        return { ok: false, lastErr, platformError: platErr };
      }

      if (!resp.ok) {
        let errMsg = `HTTP ${resp.status}`;
        let errType: string | undefined;
        try {
          const e = JSON.parse(typeof d === "string" ? d : JSON.stringify(d));
          if (e?.error?.message) errMsg = e.error.message;
          if (e?.error?.type) errType = e.error.type;
        } catch { /* ignore */ }
        lastErr = errMsg.slice(0, 60);
        if (resp.status !== 429 && resp.status < 500 && retry < MAX_SAME_UPSTREAM_RETRIES) continue;
        const retryAfter = parseRetryAfter(resp);
        markBad(up, resp.status, errMsg, { retryAfterSec: retryAfter, errType });
        const platErr = isPlatformError(errMsg);
        if (platErr) failedPlatforms.add(up.base_url);
        ledgerSettle(up, { success: false, rollbackRequest: resp.status !== 429 && resp.status < 500 });
        return { ok: false, lastErr, platformError: platErr };
      }

      // Success — settle request now; tokens via logUsage
      ledgerSettle(up, { success: true, tokens: 0 });
      return { ok: true, body: d, upstream: up };
    } catch (e) {
      const msg = (e as Error).message || "";
      console.warn(`[fallback] fetch err ${up.name}: ${msg.slice(0, 50)}`);
      lastErr = /timeout|aborted|TimeoutError/i.test(msg) ? "timeout" : "fetch";
      if (lastErr === "timeout") break;
    }
  }

  if (lastErr === "fetch") markBad(up, 0, "fetch failed after retries");
  else if (lastErr === "timeout") markBad(up, 0, "attempt timeout");
  ledgerSettle(up, { success: false, rollbackRequest: true });
  return { ok: false, lastErr, platformError: false };
}

export async function nonStreamWithFallback(
  routing: RoutingResult,
  fetchFn: (up: UpstreamConfig, signal?: AbortSignal) => Promise<{ response: Response; body: any } | null>,
): Promise<NonStreamResult> {
  const { candidates } = routing;
  const failureReasons = new Map<string, string>();
  const failedPlatforms = new Set<string>();
  const rateLimitedHosts = new Set<string>();
  const trail: FallbackAttempt[] = [];
  const budgetStart = Date.now();
  let attempts = 0;
  let freeFailCount = 0;
  const tried = new Set<string>();
  const paidOnlyReq = !candidates.some(u => !isPaidUpstream(u) && isUpstreamOk(u));
  const pinPaidReq =
    !!candidates[0] &&
    isPaidUpstream(candidates[0]) &&
    candidates.some(u => !isPaidUpstream(u) && isUpstreamOk(u));
  let annotatedPaidReason = false;

  while (true) {
    if (attempts >= failoverMaxAttempts()) {
      pushTrail(trail, "*", "budget:attempts", budgetStart);
      break;
    }
    if (Date.now() - budgetStart >= failoverMaxMs()) {
      const paidUntried = candidates.find(
        u => isPaidUpstream(u) && !tried.has(u.name) && !failedPlatforms.has(u.base_url)
          && !rateLimitedHosts.has(u.name) && !ledgerWouldExceed(u),
      );
      if (!paidUntried) {
        markPaidSkippedBudget(candidates, tried, failureReasons);
        pushTrail(trail, "*", "budget:wall", budgetStart);
        break;
      }
    }

    const up = selectNextCandidate(candidates, tried, {
      budgetStart,
      attempts,
      freeFailCount,
      failedPlatforms,
      rateLimitedHosts,
      paidOnly: paidOnlyReq,
    });
    if (!up) break;
    if (!annotatedPaidReason && isPaidUpstream(up)) {
      annotatedPaidReason = true;
      if (paidOnlyReq) pushTrail(trail, up.name, "paid_forced", budgetStart);
      else if (pinPaidReq) pushTrail(trail, up.name, "paid_pinned", budgetStart);
    }
    if (Date.now() - budgetStart >= failoverMaxMs() && !isPaidUpstream(up)) {
      markPaidSkippedBudget(candidates, tried, failureReasons);
      pushTrail(trail, "*", "budget:wall", budgetStart);
      break;
    }

    if (failedPlatforms.has(up.base_url)) {
      tried.add(up.name);
      failureReasons.set(up.name, "skipped (same platform fault)");
      pushTrail(trail, up.name, "skip:platform", budgetStart);
      continue;
    }
    if (rateLimitedHosts.has(up.name)) {
      tried.add(up.name);
      failureReasons.set(up.name, "skipped (key rate-limit)");
      pushTrail(trail, up.name, "skip:key-rl", budgetStart);
      continue;
    }

    const exceed = ledgerWouldExceed(up);
    if (exceed) {
      tried.add(up.name);
      failureReasons.set(up.name, `ledger:${exceed}`);
      pushTrail(trail, up.name, `ledger:${exceed}`, budgetStart);
      continue;
    }

    tried.add(up.name);
    attempts += 1;
    const t0 = Date.now();
    const wallDeadline = budgetStart + failoverMaxMs();
    const wallLeft = wallDeadline - Date.now();
    const attemptAc = new AbortController();
    const wallTimer = setTimeout(() => {
      attemptAc.abort(Object.assign(new Error("budget:wall"), { name: "TimeoutError" }));
    }, Math.max(1, wallLeft > 0 ? wallLeft : (isPaidUpstream(up) ? TIMEOUTS.ATTEMPT_PAID_MS : 1)));
    let result: Awaited<ReturnType<typeof tryUpstreamNonStream>>;
    try {
      result = await tryUpstreamNonStream(up, fetchFn, failedPlatforms, attemptAc.signal);
    } finally {
      clearTimeout(wallTimer);
    }
    if (result.ok) {
      pushTrail(trail, up.name, "ok", t0);
      recordTrailRing(routing.tier, true, up.name, trail);
      return { body: result.body, upstream: result.upstream, trail };
    }
    failureReasons.set(up.name, result.lastErr);
    pushTrail(trail, up.name, result.lastErr, t0);
    if (!isPaidUpstream(up)) freeFailCount += 1;
    if (/rate.?limit|限流|超限|too many requests/i.test(result.lastErr)) {
      rateLimitedHosts.add(up.name);
    } else {
      await sleep(KEY_STAGGER_MS);
    }
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
