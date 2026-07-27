// ═══════════════════════════════════════════════════════════════
//  Per-upstream egress（HTTP CONNECT / SOCKS 代理）
//  用途：免费多钥拆到不同出口 IP，避免 OpenCode 同 IP RPM 整池假死
// ═══════════════════════════════════════════════════════════════

import { ProxyAgent, Agent, fetch as undiciFetch, type Dispatcher, type RequestInit as UndiciRequestInit } from "undici";
import type { UpstreamConfig } from "./types.js";
import { TIMEOUTS } from "./config.js";
import { isPaidUpstream } from "./tiers.js";

const _agents = new Map<string, Dispatcher>();

function makeDirectAgent(): Agent {
  return new Agent({
    connect: { timeout: TIMEOUTS.CONNECT_MS },
    bodyTimeout: 0,
    headersTimeout: Math.max(TIMEOUTS.HEADERS_MS, TIMEOUTS.ATTEMPT_PAID_MS + 5_000),
    keepAliveTimeout: TIMEOUTS.KEEPALIVE_MS,
  });
}

let _direct = makeDirectAgent();

/** 解析上游 proxy 字段；支持 http(s):// 或 socks5://host:port */
export function resolveUpstreamProxy(up: UpstreamConfig): string | null {
  const raw = (up.proxy || "").trim();
  if (!raw) return null;
  if (/^(https?|socks5?):\/\//i.test(raw)) return raw;
  // 允许写 host:port → 默认 http CONNECT
  if (/^[\w.\[\]:-]+:\d+$/.test(raw)) return `http://${raw}`;
  return null;
}

export function getDispatcherForUpstream(up: UpstreamConfig): Dispatcher {
  const proxy = resolveUpstreamProxy(up);
  if (!proxy) return _direct;
  let agent = _agents.get(proxy);
  if (!agent) {
    agent = new ProxyAgent({
      uri: proxy,
      requestTls: { timeout: TIMEOUTS.CONNECT_MS },
      proxyTls: { timeout: TIMEOUTS.CONNECT_MS },
    });
    _agents.set(proxy, agent);
    console.log(`[egress] proxy agent ready: ${proxy}`);
  }
  return agent;
}

function mergeAbortSignals(a?: AbortSignal | null, b?: AbortSignal | null): AbortSignal | undefined {
  if (!a && !b) return undefined;
  if (!a) return b!;
  if (!b) return a;
  if (typeof AbortSignal.any === "function") return AbortSignal.any([a, b]);
  return b;
}

export interface UpstreamFetchOpts {
  /** 覆盖首包超时；默认 free=ATTEMPT_MS / paid=ATTEMPT_PAID_MS */
  attemptMs?: number;
}

/** 带上游出口的 fetch（代理失败时抛错，由 fallback 换钥）
 *
 * 必须用 undici 自带的 fetch：Node 全局 fetch 与 npm undici.ProxyAgent
 * 混用会报 InvalidArgumentError: invalid onRequestStart method。
 *
 * 首包超时：仅限制「等到 Response 头」；拿到头后立刻 clearTimeout，
 * 否则 AbortSignal 会在流式读 body 时把长对话杀掉（Desktop 大上下文必炸）。
 */
export async function upstreamFetch(
  up: UpstreamConfig,
  url: string,
  init: RequestInit = {},
  opts?: UpstreamFetchOpts,
): Promise<Response> {
  const dispatcher = getDispatcherForUpstream(up);
  const attemptMs =
    opts?.attemptMs ??
    (isPaidUpstream(up) ? TIMEOUTS.ATTEMPT_PAID_MS : TIMEOUTS.ATTEMPT_MS);

  const ac = new AbortController();
  const timer = setTimeout(() => {
    ac.abort(Object.assign(new Error("attempt timeout"), { name: "TimeoutError" }));
  }, attemptMs);

  const signal = mergeAbortSignals(init.signal as AbortSignal | undefined, ac.signal);
  try {
    const resp = await undiciFetch(url, {
      ...(init as UndiciRequestInit),
      dispatcher,
      signal,
    });
    // 首包已到：解除 attempt abort，让 SSE/body 长流不受 15–55s 墙限制
    clearTimeout(timer);
    return resp as unknown as Response;
  } catch (e) {
    clearTimeout(timer);
    throw e;
  }
}

/** 测试用：清空 agent 缓存 */
export function _resetEgressAgentsForTest(): void {
  for (const a of _agents.values()) {
    try {
      void (a as Agent).close?.();
    } catch {
      /* ignore */
    }
  }
  _agents.clear();
  _direct = makeDirectAgent();
}
