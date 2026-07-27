// ═══════════════════════════════════════════════════════════════
//  Per-upstream egress（HTTP CONNECT / SOCKS 代理）
//  用途：免费多钥拆到不同出口 IP，避免 OpenCode 同 IP RPM 整池假死
// ═══════════════════════════════════════════════════════════════

import { ProxyAgent, Agent, fetch as undiciFetch, type Dispatcher, type RequestInit as UndiciRequestInit } from "undici";
import type { UpstreamConfig } from "./types.js";
import { TIMEOUTS } from "./config.js";

const _agents = new Map<string, Dispatcher>();

function makeDirectAgent(): Agent {
  return new Agent({
    connect: { timeout: TIMEOUTS.CONNECT_MS },
    bodyTimeout: 0,
    headersTimeout: Math.max(TIMEOUTS.HEADERS_MS, TIMEOUTS.ATTEMPT_MS + 5_000),
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

/** 带上游出口的 fetch（代理失败时抛错，由 fallback 换钥）
 *
 * 必须用 undici 自带的 fetch：Node 全局 fetch 与 npm undici.ProxyAgent
 * 混用会报 InvalidArgumentError: invalid onRequestStart method。
 * 默认叠加 LOOP_UPSTREAM_ATTEMPT_MS 硬超时，避免单钥挂死吃光 failover 墙钟。
 */
export async function upstreamFetch(
  up: UpstreamConfig,
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  const dispatcher = getDispatcherForUpstream(up);
  const attemptSignal = AbortSignal.timeout(TIMEOUTS.ATTEMPT_MS);
  const signal = mergeAbortSignals(init.signal as AbortSignal | undefined, attemptSignal);
  return undiciFetch(url, {
    ...(init as UndiciRequestInit),
    dispatcher,
    signal,
  }) as unknown as Promise<Response>;
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
